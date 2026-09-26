"""
Composio submission provider (optional).

Requires:
- COMPOSIO_API_KEY env var
- A Composio connected account for Upwork (set up via Composio dashboard)
- The Composio Upwork toolkit must expose a proposal submission action

This provider tries to use Composio's tool execution API to submit proposals.
If Composio's Upwork toolkit doesn't have a submit action, this provider
reports unhealthy and the Playwright provider is used instead.

The provider is pluggable — swap or add providers without changing the autobidder.
"""

import json
import logging
from typing import Any

import httpx

from core.config import COMPOSIO_API_KEY, COMPOSIO_BASE_URL
from services.submission_providers import BaseSubmissionProvider, SubmissionResult

logger = logging.getLogger(__name__)


class ComposioProvider(BaseSubmissionProvider):
    """Submit proposals via Composio's tool execution API."""

    def __init__(self):
        self._toolkit_slug = "upwork"
        self._toolkit_version = "latest"
        self._connected_account_id: str | None = None
        self._submit_tool_slug: str | None = None
        self._healthy = False
        self._discovered = False

    def name(self) -> str:
        return "composio"

    def health_check(self) -> bool:
        if not COMPOSIO_API_KEY:
            logger.info("Composio provider: COMPOSIO_API_KEY not set")
            return False
        if self._discovered:
            return self._healthy
        # Try to discover tools
        self._discover_tools()
        return self._healthy

    def _discover_tools(self):
        """Query Composio for Upwork tools to find a submit action."""
        if self._discovered:
            return
        self._discovered = True

        try:
            # List tools for the upwork toolkit
            url = f"{COMPOSIO_BASE_URL}/tools"
            headers = {"x-api-key": COMPOSIO_API_KEY}
            params = {
                "toolkit_slug": self._toolkit_slug,
                "toolkit_versions": "latest",
                "limit": 500,
            }

            resp = httpx.get(url, headers=headers, params=params, timeout=30.0)
            if resp.status_code == 200:
                data = resp.json()
                items = data.get("items", [])
                logger.info("Composio found %d Upwork tools", len(items))

                for tool in items:
                    slug = tool.get("slug", "").upper()
                    # Look for submit / apply / proposal actions
                    if any(kw in slug for kw in ["SUBMIT", "PROPOSAL", "APPLY", "BID"]):
                        logger.info("Composio Upwork tool candidate: %s (%s)", slug, tool.get("name"))
                        if "SUBMIT" in slug and "PROPOSAL" in slug:
                            self._submit_tool_slug = slug
                            break

                # Also check for connected accounts
                if not self._submit_tool_slug:
                    # Maybe the tool has a different naming; list all and pick write tools
                    for tool in items:
                        slug = tool.get("slug", "").upper()
                        if "PROPOSAL" in slug or "BID" in slug:
                            self._submit_tool_slug = slug
                            break

                if self._submit_tool_slug:
                    # Find connected account for upwork
                    self._find_connected_account(items)
                    self._healthy = True
                    logger.info("Composio provider healthy: tool=%s", self._submit_tool_slug)
                else:
                    logger.warning("Composio: No proposal submit tool found in Upwork toolkit")
                    self._healthy = False
            else:
                logger.warning("Composio API returned %s: %s", resp.status_code, resp.text[:200])
                self._healthy = False
        except Exception as exc:
            logger.warning("Composio discovery failed: %s", exc)
            self._healthy = False

    def _find_connected_account(self, tools: list):
        """Find a connected Upwork account in Composio."""
        try:
            url = f"{COMPOSIO_BASE_URL}/connected_accounts"
            headers = {"x-api-key": COMPOSIO_API_KEY}
            params = {"toolkit_slug": self._toolkit_slug, "limit": 50}
            resp = httpx.get(url, headers=headers, params=params, timeout=30.0)
            if resp.status_code == 200:
                data = resp.json()
                items = data.get("items", [])
                for ac in items:
                    if ac.get("toolkit", {}).get("slug") == self._toolkit_slug:
                        self._connected_account_id = ac.get("id")
                        logger.info("Composio connected account: %s", self._connected_account_id)
                        break
        except Exception as exc:
            logger.warning("Composio connected account lookup failed: %s", exc)

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
        """Submit via Composio tool execution API."""
        if not self._submit_tool_slug:
            return SubmissionResult(
                success=False,
                error="Composio: submit tool not discovered",
                provider=self.name(),
            )
        if not self._connected_account_id:
            return SubmissionResult(
                success=False,
                error="Composio: no connected Upwork account",
                provider=self.name(),
            )

        try:
            # Build arguments for the Composio tool
            # The exact args depend on the tool's schema — we try a reasonable shape
            args = {
                "job_id": job_id,
                "cover_letter": cover_letter,
                "bid_amount": hourly_rate or budget,
            }
            if screening_answers:
                args["screening_answers"] = screening_answers

            url = f"{COMPOSIO_BASE_URL}/tools/execute/{self._submit_tool_slug}"
            headers = {
                "x-api-key": COMPOSIO_API_KEY,
                "Content-Type": "application/json",
            }
            body = {
                "arguments": args,
                "connected_account_id": self._connected_account_id,
                "toolkit_versions": {"upwork": "latest"},
            }

            resp = httpx.post(url, headers=headers, json=body, timeout=60.0)
            if resp.status_code == 200:
                data = resp.json()
                logger.info("Composio submit response: %s", json.dumps(data, default=str)[:500])
                # Interpret response
                success = data.get("success", False)
                if success:
                    result_data = data.get("data", {})
                    return SubmissionResult(
                        success=True,
                        proposal_url=result_data.get("proposal_url") or result_data.get("url") or "",
                        provider=self.name(),
                    )
                else:
                    error = data.get("error", data.get("message", "Unknown Composio error"))
                    return SubmissionResult(
                        success=False,
                        error=f"Composio: {error}",
                        provider=self.name(),
                    )
            else:
                return SubmissionResult(
                    success=False,
                    error=f"Composio API: {resp.status_code} {resp.text[:200]}",
                    provider=self.name(),
                )
        except Exception as exc:
            logger.error("Composio submit failed: %s", exc)
            return SubmissionResult(
                success=False,
                error=f"Composio error: {exc}",
                provider=self.name(),
            )


def register_composio_provider() -> ComposioProvider | None:
    """Register the Composio provider if API key is configured."""
    if COMPOSIO_API_KEY:
        provider = ComposioProvider()
        from services.submission_providers import register_provider
        register_provider(provider)
        logger.info("Composio provider registered (health: %s)", provider.health_check())
        return provider
    return None
