import json
from typing import Any

import httpx

from core.config import UPWORK_GRAPHQL_URL, UPWORK_API_KEY


class UpworkGraphQLClient:
    """Read-only Upwork GraphQL API client.

    Uses OAuth2 bearer token (UPWORK_API_KEY env = access token).
    Covers: job search, job details, profile, proposals, messages, contracts.
    """

    def __init__(self, access_token: str | None = None):
        self._token = access_token or UPWORK_API_KEY
        self._client = httpx.Client(
            base_url=UPWORK_GRAPHQL_URL,
            timeout=30.0,
            headers={
                "Authorization": f"Bearer {self._token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )

    def raw(self, query: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
        resp = self._client.post(
            "",
            json={"query": query, "variables": variables or {}},
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("errors"):
            raise RuntimeError(f"Upwork GraphQL error: {data['errors']}")
        return data.get("data", {})

    # ---- Job Search ----
    def search_jobs(
        self,
        query: str = "",
        skills: list[str] | None = None,
        job_type: str | None = None,
        min_budget: int | None = None,
        max_budget: int | None = None,
        experience_level: str | None = None,
        location: str | None = None,
        posted_within: str | None = None,  # e.g. "3", "7", "14" days
        page: int = 1,
        limit: int = 25,
    ) -> dict[str, Any]:
        """Search marketplace job postings.

        Returns pager with job postings matching filters.
        """
        # Build filter JSON
        filter_obj: dict[str, Any] = {}
        if query:
            filter_obj["q"] = query
        if skills:
            filter_obj["skills"] = skills
        if job_type:
            filter_obj["jobType"] = job_type
        if min_budget is not None or max_budget is not None:
            filter_obj["budget"] = {}
            if min_budget is not None:
                filter_obj["budget"]["min"] = min_budget
            if max_budget is not None:
                filter_obj["budget"]["max"] = max_budget
        if experience_level:
            filter_obj["experienceLevel"] = experience_level
        if location:
            filter_obj["location"] = location

        query_str = """
        query MarketplaceJobPostingsSearch(
            $filter: MarketplaceJobPostingsSearchFilterInput,
            $paging: PagingInput
        ) {
            marketplaceJobPostingsSearch(filter: $filter, paging: $paging) {
                paging {
                    total
                    page
                    pageSize
                }
                postings {
                    jobId
                    title
                    description
                    budget
                    hourlyRate
                    category
                    skills
                    experienceLevel
                    jobType
                    client {
                        name
                        paymentVerified
                        rate
                        jobsPosted
                        hireRate
                        country
                    }
                    postedAt
                    url
                    screeningQuestions {
                        question
                        required
                    }
                }
            }
        }
        """
        return self.raw(
            query_str,
            {
                "filter": filter_obj,
                "paging": {"page": page, "pageSize": limit},
            },
        )

    def get_job_details(self, job_id: str) -> dict[str, Any]:
        """Get full details of a single job posting."""
        query_str = """
        query JobPostingLookup($jobId: String!) {
            jobPostingLookup(jobId: $jobId) {
                jobId
                title
                description
                budget
                hourlyRate
                category
                skills
                experienceLevel
                jobType
                client {
                    name
                    paymentVerified
                    rate
                    jobsPosted
                    hireRate
                    country
                    feedback
                }
                postedAt
                url
                screeningQuestions {
                    question
                    required
                }
                proposalCount
                filled
            }
        }
        """
        return self.raw(query_str, {"jobId": job_id})

    # ---- Profile ----
    def get_my_profile(self) -> dict[str, Any]:
        """Get the authenticated freelancer's profile."""
        query_str = """
        query FreelancerProfile {
            freelancerProfile {
                id
                firstname
                lastname
                title
                overview
                skills
                totalEarned
                jkScore
                jobsCount
                jobsHiredCount
                region
                portofolioUrl
                earning
            }
        }
        """
        return self.raw(query_str)

    def get_my_stats(self) -> dict[str, Any]:
        """Get profile stats: JSS, connects balance, earnings."""
        query_str = """
        query FreelancerStats {
            freelancerStats {
                jkScore
                connectsBalance
                availableConnects
                earnedAmount
                earningsHistory {
                    totalEarned
                    period
                }
            }
        }
        """
        return self.raw(query_str)

    # ---- Proposals ----
    def list_proposals(
        self,
        state: str | None = None,
        page: int = 1,
        limit: int = 25,
    ) -> dict[str, Any]:
        """List freelancer's proposals (submitted, in review, etc.)"""
        query_str = """
        query FreelancerProposals(
            $state: ContractProposalStateV2,
            $paging: PagingInput
        ) {
            freelancerProposals(state: $state, paging: $paging) {
                paging { total page pageSize }
                contracts {
                    proposalId
                    jobId
                    jobTitle
                    jobDescription
                    clientName
                    budget
                    hourlyRate
                    status
                    submittedAt
                    url
                }
            }
        }
        """
        return self.raw(query_str, {"state": state, "paging": {"page": page, "pageSize": limit}})

    def get_proposal(self, proposal_id: str) -> dict[str, Any]:
        query_str = """
        query ProposalDetails($proposalId: String!) {
            proposalDetails(proposalId: $proposalId) {
                proposalId
                jobId
                jobTitle
                coverLetter
                status
                submittedAt
                clientName
                budget
            }
        }
        """
        return self.raw(query_str, {"proposalId": proposal_id})

    # ---- Messages ----
    def list_conversations(self, page: int = 1, limit: int = 25) -> dict[str, Any]:
        query_str = """
        query Conversations($paging: PagingInput) {
            conversations(paging: $paging) {
                paging { total page pageSize }
                items {
                    id
                    clientName
                    clientAvatar
                    lastMessage
                    lastMessageAt
                    unreadCount
                    jobTitle
                }
            }
        }
        """
        return self.raw(query_str, {"paging": {"page": page, "pageSize": limit}})

    def get_conversation(self, conversation_id: str) -> dict[str, Any]:
        query_str = """
        query Conversation($conversationId: String!) {
            conversation(conversationId: $conversationId) {
                id
                clientName
                messages {
                    id
                    body
                    senderType
                    createdAt
                }
            }
        }
        """
        return self.raw(query_str, {"conversationId": conversation_id})

    def send_message(self, conversation_id: str, body: str) -> dict[str, Any]:
        mutation = """
        mutation SendMessage($conversationId: String!, $body: String!) {
            sendMessage(conversationId: $conversationId, body: $body) {
                success
                message {
                    id
                    body
                    createdAt
                }
            }
        }
        """
        return self.raw(mutation, {"conversationId": conversation_id, "body": body})

    # ---- Contracts ----
    def list_contracts(self, state: str | None = None, page: int = 1, limit: int = 25) -> dict[str, Any]:
        query_str = """
        query VendorContracts(
            $filter: VendorContractSearchFilterInput,
            $paging: ContractPagingInput
        ) {
            vendorContracts(filter: $filter, paging: $paging) {
                paging { total page pageSize }
                contracts {
                    contractId
                    jobTitle
                    clientName
                    budget
                    hourlyRate
                    status
                    startedOn
                    contractType
                }
            }
        }
        """
        return self.raw(query_str, {"filter": {"state": state} if state else {}, "paging": {"page": page, "pageSize": limit}})

    def get_contract(self, contract_id: str) -> dict[str, Any]:
        query_str = """
        query ContractDetails($contractId: String!) {
            contractDetails(contractId: $contractId) {
                contractId
                jobTitle
                clientName
                budget
                hourlyRate
                status
                startedOn
                contractType
            }
        }
        """
        return self.raw(query_str, {"contractId": contract_id})

    def get_work_diary(self, contract_id: str, page: int = 1, limit: int = 20) -> dict[str, Any]:
        query_str = """
        query WorkDiary($contractId: String!, $paging: PagingInput) {
            workDiary(contractId: $contractId, paging: $paging) {
                paging { total page pageSize }
                entries {
                    id
                    startTime
                    endTime
                    unitAmount
                    description
                }
            }
        }
        """
        return self.raw(query_str, {"contractId": contract_id, "paging": {"page": page, "pageSize": limit}})

    def get_earnings(self) -> dict[str, Any]:
        query_str = """
        query FreelancerEarnings {
            freelancerEarnings {
                totalEarned
                availableBalance
                pendingAmount
                currency
                period
            }
        }
        """
        return self.raw(query_str)

    def get_connects(self) -> dict[str, Any]:
        query_str = """
        query ConnectsBalance {
            connectsBalance {
                available
                total
                earned
                purchased
            }
        }
        """
        return self.raw(query_str)

    def close(self):
        self._client.close()
