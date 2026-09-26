"""
Auto-bidder scheduler.

Runs as a background process on the VPS. Controlled via the running flag in DB.

Workflow (each scan cycle):
1. Load autobid settings from DB
2. If not running, exit
3. Check today's proposal count vs max_proposals_per_day
4. Search Upwork for matching jobs (new jobs first)
5. For each job:
   a. Skip if already analyzed/queued today (dedup)
   b. Call Claude to score the job (0-100)
   c. If score >= min_score, generate a proposal draft
   d. Save proposal as 'pending' in DB
   e. Log activity
   f. If we hit max_proposals_per_day, stop
6. Sleep for scan interval, repeat

The scheduler does NOT submit proposals automatically. It generates drafts
and saves them as 'pending' for the user to review in the UI.
"""

import asyncio
import datetime
import logging
import threading
from typing import Any

from core.db import get_conn
from services.claude_service import analyze_job, generate_proposal
from services.upwork_client import UpworkGraphQLClient

logger = logging.getLogger(__name__)

TODAY_KEY = "today_proposals_count"
DATE_KEY = "today_date"


class AutoBidder:
    """Auto-bidder engine. Does NOT auto-submit; generates drafts for review."""

    def __init__(self, upwork_token: str):
        self.upwork_token = upwork_token
        self._client: UpworkGraphQLClient | None = None
        self._running = False
        self._thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None

    @property
    def client(self) -> UpworkGraphQLClient:
        if self._client is None:
            self._client = UpworkGraphQLClient(self.upwork_token)
        return self._client

    def start(self):
        """Start the auto-bidder scheduler in a background thread."""
        if self._running:
            return
        self._running = True
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._run_event_loop, daemon=True)
        self._thread.start()
        logger.info("Auto-bidder started")

    def _run_event_loop(self):
        asyncio.set_event_loop(self._loop)
        self._loop.run_until_complete(self._run_loop())

    def stop(self):
        """Stop the auto-bidder scheduler."""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=10)
        self._thread = None
        self._loop = None
        logger.info("Auto-bidder stopped")

    @property
    def is_running(self) -> bool:
        return self._running

    async def _run_loop(self):
        """Main scheduler loop."""
        from core.config import AUTO_BID_SCAN_INTERVAL_SECONDS

        while self._running:
            try:
                await self._scan_cycle()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("Auto-bidder scan cycle error: %s", exc)
                await asyncio.sleep(30)
                continue

            if self._running:
                await asyncio.sleep(AUTO_BID_SCAN_INTERVAL_SECONDS)

    async def _scan_cycle(self):
        """One scan cycle: search, score, generate drafts."""
        from core.config import BASE_DIR
        import json

        conn = get_conn()

        # Load settings
        settings_row = conn.execute("SELECT * FROM autobid_settings WHERE id = 1").fetchone()
        if not settings_row:
            conn.close()
            return

        settings = dict(settings_row)
        if not settings.get("running", False):
            conn.close()
            return

        min_score = settings.get("min_score", 70)
        max_per_day = settings.get("max_proposals_per_day", 10)
        skills_filter = json.loads(settings.get("skills_filter", "[]"))
        exclude_skills = json.loads(settings.get("exclude_skills", "[]"))
        job_types = json.loads(settings.get("job_types", '["FIXED", "HOURLY"]'))
        locations = json.loads(settings.get("locations", "[]"))
        hourly_min = settings.get("hourly_rate_min", 0)
        hourly_max = settings.get("hourly_rate_max", 200)
        new_jobs_only = settings.get("new_jobs_only", True)
        proposal_style = settings.get("proposal_style", "")
        custom_instructions = settings.get("custom_instructions", "")

        # Check daily cap
        today_proposals = self._count_today_proposals(conn)
        if today_proposals >= max_per_day:
            logger.info("Daily proposal cap reached (%d/%d)", today_proposals, max_per_day)
            conn.close()
            return

        remaining_today = max_per_day - today_proposals

        # Load profile
        profile_row = conn.execute("SELECT * FROM profile WHERE id = 1").fetchone()
        profile = json.loads(profile_row["data"]) if profile_row and profile_row["data"] else None

        # Load saved proposals today (for dedup)
        seen_job_ids = self._get_today_proposed_job_ids(conn)

        # Search Upwork
        try:
            search_result = self.client.search_jobs(
                skills=skills_filter if skills_filter else None,
                job_type=None,
                posted_within="7" if new_jobs_only else None,
                page=1,
                limit=remaining_today * 3,  # fetch extra to filter
            )
        except Exception as exc:
            logger.error("Upwork search failed: %s", exc)
            conn.close()
            return

        postings = []
        data = search_result.get("marketplaceJobPostingsSearch", {})
        pager = data.get("paging", {})
        raw_postings = data.get("postings", [])
        for p in raw_postings:
            pid = p.get("jobId")
            if pid and pid not in seen_job_ids:
                postings.append(p)

        logger.info("Scan found %d new candidate jobs (remaining today: %d)", len(postings), remaining_today)

        count = 0
        for job in postings:
            if count >= remaining_today:
                break

            try:
                job_id = job.get("jobId")
                logger.info("Analyzing job %s: %s", job_id, job.get("title", "")[:60])

                # Score the job
                analysis = analyze_job(job, profile)
                score = analysis.get("score", 0)

                # Save analysis
                conn.execute(
                    """INSERT OR REPLACE INTO job_analyzes
                       (job_id, job_url, job_title, job_description, score, grade,
                        match_breakdown, red_flags, tips, analyzed_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
                    (
                        job_id,
                        f"https://www.upwork.com/jobs/{job_id}",
                        job.get("title", ""),
                        (job.get("description") or "")[:5000],
                        score,
                        analysis.get("grade", "F"),
                        json.dumps(analysis.get("match_breakdown", {})),
                        json.dumps(analysis.get("red_flags", [])),
                        json.dumps(analysis.get("tips", [])),
                    ),
                )
                conn.commit()

                # If score passes threshold, generate proposal
                if score >= min_score:
                    proposal_data = generate_proposal(
                        job=job,
                        profile=profile or {},
                        cover_letter_style=proposal_style,
                        custom_instructions=custom_instructions,
                    )

                    cover_letter = proposal_data.get("cover_letter", "")
                    screening_answers = proposal_data.get("screening_answers", {})
                    bid_suggestion = proposal_data.get("bid_suggestion", "")

                    conn.execute(
                        """INSERT INTO proposals
                           (job_id, job_title, job_description, client_history,
                            budget, skills, screening_questions,
                            cover_letter, generated_answers, status, created_at)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', CURRENT_TIMESTAMP)""",
                        (
                            job_id,
                            job.get("title", ""),
                            (job.get("description") or "")[:5000],
                            json.dumps(dict(job.get("client", {}))),
                            job.get("budget") or job.get("hourlyRate") or "",
                            json.dumps(job.get("skills", []) or []),
                            json.dumps([
                                {"question": q.get("question", ""), "required": q.get("required", False)}
                                for q in (job.get("screeningQuestions") or [])
                            ]),
                            cover_letter,
                            json.dumps(screening_answers),
                        ),
                    )
                    conn.commit()

                    self._log_activity(conn, "proposal_drafted", job_id, f"Score {score}, grade {analysis.get('grade')}")

                    count += 1
                    logger.info("Drafted proposal for job %s (score %d)", job_id, score)
                else:
                    self._log_activity(conn, "job_skipped", job_id, f"Score {score} below min {min_score}")

            except Exception as exc:
                logger.error("Error processing job %s: %s", job.get("jobId"), exc)
                continue

        conn.close()
        logger.info("Scan cycle complete: %d proposals drafted", count)

    def _count_today_proposals(self, conn) -> int:
        today = datetime.date.today().isoformat()
        row = conn.execute(
            "SELECT COUNT(*) as cnt FROM proposals WHERE DATE(created_at) = ? AND status IN ('pending', 'approved', 'improved')",
            (today,),
        ).fetchone()
        return row["cnt"] if row else 0

    def _get_today_proposed_job_ids(self, conn) -> set[str]:
        today = datetime.date.today().isoformat()
        rows = conn.execute(
            "SELECT job_id FROM proposals WHERE DATE(created_at) = ?",
            (today,),
        ).fetchall()
        return {r["job_id"] for r in rows}

    def _log_activity(self, conn, event_type: str, job_id: str, description: str):
        conn.execute(
            "INSERT INTO activity_log (event_type, job_id, description, created_at) VALUES (?, ?, ?, CURRENT_TIMESTAMP)",
            (event_type, job_id, description),
        )
        conn.commit()
