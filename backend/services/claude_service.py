"""
Claude API service for job analysis, proposal generation, and profile processing.

Uses Anthropic's Claude (configured via CLAUDE_API_KEY) to:
- Score jobs 0-100 with grade, match breakdown, red flags, tips
- Generate cover letters tailored to job + profile
- Answer screening questions
- Improve existing proposals based on feedback
"""

import json
import logging
from typing import Any

from anthropic import Anthropic

from core.config import CLAUDE_API_KEY, CLAUDE_MODEL, CLAUDE_MAX_TOKENS, CLAUDE_TEMPERATURE

logger = logging.getLogger(__name__)

_client: Anthropic | None = None


def _get_client() -> Anthropic:
    global _client
    if _client is None:
        if not CLAUDE_API_KEY:
            raise RuntimeError("CLAUDE_API_KEY not set")
        _client = Anthropic(api_key=CLAUDE_API_KEY)
    return _client


# ---- Job Analysis (Fit Check) ----

JOB_ANALYSIS_SYSTEM = """
You are an expert Upwork job analyst. You assess whether a freelancer should bid on a job.

You will be given:
- The job posting (title, description, budget, skills, client info)
- The freelancer's profile (title, skills, overview, stats)

Return a JSON object with this exact schema:
{
  "score": <int 0-100>,
  "grade": "<A|B|C|D|F>",
  "match_breakdown": {
    "skill_fit": "<brief description>",
    "budget_fit": "<brief description>",
    "client_quality": "<brief description>",
    "competition": "<brief description>",
    "clarity": "<brief description>"
  },
  "red_flags": ["<flag 1>", "<flag 2>", ...],
  "tips": ["<tip 1>", "<tip 2>", ...],
  "should_bid": <bool>,
  "confidence": "<high|medium|low>"
}

Grading scale:
- A (85-100): Excellent fit, high chance of success, bid immediately
- B (70-84): Good fit, worth pursuing with a strong proposal
- C (55-69): Marginal fit, only bid if you have a unique angle
- D (40-54): Poor fit, probably skip
- F (0-39): Bad fit, definitely skip

Red flags to look for:
- Client has no payment verification
- Very low budget for the scope
- Vague/no description
- "Urgent" / "ASAP" with unrealistic timeline
- No skills listed or contradictory requirements
- Client has 0 jobs posted and 0% hire rate
- Multiple similar postings from same client (spammy)
- Budget too low for the freelancer's rate
- Request for free work / spec work
- "Long-term" but no details about duration or pay

Tips should be actionable suggestions for the proposal.
"""

JOB_ANALYSIS_USER_TEMPLATE = """
Analyze this Upwork job posting for the given freelancer profile.

=== JOB POSTING ===
Title: {job_title}
Budget: {budget}
Hourly Rate: {hourly_rate}
Type: {job_type}
Experience Level: {experience_level}
Skills: {skills}
Posted: {posted_at}
Client: {client_name}
Client Payment Verified: {payment_verified}
Client Rate: {client_rate}
Client Jobs Posted: {jobs_posted}
Client Hire Rate: {hire_rate}
Client Country: {client_country}
Job Description:
{job_description}

=== SCREENING QUESTIONS ===
{screening_questions}

=== FREELANCER PROFILE ===
Title: {profile_title}
Skills: {profile_skills}
Overview: {profile_overview}
JSS Score: {profile_jss}
Total Earned: {profile_earned}
Jobs Hired: {profile_jobs_hired}

Return ONLY valid JSON matching the schema. No extra text.
"""


def analyze_job(
    job: dict[str, Any],
    profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Score a job posting 0-100 and return analysis."""
    client = job.get("client", {})
    screening = job.get("screeningQuestions", [])

    screening_text = ""
    if screening:
        screening_text = "\n".join(
            f"Q: {q.get('question', '')}\nRequired: {q.get('required', False)}"
            for q in screening
        )
    else:
        screening_text = "None"

    budget = job.get("budget") or ""
    hourly = job.get("hourlyRate") or ""
    if hourly and not budget:
        budget = f"Hourly: {hourly}"
    elif hourly:
        budget = f"{budget} (Hourly: {hourly})"

    user_prompt = JOB_ANALYSIS_USER_TEMPLATE.format(
        job_title=job.get("title", "N/A"),
        budget=budget,
        hourly_rate=job.get("hourlyRate") or "N/A",
        job_type=job.get("jobType") or "N/A",
        experience_level=job.get("experienceLevel") or "N/A",
        skills=", ".join(job.get("skills", []) or []),
        posted_at=job.get("postedAt") or "N/A",
        client_name=client.get("name", "N/A"),
        payment_verified=client.get("paymentVerified", "unknown"),
        client_rate=client.get("rate") or "N/A",
        jobs_posted=client.get("jobsPosted") or "N/A",
        hire_rate=client.get("hireRate") or "N/A",
        client_country=client.get("country") or "N/A",
        job_description=job.get("description", "")[:6000],
        screening_questions=screening_text,
        profile_title=profile.get("title", "N/A") if profile else "N/A",
        profile_skills=", ".join(profile.get("skills", []) or []) if profile else "N/A",
        profile_overview=(profile.get("overview") or "")[:2000] if profile else "N/A",
        profile_jss=profile.get("jkScore") if profile else "N/A",
        profile_earned=profile.get("totalEarned") or "N/A" if profile else "N/A",
        profile_jobs_hired=profile.get("jobsHiredCount") if profile else "N/A",
    )

    messages = [
        {"role": "system", "content": JOB_ANALYSIS_SYSTEM},
        {"role": "user", "content": user_prompt},
    ]

    resp = _get_client().messages.create(
        model=CLAUDE_MODEL,
        max_tokens=CLAUDE_MAX_TOKENS,
        temperature=CLAUDE_TEMPERATURE,
        system=JOB_ANALYSIS_SYSTEM,
        messages=[{"role": "user", "content": user_prompt}],
    )

    try:
        text = resp.content[0].text
        # Try to extract JSON from the response
        return _parse_json_from_text(text)
    except Exception as exc:
        logger.error("Failed to parse job analysis: %s", exc)
        return {
            "score": 0,
            "grade": "F",
            "match_breakdown": {},
            "red_flags": [f"Analysis error: {exc}"],
            "tips": ["Retry the analysis"],
            "should_bid": False,
            "confidence": "low",
        }


# ---- Proposal Generation ----

PROPOSAL_SYSTEM = """
You are an expert Upwork proposal writer. You write winning, personalized proposals
that sound like the freelancer and address the client's actual needs.

Rules:
- Address the client by name if known
- Reference specifics from the job description
- Match the freelancer's tone and experience level
- Keep it concise (150-300 words typically)
- Include a clear call to action at the end
- Never sound generic or templated
- Address screening questions separately
- Highlight relevant past work that matches THIS job
"""


def generate_proposal(
    job: dict[str, Any],
    profile: dict[str, Any],
    cover_letter_style: str | None = None,
    custom_instructions: str | None = None,
) -> dict[str, Any]:
    """Generate a cover letter + screening answers for a job."""
    client = job.get("client", {})
    screening = job.get("screeningQuestions", [])
    budget = job.get("budget") or ""
    hourly = job.get("hourlyRate") or ""

    screening_section = ""
    if screening:
        screening_section = "\n".join(
            f"- {q.get('question', '')}"
            for q in screening
        )

    user_prompt = f"""
=== JOB ===
Title: {job.get('title', 'N/A')}
Budget: {budget}
Hourly: {hourly}
Type: {job.get('jobType', 'N/A')}
Skills: {', '.join(job.get('skills', []) or [])}
Client: {client.get('name', 'N/A')}
Description:
{job.get('description', '')[:5000]}

=== SCREENING QUESTIONS ({len(screening)}) ===
{screening_section or 'None'}

=== YOUR PROFILE ===
Title: {profile.get('title', 'N/A')}
Skills: {', '.join(profile.get('skills', []) or [])}
Overview:
{(profile.get('overview') or '')[:3000]}
Experience: {profile.get('totalEarned', 'N/A')} earned, {profile.get('jobsHiredCount', 0)} jobs hired, JSS: {profile.get('jkScore', 'N/A')}

=== STYLE / INSTRUCTIONS ===
Cover Letter Style: {cover_letter_style or 'Professional, direct, confident'}
Custom Instructions: {custom_instructions or 'None'}

Generate:
1. cover_letter: A personalized proposal cover letter (150-350 words)
2. screening_answers: A JSON object mapping each screening question to a concise answer
3. bid_suggestion: Suggested bid (either hourly rate or fixed price suggestion based on budget)

Return as JSON:
{{
  "cover_letter": "...",
  "screening_answers": {{"question": "answer", ...}},
  "bid_suggestion": "..."
}}
"""

    resp = _get_client().messages.create(
        model=CLAUDE_MODEL,
        max_tokens=CLAUDE_MAX_TOKENS,
        temperature=0.7,
        system=PROPOSAL_SYSTEM,
        messages=[{"role": "user", "content": user_prompt}],
    )

    try:
        return _parse_json_from_text(resp.content[0].text)
    except Exception as exc:
        logger.error("Failed to parse proposal: %s", exc)
        return {
            "cover_letter": f"[Proposal generation failed: {exc}]",
            "screening_answers": {},
            "bid_suggestion": "N/A",
        }


def improve_proposal(
    job: dict[str, Any],
    profile: dict[str, Any],
    current_cover_letter: str,
    feedback: str,
) -> dict[str, Any]:
    """Regenerate a proposal based on user feedback."""
    user_prompt = f"""
=== JOB ===
Title: {job.get('title', 'N/A')}
Description:
{job.get('description', '')[:4000]}

=== YOUR PROFILE ===
Profile: {profile.get('title', 'N/A')}
Skills: {', '.join(profile.get('skills', []) or [])}

=== CURRENT COVER LETTER ===
{current_cover_letter}

=== USER FEEDBACK ===
{feedback}

Rewrite the cover letter addressing this feedback. Keep the same structure and tone
but improve based on what the user asked for. Return JSON:
{{
  "cover_letter": "..."
}}
"""

    resp = _get_client().messages.create(
        model=CLAUDE_MODEL,
        max_tokens=CLAUDE_MAX_TOKENS,
        temperature=0.7,
        system=PROPOSAL_SYSTEM,
        messages=[{"role": "user", "content": user_prompt}],
    )

    try:
        parsed = _parse_json_from_text(resp.content[0].text)
        return {"cover_letter": parsed.get("cover_letter", resp.content[0].text)}
    except Exception as exc:
        logger.error("Failed to parse improved proposal: %s", exc)
        return {"cover_letter": resp.content[0].text}


# ---- Profile Processing ----

def process_profile(raw_profile: dict[str, Any]) -> dict[str, Any]:
    """Clean up and enrich a raw profile from the API."""
    return {
        "id": raw_profile.get("id"),
        "firstname": raw_profile.get("firstname", ""),
        "lastname": raw_profile.get("lastname", ""),
        "title": raw_profile.get("title", ""),
        "overview": raw_profile.get("overview", ""),
        "skills": raw_profile.get("skills", []),
        "total_earned": raw_profile.get("totalEarned", "0"),
        "jk_score": raw_profile.get("jkScore"),
        "jobs_count": raw_profile.get("jobsCount", 0),
        "jobs_hired_count": raw_profile.get("jobsHiredCount", 0),
        "region": raw_profile.get("region", ""),
        "portfolio_url": raw_profile.get("portofolioUrl") or raw_profile.get("portfolioUrl", ""),
        "raw": raw_profile,
    }


# ---- Helpers ----

def _parse_json_from_text(text: str) -> dict[str, Any]:
    """Extract a JSON object from a Claude text response.

    Handles cases where Claude wraps JSON in markdown fences or adds preamble.
    """
    text = text.strip()

    # Strip markdown fences
    if text.startswith("```"):
        # Find the closing fence
        lines = text.split("\n")
        json_lines = []
        in_code = False
        for line in lines:
            if line.strip().startswith("```"):
                if in_code:
                    break
                in_code = True
                continue
            if in_code:
                json_lines.append(line)
        text = "\n".join(json_lines)

    # Try parsing directly
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try to find JSON object boundaries
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            pass

    # Try stripping common preamble
    for marker in ["Here is the JSON:", "Sure, here", "Here's", "Results:", "```json"]:
        idx = text.find(marker)
        if idx >= 0:
            try:
                return json.loads(text[idx:].strip())
            except json.JSONDecodeError:
                continue

    raise ValueError(f"Could not parse JSON from response: {text[:200]}")
