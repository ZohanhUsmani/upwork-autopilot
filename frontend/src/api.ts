const API_BASE = import.meta.env.VITE_API_URL || '/api';

export interface JobAnalysis {
  score: number;
  grade: string;
  match_breakdown: Record<string, string>;
  red_flags: string[];
  tips: string[];
  should_bid: boolean;
  confidence: string;
}

export interface Profile {
  id: string;
  firstname: string;
  lastname: string;
  title: string;
  overview: string;
  skills: string[];
  total_earned: string;
  jk_score: number | null;
  jobs_count: number;
  jobs_hired_count: number;
  region: string;
  portfolio_url: string;
}

export interface Proposal {
  id: number;
  job_id: string;
  job_title: string;
  job_description: string;
  budget: string;
  skills: string[];
  screening_questions: { question: string; required: boolean }[];
  cover_letter: string;
  generated_answers: Record<string, string>;
  status: string;
  feedback: string | null;
  improved_cover_letter: string | null;
  submitted_at: string | null;
  created_at: string;
  client_name?: string;
}

export interface AutobidSettings {
  min_score: number;
  max_budget_usd: number;
  skills_filter: string[];
  exclude_skills: string[];
  job_types: string[];
  locations: string[];
  hourly_rate_min: number;
  hourly_rate_max: number;
  max_proposals_per_day: number;
  new_jobs_only: boolean;
  proposal_style: string;
  custom_instructions: string;
  running: boolean;
}

export interface DashboardStats {
  today_proposals: number;
  today_submitted: number;
  week_activity: number;
  by_status: Record<string, number>;
  recent_activity: { id: number; event_type: string; job_id: string; description: string; created_at: string }[];
  autobid_running: boolean;
}

// API client
async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const url = `${API_BASE}${path}`;
  const res = await fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
  });
  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new Error(`API ${res.status}: ${text}`);
  }
  return res.json();
}

export const api = {
  // Health
  health: () => request<{ status: string; autobidder_running: boolean }>('/health'),

  // Credentials
  saveCredentials: (data: { claude_api_key?: string; upwork_api_key?: string; composio_api_key?: string }) =>
    request<{ success: boolean }>('/api/credentials/save', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  verifyUpwork: () => request<{ success: boolean; profile?: Profile }>('/api/credentials/verify-upwork', { method: 'POST' }),

  // Profile
  getProfile: () => request<Profile>('/api/profile'),
  syncProfile: () => request<{ success: boolean; profile: Profile }>('/api/profile/sync', { method: 'POST' }),

  // Job analysis
  analyzeJob: (jobUrl: string, jobDescription?: string) =>
    request<JobAnalysis>('/api/jobs/analyze', {
      method: 'POST',
      body: JSON.stringify({ job_url: jobUrl, job_description: jobDescription }),
    }),

  // Proposals
  generateProposal: (data: {
    job_id: string; job_title: string; job_description: string;
    budget: string; skills: string[]; client_name: string;
    screening_questions?: { question: string; required: boolean }[];
  }) => request<{ proposal_id: number; cover_letter: string; screening_answers: Record<string, string>; bid_suggestion: string }>(
    '/api/proposals/generate', { method: 'POST', body: JSON.stringify(data) }
  ),

  listProposals: (status?: string, limit = 50, offset = 0) =>
    request<Proposal[]>(`/api/proposals?${status ? `status=${status}&` : ''}limit=${limit}&offset=${offset}`),

  approveProposal: (id: number) => request<{ success: boolean; proposal_id: number }>(`/api/proposals/approve`, {
    method: 'POST', body: JSON.stringify({ proposal_id: id }),
  }),

  improveProposal: (id: number, feedback: string) =>
    request<{ success: boolean; cover_letter: string }>('/api/proposals/improve', {
      method: 'POST', body: JSON.stringify({ proposal_id: id, feedback }),
    }),

  submitProposal: (id: number) =>
    request<{ success: boolean; provider: string; proposal_url?: string; error?: string }>('/api/proposals/submit', {
      method: 'POST', body: JSON.stringify({ proposal_id: id }),
    }),

  discardProposal: (id: number) => request<{ success: boolean }>('/api/proposals/discard', {
    method: 'POST', body: JSON.stringify({ proposal_id: id }),
  }),

  // Auto-bidder
  getAutobidSettings: () => request<AutobidSettings>('/api/autobid/settings'),
  saveAutobidSettings: (data: Partial<AutobidSettings>) =>
    request<{ success: boolean }>('/api/autobid/settings', { method: 'POST', body: JSON.stringify(data) }),
  startAutobid: () => request<{ success: boolean; running: boolean }>('/api/autobid/start', { method: 'POST' }),
  stopAutobid: () => request<{ success: boolean; running: boolean }>('/api/autobid/stop', { method: 'POST' }),
  getAutobidStatus: () => request<{ running: boolean; today_proposals: number }>('/api/autobid/status'),

  // Analytics
  getDashboard: () => request<DashboardStats>('/api/analytics/dashboard'),
  getProposalsAnalytics: (days = 30) => request<Proposal[]>(`/api/analytics/proposals?days=${days}`),

  // Upwork direct
  searchUpworkJobs: (params: Record<string, string | number>) =>
    request<Record<string, unknown>>(`/api/upwork/jobs/search?${new URLSearchParams(params as Record<string, string>).toString()}`),
  getUpworkJob: (jobId: string) => request<Record<string, unknown>>(`/api/upwork/jobs/${jobId}`),
  listUpworkProposals: (state = '') => request<Record<string, unknown>>(`/api/upwork/proposals?state=${state}`),
  listConversations: () => request<Record<string, unknown>>('/api/upwork/conversations'),
  sendMessage: (conversationId: string, body: string) =>
    request<Record<string, unknown>>(`/api/upwork/messages/${conversationId}`, {
      method: 'POST', body: JSON.stringify({ body }),
    }),
  listContracts: () => request<Record<string, unknown>>('/api/upwork/contracts'),
  getUpworkStats: () => request<Record<string, unknown>>('/api/upwork/stats'),

  // Bulk scan
  bulkScan: (jobCount: number) =>
    request<{ jobs: any[]; total: number; high_rank_count: number; high_threshold: number }>('/api/bulk/scan', {
      method: 'POST', body: JSON.stringify({ job_count: jobCount }),
    }),
  bulkGenerateDrafts: (jobCount: number) =>
    request<{ drafts: any[]; total: number }>('/api/bulk/generate-drafts', {
      method: 'POST', body: JSON.stringify({ job_count: jobCount }),
    }),

  // Utility
  parseJobUrl: (jobUrl: string) => request<{ job_id: string | null; url: string; error?: string }>(`/api/job-url-parser?job_url=${encodeURIComponent(jobUrl)}`),
};
