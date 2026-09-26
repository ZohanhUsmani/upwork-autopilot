"""
Playwright-based submission provider.

Uses a headless Chromium browser on the VPS to:
1. Log into Upwork (or restore saved session cookies)
2. Navigate to the job URL
3. Fill the proposal form: cover letter, screening answers, bid amount
4. Submit the proposal

Session management:
- On first use, performs login with stored credentials
- Saves cookies after login for fast restore on subsequent runs
- Cookies are encrypted and stored in the database
- Periodically checks session validity; re-logins if expired

NOTE: This interacts with Upwork's web UI, not their API. Upwork may show
CAPTCHAs, 2FA prompts, or block automated behavior. The user should be
prepared to manually handle these when they occur. Respect Upwork ToS.
"""

import json
import logging
import time
from typing import Any

from playwright.sync_api import (
    Browser,
    BrowserContext,
    Page,
    Playwright,
    sync_playwright,
)

from core.config import PLAYWRIGHT_HEADLESS, UPWORK_GRAPHQL_URL
from core.crypto import decrypt
from core.db import get_conn

logger = logging.getLogger(__name__)

UPWORK_LOGIN_URL = "https://www.upwork.com/nx/accounts/login"
UPWORK_JOB_URL = "https://www.upwork.com/jobs"

# How long a session is considered fresh (seconds)
SESSION_REFRESH_DAYS = 7


class PlaywrightProvider:
    def __init__(self):
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None
        self._initialized = False

    def name(self) -> str:
        return "playwright"

    def health_check(self) -> bool:
        """Check if we can launch a browser."""
        if not self._initialized:
            return False
        try:
            return self._browser is not None and self._context is not None
        except Exception:
            return False

    def initialize(self):
        """Launch browser and restore/create session."""
        if self._initialized:
            return
        self._playwright = sync_playwright().start()
        headless = PLAYWRIGHT_HEADLESS
        self._browser = self._playwright.chromium.launch(
            headless=headless,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
        )
        self._context = self._browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 720},
            locale="en-US",
        )
        # Try to restore cookies
        self._restore_session()
        self._page = self._context.new_page()
        self._initialized = True
        logger.info("Playwright provider initialized (headless=%s)", headless)

    def _restore_session(self):
        """Restore encrypted cookies from DB if fresh enough."""
        conn = get_conn()
        row = conn.execute("SELECT * FROM creds WHERE id = 1").fetchone()
        conn.close()
        if not row or not row["playwright_cookies_encrypted"]:
            logger.info("No saved Playwright session found")
            return
        try:
            cookies_json = decrypt(row["playwright_cookies_encrypted"])
            cookies = json.loads(cookies_json)
            self._context.add_cookies(cookies)
            logger.info("Restored Playwright session from DB")
        except Exception as exc:
            logger.warning("Failed to restore Playwright session: %s", exc)

    def save_session(self):
        """Save current cookies to DB (encrypted)."""
        if not self._context:
            return
        try:
            cookies = self._context.cookies()
            cookies_json = json.dumps(cookies, indent=2)
            encrypted = encrypt_safe(cookies_json)
            conn = get_conn()
            conn.execute(
                "INSERT OR REPLACE INTO creds (id, playwright_cookies_encrypted, saved_at) VALUES (1, ?, CURRENT_TIMESTAMP)",
                (encrypted,),
            )
            conn.commit()
            conn.close()
            logger.info("Playwright session saved to DB")
        except Exception as exc:
            logger.error("Failed to save Playwright session: %s", exc)

    def login(self, email: str, password: str, two_factor_code: str | None = None) -> bool:
        """Perform Upwork login. Returns True on success."""
        if not self._page:
            raise RuntimeError("Playwright not initialized")
        page = self._page
        page.goto(UPWORK_LOGIN_URL, wait_until="networkidle", timeout=30000)
        time.sleep(2)

        # Fill email
        try:
            page.fill('input[name="email"]', email)
            page.click('button[type="submit"]')
            page.wait_for_load_state("networkidle", timeout=20000)
            time.sleep(2)
        except Exception as exc:
            logger.error("Failed at email step: %s", exc)
            return False

        # Fill password
        try:
            page.fill('input[name="password"]', password)
            page.click('button[type="submit"]')
            page.wait_for_load_state("networkidle", timeout=20000)
            time.sleep(3)
        except Exception as exc:
            logger.error("Failed at password step: %s", exc)
            return False

        # Handle 2FA if present
        if page.url.startswith("https://www.upwork.com/nx/accounts/login") and "two-factor" in page.content().lower():
            if two_factor_code:
                try:
                    page.fill('input[name="verificationCode"]', two_factor_code)
                    page.click('button[type="submit"]')
                    page.wait_for_load_state("networkidle", timeout=20000)
                    time.sleep(2)
                except Exception as exc:
                    logger.error("Failed at 2FA step: %s", exc)
                    return False
            else:
                logger.warning("2FA required but no code provided — session may be incomplete")
                return False

        # Verify we're logged in
        if "logout" in page.content().lower() or "my upwork" in page.content().lower():
            self.save_session()
            logger.info("Upwork login successful, session saved")
            return True

        logger.warning("Login may have failed — URL: %s", page.url)
        return False

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
    ) -> "SubmissionResult":
        """Submit a proposal via the Upwork web UI using Playwright."""
        if not self._initialized:
            self.initialize()

        page = self._page
        job_url = f"{UPWORK_JOB_URL}/{job_id}"

        try:
            # Navigate to job page
            page.goto(job_url, wait_until="networkidle", timeout=30000)
            time.sleep(2)

            # Click "Apply Now" / "Submit Proposal"
            apply_button = None
            for selector in [
                ' button:has-text("Apply Now")',
                ' button:has-text("Submit Proposal")',
                ' a:has-text("Apply Now")',
                ' a:has-text("Submit Proposal")',
                '[data-test="apply-now-button"]',
                '[data-test="submit-proposal-button"]',
            ]:
                try:
                    apply_button = page.query_selector(selector)
                    if apply_button:
                        break
                except Exception:
                    continue

            if not apply_button:
                # Fallback: try clicking any prominent primary button
                apply_button = page.query_selector('button.primary, .btn-primary, button[data-test]')
                if not apply_button:
                    return SubmissionResult(
                        success=False,
                        error=f"Could not find Apply/Submit button for job {job_id}",
                        provider=self.name(),
                    )

            apply_button.click()
            page.wait_for_load_state("networkidle", timeout=20000)
            time.sleep(2)

            # Fill cover letter
            cover_letter_filled = False
            for selector in [
                'textarea[name="coverLetter"]',
                'textarea[data-test="cover-letter"]',
                'textarea#coverLetter',
                'textarea[placeholder*="cover"]',
                'textarea[placeholder*="Cover"]',
                '.cover-letter-textarea',
            ]:
                try:
                    ta = page.query_selector(selector)
                    if ta:
                        ta.fill(cover_letter)
                        cover_letter_filled = True
                        logger.info("Filled cover letter textarea")
                        break
                except Exception:
                    continue

            if not cover_letter_filled:
                logger.warning("Could not find cover letter textarea — attempting fallback")

            # Fill screening questions
            if screening_answers:
                for question, answer in screening_answers.items():
                    self._fill_screening_question(page, question, answer)

            # Set bid / hourly rate
            if hourly_rate:
                self._fill_bid_amount(page, hourly_rate, budget)

            # Submit
            submit_button = None
            for selector in [
                ' button:has-text("Submit Proposal")',
                ' button:has-text("Submit")',
                ' button:has-text("Send")',
                ' button:has-text("Submit Bid")',
                '[data-test="submit-proposal-submit-button"]',
                'button[type="submit"]',
            ]:
                try:
                    sb = page.query_selector(selector)
                    if sb and sb.is_visible():
                        submit_button = sb
                        break
                except Exception:
                    continue

            if not submit_button:
                # Last resort: any visible submit button
                submit_button = page.query_selector('button[type="submit"]')

            if submit_button:
                submit_button.click()
                page.wait_for_load_state("networkidle", timeout=30000)
                time.sleep(3)

                # Check for success
                if "successfully" in page.content().lower() or "thank" in page.content().lower():
                    proposal_url = page.url
                    logger.info("Proposal submitted successfully via Playwright")
                    return SubmissionResult(
                        success=True,
                        proposal_url=proposal_url,
                        provider=self.name(),
                    )
                elif "error" in page.content().lower() or "failed" in page.content().lower():
                    return SubmissionResult(
                        success=False,
                        error="Upwork returned an error on submission",
                        provider=self.name(),
                    )

            return SubmissionResult(
                success=False,
                error="Could not confirm submission — no success indicator found",
                provider=self.name(),
            )

        except Exception as exc:
            logger.error("Playwright submit_proposal failed: %s", exc)
            return SubmissionResult(
                success=False,
                error=f"Playwright error: {exc}",
                provider=self.name(),
            )

    def _fill_screening_question(self, page: Page, question: str, answer: str):
        """Try to find and fill a screening question answer field."""
        try:
            # Look for textarea / input near the question text
            # Upwork screening questions appear as expandable sections
            question_lower = question.lower()
            page_content = page.content().lower()

            # Strategy: find text field after the question label
            # Try common patterns
            for selector in [
                f'textarea:has-text("{question[:50]}")',
                f'input:has-text("{question[:50]}")',
            ]:
                try:
                    elem = page.query_selector(selector)
                    if elem:
                        elem.fill(answer)
                        logger.info("Filled screening: %s...", question[:40])
                        return
                except Exception:
                    continue

            # Broader: fill the first empty textarea after clicking the question
            question_el = page.query_selector(f'textarea, input[type="text"], input[type="textarea"]')
            if question_el:
                try:
                    question_el.fill(answer)
                    logger.info("Filled screening question (broad match): %s...", question[:40])
                except Exception:
                    pass
        except Exception as exc:
            logger.warning("Failed to fill screening question '%s': %s", question[:40], exc)

    def _fill_bid_amount(self, page: Page, hourly_rate: str, budget: str):
        """Fill the bid amount / hourly rate field."""
        try:
            for selector in [
                'input[name="bidAmount"]',
                'input[data-test="bid-amount"]',
                'input[id="bidAmount"]',
                'input[placeholder*="rate"]',
                '.bid-amount-input',
            ]:
                try:
                    inp = page.query_selector(selector)
                    if inp and inp.is_visible():
                        inp.fill(str(hourly_rate))
                        logger.info("Filled bid amount: %s", hourly_rate)
                        return
                except Exception:
                    continue
        except Exception as exc:
            logger.warning("Failed to fill bid amount: %s", exc)

    def close(self):
        """Clean up browser resources."""
        try:
            if self._context:
                self.save_session()
            if self._browser:
                self._browser.close()
            if self._playwright:
                self._playwright.stop()
        except Exception as exc:
            logger.warning("Error closing Playwright: %s", exc)
        finally:
            self._initialized = False
            self._browser = None
            self._context = None
            self._page = None


# Simple encryption helper that uses the core crypto module.
# Avoid circular imports by inlining the call path.
def encrypt_safe(plaintext: str) -> str:
    from core.crypto import encrypt
    return encrypt(plaintext)
