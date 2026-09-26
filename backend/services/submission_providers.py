"""
Submission providers for applying to Upwork jobs.

Abstraction: each provider implements submit_proposal(job_details, cover_letter, answers)
and returns a result dict with {success, proposal_url, error, provider}.

Providers:
  - playwright: headless browser on the VPS (always available, primary)
  - composio:  Composio Upwork toolkit (optional, set COMPOSIO_API_KEY + connected account)

The autobidder tries providers in order: composio first (if configured), then playwright.
"""

from abc import ABC, abstractmethod
from typing import Any


class SubmissionResult:
    def __init__(self, success: bool, proposal_url: str | None = None, error: str | None = None, provider: str = ""):
        self.success = success
        self.proposal_url = proposal_url
        self.error = error
        self.provider = provider

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "proposal_url": self.proposal_url,
            "error": self.error,
            "provider": self.provider,
        }


class BaseSubmissionProvider(ABC):
    """Abstract submission provider."""

    @abstractmethod
    def name(self) -> str:
        """Provider identifier."""
        ...

    @abstractmethod
    def health_check(self) -> bool:
        """Is this provider ready to submit?"""
        ...

    @abstractmethod
    def submit_proposal(
        self,
        job_id: str,
        job_title: str,
        job_description: str,
        budget: str,
        hourly_rate: str | None,
        skills: list[str],
        client_name: str,
        cover_letter: str,
        screening_answers: dict[str, str] | None,
        profile_data: dict[str, Any] | None,
    ) -> SubmissionResult:
        """Submit a proposal to an Upwork job.

        Args:
            job_id: Upwork job ID
            job_title: Job title
            job_description: Full job description
            budget: Budget string (e.g. "$500-$1000", "Fixed", hourly range)
            hourly_rate: Proposed hourly rate or None for fixed
            skills: Skills required
            client_name: Client display name
            cover_letter: The proposal cover letter text
            screening_answers: Dict of question->answer for screening questions
            profile_data: User's profile data (for context)
        """
        ...


# Registry
_providers: list[BaseSubmissionProvider] = []


def register_provider(provider: BaseSubmissionProvider):
    _providers.append(provider)


def get_providers() -> list[BaseSubmissionProvider]:
    return list(_providers)


def get_healthy_providers() -> list[BaseSubmissionProvider]:
    return [p for p in _providers if p.health_check()]


def try_submit(
    job_id: str,
    job_title: str,
    job_description: str,
    budget: str,
    hourly_rate: str | None,
    skills: list[str],
    client_name: str,
    cover_letter: str,
    screening_answers: dict[str, str] | None,
    profile_data: dict[str, Any] | None,
) -> SubmissionResult:
    """Try each healthy provider in order until one succeeds."""
    for provider in get_healthy_providers():
        try:
            result = provider.submit_proposal(
                job_id=job_id,
                job_title=job_title,
                job_description=job_description,
                budget=budget,
                hourly_rate=hourly_rate,
                skills=skills,
                client_name=client_name,
                cover_letter=cover_letter,
                screening_answers=screening_answers,
                profile_data=profile_data,
            )
            if result.success:
                return result
        except Exception as exc:
            # Log and try next provider
            continue
    return SubmissionResult(
        success=False,
        error="All submission providers failed",
        provider="none",
    )
