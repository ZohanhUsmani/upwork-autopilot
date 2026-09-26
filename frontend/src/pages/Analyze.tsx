import { useState } from 'react';
import { api } from '../api';
import type { DashboardStats, JobAnalysis, Profile, Proposal, AutobidSettings } from '../api';

export default function Analyze() {
  const [jobUrl, setJobUrl] = useState('');
  const [jobDescription, setJobDescription] = useState('');
  const [analyzing, setAnalyzing] = useState(false);
  const [result, setResult] = useState<JobAnalysis | null>(null);
  const [profile, setProfile] = useState<Profile | null>(null);
  const [toast, setToast] = useState<{ type: string; msg: string } | null>(null);

  const showToast = (type: string, msg: string) => {
    setToast({ type, msg });
    setTimeout(() => setToast(null), 4000);
  };

  const handleAnalyze = async () => {
    if (!jobUrl && !jobDescription) {
      showToast('error', 'Enter a job URL or paste the job description');
      return;
    }
    setAnalyzing(true);
    setResult(null);
    try {
      const res = await api.analyzeJob(jobUrl, jobDescription || undefined);
      setResult(res);
    } catch (err: any) {
      showToast('error', err.message || 'Analysis failed');
    } finally {
      setAnalyzing(false);
    }
  };

  const loadProfile = async () => {
    try {
      const p = await api.getProfile();
      setProfile(p);
    } catch {
      showToast('error', 'No profile synced yet. Go to Profile to sync.');
    }
  };

  const score = result?.score ?? 0;
  const gradeClass = score >= 85 ? 'grade-A' : score >= 70 ? 'grade-B' : score >= 55 ? 'grade-C' : score >= 40 ? 'grade-D' : 'grade-F';
  const scoreClass = score >= 70 ? 'score-high' : score >= 40 ? 'score-mid' : 'score-low';

  return (
    <div className="analyze-page">
      <div className="page-header">
        <div>
          <h1 className="page-title">Job Analyzer</h1>
          <p className="page-subtitle">Paste an Upwork job URL or description to get an AI-powered fit score</p>
        </div>
        <button className="btn btn-secondary" onClick={loadProfile}>
          {profile ? `Loaded: ${profile.title}` : 'Load Profile'}
        </button>
      </div>

      <div className="grid-2" style={{ marginTop: 24 }}>
        {/* Input */}
        <div className="card">
          <h2 className="card-title" style={{ marginBottom: 16 }}>Job Details</h2>
          <div className="form-group">
            <label className="label">Upwork Job URL (optional)</label>
            <input
              className="input"
              placeholder="https://www.upwork.com/jobs/~01234567890"
              value={jobUrl}
              onChange={e => setJobUrl(e.target.value)}
            />
          </div>
          <div className="form-group" style={{ marginTop: 12 }}>
            <label className="label">Job Description (paste if no URL)</label>
            <textarea
              className="textarea"
              rows={8}
              placeholder="Paste the full job description here..."
              value={jobDescription}
              onChange={e => setJobDescription(e.target.value)}
            />
          </div>
          <button
            className={`btn btn-primary ${analyzing ? 'loading' : ''}`}
            onClick={handleAnalyze}
            disabled={analyzing || (!jobUrl && !jobDescription)}
            style={{ marginTop: 16, width: '100%' }}
          >
            {analyzing ? <><div className="spinner" style={{ width: 16, height: 16, borderWidth: 2 }}></div> Analyzing...</> : 'Analyze Job'}
          </button>
        </div>

        {/* Results */}
        <div className="card">
          {result ? (
            <>
              <div className="result-header">
                <div className={`score-circle ${scoreClass}`}>
                  <span className="score-circle-inner">{score}</span>
                </div>
                <div>
                  <div className={`grade-badge ${gradeClass}`} style={{ marginRight: 8 }}>{result.grade}</div>
                  <div style={{ fontSize: 13, color: '#8888a0' }}>
                    Confidence: {result.confidence}
                  </div>
                  <div style={{ fontSize: 13, color: '#8888a0' }}>
                    {result.should_bid ? '✅ Recommended to bid' : '❌ Not recommended'}
                  </div>
                </div>
              </div>

              {/* Match breakdown */}
              <div style={{ marginTop: 20 }}>
                <h3 style={{ fontSize: 14, fontWeight: 600, color: '#a0a0b8', marginBottom: 10 }}>Match Breakdown</h3>
                <div className="breakdown-grid">
                  {result.match_breakdown && Object.entries(result.match_breakdown).map(([key, val]) => (
                    <div key={key} className="breakdown-item">
                      <span className="breakdown-key">{key.replace(/_/g, ' ')}</span>
                      <span className="breakdown-val">{val}</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Red flags */}
              {result.red_flags && result.red_flags.length > 0 && (
                <div style={{ marginTop: 16 }}>
                  <h3 style={{ fontSize: 14, fontWeight: 600, color: '#e17055', marginBottom: 8 }}>
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ marginRight: 6, verticalAlign: 'middle' }}>
                      <path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/>
                      <line x1="12" y1="9" x2="12" y2="13"/>
                      <line x1="12" y1="17" x2="12.01" y2="17"/>
                    </svg>
                    Red Flags
                  </h3>
                  <ul className="flag-list">
                    {result.red_flags.map((f: string, i: number) => (
                      <li key={i} className="flag-item">{f}</li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Tips */}
              {result.tips && result.tips.length > 0 && (
                <div style={{ marginTop: 16 }}>
                  <h3 style={{ fontSize: 14, fontWeight: 600, color: '#00b894', marginBottom: 8 }}>
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ marginRight: 6, verticalAlign: 'middle' }}>
                      <circle cx="12" cy="12" r="10"/>
                      <line x1="12" y1="16" x2="12" y2="12"/>
                      <line x1="12" y1="8" x2="12.01" y2="8"/>
                    </svg>
                    Tips for Your Proposal
                  </h3>
                  <ul className="tip-list">
                    {result.tips.map((t: string, i: number) => (
                      <li key={i} className="tip-item">{t}</li>
                    ))}
                  </ul>
                </div>
              )}
            </>
          ) : (
            <div className="empty-state">
              <div className="empty-state-icon">📊</div>
              <div className="empty-state-title">No analysis yet</div>
              <div className="empty-state-desc">Enter a job URL or description and click Analyze</div>
            </div>
          )}
        </div>
      </div>

      {toast && <div className={`toast toast-${toast.type}`}>{toast.msg}</div>}
    </div>
  );
}
