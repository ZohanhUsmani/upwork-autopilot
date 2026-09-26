"""
Upwork Autopilot — FastAPI Backend

Features:
- Upwork OAuth + GraphQL API (reads: jobs, profile, proposals, messages)
- Claude API (job scoring, proposal generation, improvement)
- Playwright submission provider (apply to jobs via headless browser)
- Composio submission provider (optional, when API key configured)
- SQLite analytics + activity log
- Auto-bidder scheduler (scan → score → draft, human-in-the-loop submission)

Env vars (set on VPS):
  CLAUDE_API_KEY
  UPWORK_API_KEY        (OAuth access token from developers.upwork.com)
  COMPOSIO_API_KEY      (optional)
  ENCRYPTION_KEY         (Fernet key for encrypting stored credentials)
  API_HOST, API_PORT
  FRONTEND_URL           (Netlify URL for CORS)
"""

import logging
from contextlib import asynccontextmanager
from datetime import date, timedelta
import json
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from core import db
from core.config import FRONTEND_URL
from services.autobidder import AutoBidder
from services.claude_service import analyze_job, generate_proposal, improve_proposal, process_profile
from services.composio_provider import register_composio_provider
from services.playwright_provider import PlaywrightProvider
from services.submission_providers import try_submit
from services.upwork_client import UpworkGraphQLClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("autopilot")

# ---- Lifecycle ----

autobidder: AutoBidder | None = None
playwright_provider: PlaywrightProvider | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Init DB
    db.init_db()

    # Register Composio provider (if key configured)
    register_composio_provider()

    # Init Playwright provider
    global playwright_provider
    playwright_provider = PlaywrightProvider()
    # Don't auto-launch browser here — launch on first use to avoid blocking startup

    # Init autobidder (started/stopped via API endpoints)
    global autobidder
    autobidder = AutoBidder("")  # token set when credentials saved; scheduler uses DB token
    yield
    # Cleanup
    if autobidder:
        autobidder.stop()
    if playwright_provider:
        playwright_provider.close()


app = FastAPI(
    title="Upwork Autopilot API",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_URL, "http://localhost:5173", "https://*.netlify.app"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---- Pydantic Models ----

class JobAnalyzeRequest(BaseModel):
    job_url: str
    job_description: str | None = None


class ProposalGenerateRequest(BaseModel):
    job_id: str
    job_title: str
    job_description: str
    budget: str
    skills: list[str]
    client_name: str
    screening_questions: list[dict[str, Any]] | None = None
    profile_id: int | None = None


class ProposalSubmitRequest(BaseModel):
    proposal_id: int


class ProposalImproveRequest(BaseModel):
    proposal_id: int
    feedback: str


class AutobidSettingsRequest(BaseModel):
    min_score: int | None = None
    max_budget_usd: int | None = None
    skills_filter: list[str] | None = None
    exclude_skills: list[str] | None = None
    job_types: list[str] | None = None
    locations: list[str] | None = None
    hourly_rate_min: float | None = None
    hourly_rate_max: float | None = None
    max_proposals_per_day: int | None = None
    new_jobs_only: bool | None = None
    proposal_style: str | None = None
    custom_instructions: str | None = None


class StartStopRequest(BaseModel):
    running: bool


class CredentialSaveRequest(BaseModel):
    claude_api_key: str | None = None
    upwork_api_key: str | None = None
    composio_api_key: str | None = None


class ProfileSyncRequest(BaseModel):
    pass


# ---- Helpers ----

def _get_upwork_client():
    from core.db import get_conn
    from core.crypto import decrypt

    conn = get_conn()
    row = conn.execute("SELECT * FROM creds WHERE id = 1").fetchone()
    conn.close()
    if not row or not row["upwork_api_key_encrypted"]:
        raise HTTPException(status_code=400, detail="Upwork API key not configured")
    token = decrypt(row["upwork_api_key_encrypted"])
    return UpworkGraphQLClient(token)


def _get_profile():
    from core.db import get_conn
    conn = get_conn()
    row = conn.execute("SELECT * FROM profile WHERE id = 1").fetchone()
    conn.close()
    if not row or not row["data"]:
        return None
    import json
    return json.loads(row["data"])


# ---- Routes ----

@app.get("/health")
async def health():
    return {"status": "ok", "autobidder_running": autobidder.is_running if autobidder else False}


# ---- Credentials ----

@app.post("/api/credentials/save")
async def save_credentials(req: CredentialSaveRequest):
    """Save encrypted credentials to the database."""
    from core.crypto import encrypt

    existing = None
    from core.db import get_conn
    conn = get_conn()
    row = conn.execute("SELECT * FROM creds WHERE id = 1").fetchone()
    if row:
        existing = dict(row)
    conn.close()

    claude_encrypted = encrypt(req.claude_api_key) if req.claude_api_key else (existing["claude_api_key_encrypted"] if existing else None)
    upwork_encrypted = encrypt(req.upwork_api_key) if req.upwork_api_key else (existing["upwork_api_key_encrypted"] if existing else None)
    composio_encrypted = encrypt(req.composio_api_key) if req.composio_api_key else (existing["composio_api_key_encrypted"] if existing else None)

    conn = get_conn()
    conn.execute(
        """INSERT OR REPLACE INTO creds
           (id, claude_api_key_encrypted, upwork_api_key_encrypted, composio_api_key_encrypted, saved_at)
           VALUES (1, ?, ?, ?, CURRENT_TIMESTAMP)""",
        (claude_encrypted, upwork_encrypted, composio_encrypted),
    )
    conn.commit()
    conn.close()

    logger.info("Credentials saved (claude=%s, upwork=%s, composio=%s)",
                bool(req.claude_api_key), bool(req.upwork_api_key), bool(req.composio_api_key))
    return {"success": True}


@app.post("/api/credentials/verify-upwork")
async def verify_upwork_credentials():
    """Test the Upwork API key by fetching the profile."""
    try:
        client = _get_upwork_client()
        profile_data = client.get_my_profile()
        if profile_data:
            return {"success": True, "profile": profile_data}
        raise HTTPException(status_code=400, detail="Could not fetch profile — check API key")
    except Exception as exc:
        logger.error("Upwork credential verification failed: %s", exc)
        raise HTTPException(status_code=400, detail=f"Upwork verification failed: {exc}")


# ---- Profile ----

@app.get("/api/profile")
async def get_profile():
    """Get the stored profile."""
    profile = _get_profile()
    if not profile:
        raise HTTPException(status_code=404, detail="No profile synced yet")
    return profile


@app.post("/api/profile/sync")
async def sync_profile():
    """Fetch and store the Upwork profile from the GraphQL API."""
    try:
        client = _get_upwork_client()
        raw = client.get_my_profile()
        if not raw or not raw.get("freelancerProfile"):
            raise HTTPException(status_code=400, detail="Could not fetch profile from Upwork")

        profile = process_profile(raw["freelancerProfile"])

        from core.db import get_conn
        conn = get_conn()
        conn.execute(
            "INSERT OR REPLACE INTO profile (id, data, updated_at) VALUES (1, ?, CURRENT_TIMESTAMP)",
            (json.dumps(profile),),
        )
        conn.commit()
        conn.close()

        logger.info("Profile synced: %s %s", profile.get("firstname"), profile.get("lastname"))
        return {"success": True, "profile": profile}
    except Exception as exc:
        logger.error("Profile sync failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


# ---- Job Analysis (Fit Check) ----

@app.post("/api/jobs/analyze")
async def analyze_job_endpoint(req: JobAnalyzeRequest):
    """Analyze a job URL or description and return a 0-100 score + red flags + tips."""
    try:
        profile = _get_profile()

        # If a job_url is provided, try to extract job ID and fetch details
        job_data = {
            "title": "Unknown",
            "description": req.job_description or "",
            "jobId": req.job_url.split("/")[-1] if req.job_url else "unknown",
        }

        # Try to fetch from Upwork API if we have a real URL
        if req.job_url and "upwork.com/jobs/" in req.job_url:
            try:
                job_id = req.job_url.rstrip("/").split("/")[-1]
                client = _get_upwork_client()
                fetched = client.get_job_details(job_id)
                if fetched and fetched.get("jobPostingLookup"):
                    job_data = fetched["jobPostingLookup"]
            except Exception as fetch_exc:
                logger.warning("Could not fetch job details from API, using provided description: %s", fetch_exc)
                if not req.job_description:
                    raise HTTPException(status_code=400, detail="Job URL provided but API fetch failed and no description given")

        analysis = analyze_job(job_data, profile)
        return analysis
    except Exception as exc:
        logger.error("Job analysis failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


# ---- Proposal Generation ----

@app.post("/api/proposals/generate")
async def generate_proposal_endpoint(req: ProposalGenerateRequest):
    """Generate a cover letter + screening answers for a job."""
    try:
        profile = _get_profile()
        if not profile:
            raise HTTPException(status_code=400, detail="No profile synced — sync your profile first")

        # Build job dict
        screening = req.screening_questions or []
        job = {
            "jobId": req.job_id,
            "title": req.job_title,
            "description": req.job_description,
            "budget": req.budget,
            "skills": req.skills,
            "client": {"name": req.client_name},
            "screeningQuestions": screening,
        }

        result = generate_proposal(
            job=job,
            profile=profile,
            cover_letter_style=None,  # loaded from settings if needed
            custom_instructions=None,
        )

        # Save as pending proposal
        from core.db import get_conn
        conn = get_conn()
        conn.execute(
            """INSERT INTO proposals
               (job_id, job_title, job_description, client_history,
                budget, skills, screening_questions,
                cover_letter, generated_answers, status, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', CURRENT_TIMESTAMP)""",
            (
                req.job_id,
                req.job_title,
                req.job_description[:5000],
                json.dumps({"name": req.client_name}),
                req.budget,
                json.dumps(req.skills),
                json.dumps([
                    {"question": q.get("question", ""), "required": q.get("required", False)}
                    for q in screening
                ]),
                result.get("cover_letter", ""),
                json.dumps(result.get("screening_answers", {})),
            ),
        )
        conn.commit()
        proposal_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.close()

        return {
            "proposal_id": proposal_id,
            "cover_letter": result.get("cover_letter", ""),
            "screening_answers": result.get("screening_answers", {}),
            "bid_suggestion": result.get("bid_suggestion", ""),
        }
    except Exception as exc:
        logger.error("Proposal generation failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


# ---- Proposal Actions ----

@app.post("/api/proposals/approve")
async def approve_proposal(proposal_id: int):
    """Mark a proposal as approved (ready to submit)."""
    from core.db import get_conn
    conn = get_conn()
    row = conn.execute("SELECT * FROM proposals WHERE id = ?", (proposal_id,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Proposal not found")
    conn.execute("UPDATE proposals SET status = 'approved' WHERE id = ?", (proposal_id,))
    conn.commit()
    conn.close()
    return {"success": True, "proposal_id": proposal_id}


@app.post("/api/proposals/improve")
async def improve_proposal_endpoint(req: ProposalImproveRequest):
    """Regenerate a proposal based on user feedback."""
    try:
        from core.db import get_conn
        conn = get_conn()
        row = conn.execute("SELECT * FROM proposals WHERE id = ?", (req.proposal_id,)).fetchone()
        if not row:
            conn.close()
            raise HTTPException(status_code=404, detail="Proposal not found")

        profile = _get_profile()
        if not profile:
            conn.close()
            raise HTTPException(status_code=400, detail="No profile synced")

        import json
        job_data = {
            "jobId": row["job_id"],
            "title": row["job_title"],
            "description": row["job_description"],
            "budget": row["budget"],
            "skills": json.loads(row["skills"]) if row["skills"] else [],
            "client": json.loads(row["client_history"]) if row["client_history"] else {},
        }

        improved = improve_proposal(
            job=job_data,
            profile=profile,
            current_cover_letter=row["cover_letter"],
            feedback=req.feedback,
        )

        conn.execute(
            "UPDATE proposals SET status = 'improved', improved_cover_letter = ?, feedback = ? WHERE id = ?",
            (improved.get("cover_letter", ""), req.feedback, req.proposal_id),
        )
        conn.commit()
        conn.close()

        return {"success": True, "cover_letter": improved.get("cover_letter", "")}
    except Exception as exc:
        logger.error("Improve proposal failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/proposals/submit")
async def submit_proposal_endpoint(req: ProposalSubmitRequest):
    """Submit an approved proposal to Upwork via available providers."""
    try:
        from core.db import get_conn
        conn = get_conn()
        row = conn.execute("SELECT * FROM proposals WHERE id = ?", (req.proposal_id,)).fetchone()
        if not row:
            conn.close()
            raise HTTPException(status_code=404, detail="Proposal not found")

        if row["status"] != "approved" and row["status"] != "improved":
            conn.close()
            raise HTTPException(status_code=400, detail=f"Proposal status is '{row['status']}' — must be approved or improved first")

        import json
        screening = json.loads(row["generated_answers"]) if row["generated_answers"] else {}
        client_hist = json.loads(row["client_history"]) if row["client_history"] else {}
        skills = json.loads(row["skills"]) if row["skills"] else []

        result = try_submit(
            job_id=row["job_id"],
            job_title=row["job_title"],
            job_description=row["job_description"],
            budget=row["budget"],
            hourly_rate=None,
            skills=skills,
            client_name=client_hist.get("name", ""),
            cover_letter=row["cover_letter"] or row.get("improved_cover_letter", ""),
            screening_answers=screening,
            profile_data=_get_profile(),
        )

        # Update proposal status
        if result.success:
            conn.execute(
                "UPDATE proposals SET status = 'submitted', submitted_at = CURRENT_TIMESTAMP WHERE id = ?",
                (req.proposal_id,),
            )
            logger.info("Proposal %d submitted via %s", req.proposal_id, result.provider)
        else:
            # Mark as failed but keep the data
            logger.warning("Proposal %d submission failed: %s", req.proposal_id, result.error)

        conn.commit()
        conn.close()

        return {
            "success": result.success,
            "provider": result.provider,
            "proposal_url": result.proposal_url,
            "error": result.error,
        }
    except Exception as exc:
        logger.error("Submit proposal failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/proposals/discard")
async def discard_proposal(proposal_id: int):
    """Discard a pending proposal."""
    from core.db import get_conn
    conn = get_conn()
    conn.execute("DELETE FROM proposals WHERE id = ?", (proposal_id,))
    conn.commit()
    conn.close()
    return {"success": True}


# ---- Proposal List ----

@app.get("/api/proposals")
async def list_proposals(status: str | None = None, limit: int = 50, offset: int = 0):
    """List proposals with optional status filter."""
    from core.db import get_conn
    conn = get_conn()
    query = "SELECT * FROM proposals WHERE 1=1"
    params: list = []
    if status:
        query += " AND status = ?"
        params.append(status)
    query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    rows = conn.execute(query, params).fetchall()
    conn.close()
    import json
    return [
        {
            "id": r["id"],
            "job_id": r["job_id"],
            "job_title": r["job_title"],
            "job_description": r["job_description"],
            "budget": r["budget"],
            "skills": json.loads(r["skills"]) if r["skills"] else [],
            "screening_questions": json.loads(r["screening_questions"]) if r["screening_questions"] else [],
            "cover_letter": r["cover_letter"],
            "generated_answers": json.loads(r["generated_answers"]) if r["generated_answers"] else {},
            "status": r["status"],
            "feedback": r["feedback"],
            "improved_cover_letter": r["improved_cover_letter"],
            "submitted_at": r["submitted_at"],
            "created_at": r["created_at"],
        }
        for r in rows
    ]


# ---- Auto-Bidder Settings ----

@app.get("/api/autobid/settings")
async def get_autobid_settings():
    from core.db import get_conn
    conn = get_conn()
    row = conn.execute("SELECT * FROM autobid_settings WHERE id = 1").fetchone()
    conn.close()
    if not row:
        return {}
    import json
    return {
        "min_score": row["min_score"],
        "max_budget_usd": row["max_budget_usd"],
        "skills_filter": json.loads(row["skills_filter"]) if row["skills_filter"] else [],
        "exclude_skills": json.loads(row["exclude_skills"]) if row["exclude_skills"] else [],
        "job_types": json.loads(row["job_types"]) if row["job_types"] else [],
        "locations": json.loads(row["locations"]) if row["locations"] else [],
        "hourly_rate_min": row["hourly_rate_min"],
        "hourly_rate_max": row["hourly_rate_max"],
        "max_proposals_per_day": row["max_proposals_per_day"],
        "new_jobs_only": row["new_jobs_only"],
        "proposal_style": row["proposal_style"],
        "custom_instructions": row["custom_instructions"],
        "running": row["running"],
    }


@app.post("/api/autobid/settings")
async def save_autobid_settings(req: AutobidSettingsRequest):
    from core.db import get_conn
    import json
    conn = get_conn()
    existing = conn.execute("SELECT * FROM autobid_settings WHERE id = 1").fetchone()

    def get_val(field, default):
        return getattr(req, field) if getattr(req, field) is not None else (existing[field] if existing else default)

    conn.execute(
        """INSERT OR REPLACE INTO autobid_settings
           (id, min_score, max_budget_usd, skills_filter, exclude_skills, job_types,
            locations, hourly_rate_min, hourly_rate_max, max_proposals_per_day,
            new_jobs_only, proposal_style, custom_instructions, running, updated_at)
           VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, COALESCE((SELECT running FROM autobid_settings WHERE id=1), 0), CURRENT_TIMESTAMP)""",
        (
            get_val("min_score", 70),
            get_val("max_budget_usd", 5000),
            json.dumps(get_val("skills_filter", [])),
            json.dumps(get_val("exclude_skills", [])),
            json.dumps(get_val("job_types", ["FIXED", "HOURLY"])),
            json.dumps(get_val("locations", [])),
            get_val("hourly_rate_min", 0),
            get_val("hourly_rate_max", 200),
            get_val("max_proposals_per_day", 10),
            get_val("new_jobs_only", True),
            get_val("proposal_style", ""),
            get_val("custom_instructions", ""),
        ),
    )
    conn.commit()
    conn.close()
    return {"success": True}


@app.post("/api/autobid/start")
async def start_autobid():
    """Start the auto-bidder scheduler."""
    global autobidder
    if not autobidder:
        raise HTTPException(status_code=500, detail="Auto-bidder not initialized")

    from core.db import get_conn
    from core.crypto import decrypt
    conn = get_conn()
    # Get Upwork token from credentials before closing
    creds_row = conn.execute("SELECT * FROM creds WHERE id = 1").fetchone()
    token = None
    if creds_row and creds_row["upwork_api_key_encrypted"]:
        token = decrypt(creds_row["upwork_api_key_encrypted"])
    conn.execute("UPDATE autobid_settings SET running = 1 WHERE id = 1")
    conn.commit()
    conn.close()

    if token:
        autobidder.upwork_token = token
        logger.info("Auto-bidder started with Upwork token (len=%d)", len(token))
    else:
        logger.warning("No Upwork API key found — auto-bidder will fail on Upwork API calls")

    autobidder.start()
    return {"success": True, "running": True}


@app.post("/api/autobid/stop")
async def stop_autobid():
    """Stop the auto-bidder scheduler."""
    global autobidder
    if not autobidder:
        raise HTTPException(status_code=500, detail="Auto-bidder not initialized")

    from core.db import get_conn
    conn = get_conn()
    conn.execute("UPDATE autobid_settings SET running = 0 WHERE id = 1")
    conn.commit()
    conn.close()

    autobidder.stop()
    return {"success": True, "running": False}


@app.get("/api/autobid/status")
async def autobid_status():
    global autobidder
    running = autobidder.is_running if autobidder else False

    from core.db import get_conn
    import datetime
    conn = get_conn()
    today = datetime.date.today().isoformat()
    count = conn.execute(
        "SELECT COUNT(*) as cnt FROM proposals WHERE DATE(created_at) = ? AND status IN ('pending','approved','improved','submitted')",
        (today,),
    ).fetchone()["cnt"]
    conn.close()

    return {"running": running, "today_proposals": count}


# ---- Analytics / Dashboard ----

@app.get("/api/analytics/dashboard")
async def analytics_dashboard():
    """Get dashboard stats: today's activity, this week's proposals, etc."""
    from core.db import get_conn
    import json
    import datetime

    conn = get_conn()
    today = date.today().isoformat()
    week_ago = (date.today() - timedelta(days=7)).isoformat()

    dashboard = {}

    # Today's proposals
    row = conn.execute(
        "SELECT COUNT(*) as cnt FROM proposals WHERE DATE(created_at) = ?",
        (today,),
    ).fetchone()
    dashboard["today_proposals"] = row["cnt"] if row else 0

    # Today's submissions
    row = conn.execute(
        "SELECT COUNT(*) as cnt FROM proposals WHERE DATE(submitted_at) = ? AND status = 'submitted'",
        (today,),
    ).fetchone()
    dashboard["today_submitted"] = row["cnt"] if row else 0

    # This week's activity
    row = conn.execute(
        "SELECT COUNT(*) as cnt FROM activity_log WHERE DATE(created_at) >= ?",
        (week_ago,),
    ).fetchone()
    dashboard["week_activity"] = row["cnt"] if row else 0

    # Proposals by status
    rows = conn.execute("SELECT status, COUNT(*) as cnt FROM proposals GROUP BY status").fetchall()
    dashboard["by_status"] = {r["status"]: r["cnt"] for r in rows}

    # Recent activity
    rows = conn.execute(
        "SELECT * FROM activity_log ORDER BY created_at DESC LIMIT 20",
    ).fetchall()
    dashboard["recent_activity"] = [
        {"id": r["id"], "event_type": r["event_type"], "job_id": r["job_id"], "description": r["description"], "created_at": r["created_at"]}
        for r in rows
    ]

    # Auto-bidder running state
    row = conn.execute("SELECT running FROM autobid_settings WHERE id = 1").fetchone()
    dashboard["autobid_running"] = row["running"] if row else False

    conn.close()
    return dashboard


@app.get("/api/analytics/proposals")
async def analytics_proposals(days: int = 30):
    """Get proposal stats over N days."""
    from core.db import get_conn
    import json
    import datetime

    conn = get_conn()
    since = (date.today() - timedelta(days=days)).isoformat()

    rows = conn.execute(
        "SELECT * FROM proposals WHERE DATE(created_at) >= ? ORDER BY created_at DESC",
        (since,),
    ).fetchall()
    conn.close()

    import json
    return [
        {
            "id": r["id"],
            "job_id": r["job_id"],
            "job_title": r["job_title"],
            "status": r["status"],
            "submitted_at": r["submitted_at"],
            "created_at": r["created_at"],
        }
        for r in rows
    ]


# ---- Upwork 직접 읽기 API ----

@app.get("/api/upwork/jobs/search")
async def search_upwork_jobs(
    q: str = "",
    skills: str = "",
    job_type: str = "",
    min_budget: int = 0,
    max_budget: int = 50000,
    page: int = 1,
    limit: int = 25,
):
    """Search Upwork jobs via GraphQL API."""
    try:
        client = _get_upwork_client()
        skills_list = [s.strip() for s in skills.split(",") if s.strip()] if skills else None
        result = client.search_jobs(
            query=q,
            skills=skills_list,
            job_type=job_type or None,
            min_budget=min_budget if min_budget > 0 else None,
            max_budget=max_budget if max_budget > 0 else None,
            page=page,
            limit=limit,
        )
        return result
    except Exception as exc:
        logger.error("Job search failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/upwork/jobs/{job_id}")
async def get_upwork_job(job_id: str):
    try:
        client = _get_upwork_client()
        return client.get_job_details(job_id)
    except Exception as exc:
        logger.error("Get job failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/upwork/proposals")
async def list_upwork_proposals(state: str = ""):
    try:
        client = _get_upwork_client()
        return client.list_proposals(state=state or None)
    except Exception as exc:
        logger.error("List proposals failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/upwork/conversations")
async def list_upwork_conversations():
    try:
        client = _get_upwork_client()
        return client.list_conversations()
    except Exception as exc:
        logger.error("List conversations failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/upwork/messages/{conversation_id}")
async def send_upwork_message(conversation_id: str, body: str):
    try:
        client = _get_upwork_client()
        return client.send_message(conversation_id, body)
    except Exception as exc:
        logger.error("Send message failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/upwork/contracts")
async def list_upwork_contracts():
    try:
        client = _get_upwork_client()
        return client.list_contracts()
    except Exception as exc:
        logger.error("List contracts failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/upwork/stats")
async def get_upwork_stats():
    try:
        client = _get_upwork_client()
        profile = client.get_my_profile()
        stats = client.get_my_stats()
        connects = client.get_connects()
        earnings = client.get_earnings()
        return {
            "profile": profile,
            "stats": stats,
            "connects": connects,
            "earnings": earnings,
        }
    except Exception as exc:
        logger.error("Get stats failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


# ---- Utility ----

@app.get("/api/job-url-parser")
async def parse_job_url(job_url: str):
    """Extract job ID from an Upwork job URL."""
    import re
    match = re.search(r"/jobs/~?(\d+)", job_url)
    if match:
        return {"job_id": match.group(1), "url": job_url}
    return {"job_id": None, "url": job_url, "error": "Could not parse job ID"}


# ---- Main ----

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
