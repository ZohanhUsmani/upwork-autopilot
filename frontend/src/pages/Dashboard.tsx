import { useState, useEffect } from 'react';
import { api } from '../api';
import type { DashboardStats } from '../api';

export default function Dashboard() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [running, setRunning] = useState(false);
  const [loading, setLoading] = useState(true);
  const [toast, setToast] = useState<{ type: string; msg: string } | null>(null);

  const fetchStats = () => {
    api.getDashboard()
      .then(d => { setStats(d); setRunning(d.autobid_running); })
      .catch(() => {})
      .finally(() => setLoading(false));
  };

  useEffect(() => { fetchStats(); }, []);
  useEffect(() => { if (running) { const iv = setInterval(fetchStats, 10000); return () => clearInterval(iv); } }, [running]);

  const showToast = (type: string, msg: string) => {
    setToast({ type, msg });
    setTimeout(() => setToast(null), 3000);
  };

  const handleStart = async () => {
    try {
      await api.startAutobid();
      showToast('success', 'Auto-bidder started — scanning Upwork for jobs');
      fetchStats();
    } catch (err: any) {
      showToast('error', err.message || 'Failed to start');
    }
  };

  const handleStop = async () => {
    try {
      await api.stopAutobid();
      showToast('info', 'Auto-bidder stopped');
      fetchStats();
    } catch (err: any) {
      showToast('error', err.message || 'Failed to stop');
    }
  };

  const gradeClass = (score: number) => {
    if (score >= 85) return 'grade-A';
    if (score >= 70) return 'grade-B';
    if (score >= 55) return 'grade-C';
    if (score >= 40) return 'grade-D';
    return 'grade-F';
  };

  const scoreClass = (score: number) => {
    if (score >= 70) return 'score-high';
    if (score >= 40) return 'score-mid';
    return 'score-low';
  };

  return (
    <div className="dashboard">
      <div className="page-header">
        <div>
          <h1 className="page-title">Dashboard</h1>
          <p className="page-subtitle">Your Upwork autopilot — monitor and control everything</p>
        </div>
      </div>

      {/* Status banner */}
      <div className={`autobid-banner ${running ? 'running' : 'stopped'}`}>
        <div className="banner-icon">
          {running ? (
            <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="12" cy="12" r="10"/>
              <polyline points="12 6 12 12 16 14"/>
            </svg>
          ) : (
            <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <rect x="6" y="6" width="12" height="12" rx="2"/>
            </svg>
          )}
        </div>
        <div className="banner-text">
          <span className="banner-label">Auto-Bidder</span>
          <span className="banner-status">
            {running
              ? 'Running — scanning Upwork for new jobs every 2 minutes'
              : 'Stopped — click Start to begin scanning and drafting proposals'}
          </span>
        </div>
        <div className="banner-buttons">
          {running ? (
            <button className="btn btn-danger banner-btn" onClick={handleStop}>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                <rect x="6" y="6" width="12" height="12" rx="2"/>
              </svg>
              Stop
            </button>
          ) : (
            <button className="btn btn-success banner-btn" onClick={handleStart}>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                <polygon points="5 3 19 12 5 21 5 3"/>
              </svg>
              Start
            </button>
          )}
        </div>
      </div>

      {/* What the buttons do */}
      <div className="feature-guide">
        <div className="guide-header">
          <h2 className="guide-title">What each button does</h2>
          <p className="guide-sub">Every action is explained below — nothing happens without you knowing</p>
        </div>
        <div className="guide-grid">
          <div className="guide-card">
            <div className="guide-card-icon">🔍</div>
            <div className="guide-card-body">
              <h3 className="guide-card-title">Job Analyzer</h3>
              <p className="guide-card-desc">Paste any Upwork job URL and get an instant 0-100 fit score. Shows red flags, tips for your proposal, and a match breakdown against your profile.</p>
              <p className="guide-card-note"><strong>You control it.</strong> Paste a URL → click Analyze → read the result. Nothing is submitted.</p>
            </div>
          </div>
          <div className="guide-card">
            <div className="guide-card-icon">📝</div>
            <div className="guide-card-body">
              <h3 className="guide-card-title">Proposals</h3>
              <p className="guide-card-desc">All AI-generated proposals appear here. Each one shows the cover letter, screening answers, and job details.</p>
              <p className="guide-card-note"><strong>Review → Approve → Submit.</strong> You approve a draft, then click "Submit to Upwork" only when you're ready. Nothing is sent without your click.</p>
            </div>
          </div>
          <div className="guide-card">
            <div className="guide-card-icon">👤</div>
            <div className="guide-card-body">
              <h3 className="guide-card-title">Profile</h3>
              <p className="guide-card-desc">Syncs your Upwork freelancer profile into the app. Claude uses this to tailor proposals to your skills and experience.</p>
              <p className="guide-card-note"><strong>One-time setup.</strong> Click "Sync Profile" once after adding your Upwork API key. Re-sync anytime your profile changes.</p>
            </div>
          </div>
          <div className="guide-card">
            <div className="guide-card-icon">⚙️</div>
            <div className="guide-card-body">
              <h3 className="guide-card-title">Settings</h3>
              <p className="guide-card-desc">Where you add your Claude API key, Upwork API key, and configure the auto-bidder filters (min score, skills, budget, etc.).</p>
              <p className="guide-card-note"><strong>Save credentials first.</strong> Without them, the auto-bidder can't search or score jobs.</p>
            </div>
          </div>
        </div>
      </div>

      {loading ? (
        <div className="loading-state">
          <div className="spinner" style={{ width: 32, height: 32, borderWidth: 3 }}></div>
          <p>Loading dashboard...</p>
        </div>
      ) : (
        <>
          {/* Stats */}
          <div className="stats-grid">
            <div className="stat-card">
              <div className="stat-value">{stats?.today_proposals ?? 0}</div>
              <div className="stat-label">Today's Drafts</div>
              <div className="stat-note">proposals drafted by auto-bidder today</div>
            </div>
            <div className="stat-card">
              <div className="stat-value">{stats?.today_submitted ?? 0}</div>
              <div className="stat-label">Today's Submitted</div>
              <div className="stat-note">you submitted to Upwork today</div>
            </div>
            <div className="stat-card">
              <div className="stat-value">{stats?.week_activity ?? 0}</div>
              <div className="stat-label">This Week</div>
              <div className="stat-note">total activity (scans, drafts, submits)</div>
            </div>
            <div className="stat-card">
              <div className="stat-value">{stats?.by_status?.submitted ?? 0}</div>
              <div className="stat-label">Total Submitted</div>
              <div className="stat-note">all-time proposals sent to Upwork</div>
            </div>
          </div>

          {/* Status breakdown */}
          <div className="card" style={{ marginTop: 16 }}>
            <div className="card-header">
              <h2 className="card-title">Proposal Status Breakdown</h2>
              <span className="card-subtitle">What's in your proposal queue right now</span>
            </div>
            <div className="status-bars">
              {(['pending', 'approved', 'improved', 'submitted', 'discarded'] as const).map(s => {
                const count = stats?.by_status?.[s] ?? 0;
                const pct = stats?.today_proposals ? Math.round((count / stats.today_proposals) * 100) : 0;
                const labels: Record<string, string> = {
                  pending: 'Drafted — waiting for your review',
                  approved: 'Approved — ready to submit',
                  improved: 'You asked for changes — improved version ready',
                  submitted: 'Submitted to Upwork',
                  discarded: 'You discarded this one',
                };
                return (
                  <div key={s} className="status-bar-row">
                    <div className="status-bar-left">
                      <span className={`badge badge-${s}`}>{s}</span>
                      <span className="status-bar-label">{labels[s]}</span>
                    </div>
                    <div className="bar-track">
                      <div className={`bar-fill bar-${s}`} style={{ width: `${Math.max(pct, count > 0 ? 8 : 0)}%` }}></div>
                    </div>
                    <span className="bar-count">{count}</span>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Recent activity */}
          <div className="card" style={{ marginTop: 16 }}>
            <div className="card-header">
              <h2 className="card-title">Recent Activity</h2>
              <button className="btn btn-ghost btn-sm" onClick={fetchStats}>Refresh</button>
            </div>
            {stats?.recent_activity && stats.recent_activity.length > 0 ? (
              <div className="activity-list">
                {stats.recent_activity.map(a => (
                  <div key={a.id} className="activity-item">
                    <div className="activity-time">{new Date(a.created_at).toLocaleString()}</div>
                    <div className="activity-desc">
                      <span className={`activity-badge badge-${a.event_type === 'proposal_drafted' ? 'pending' : a.event_type === 'job_skipped' ? 'discarded' : 'submitted'}`}>
                        {a.event_type.replace(/_/g, ' ')}
                      </span>
                      <span className="activity-text">{a.description}</span>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="empty-state">
                <div className="empty-state-icon">📋</div>
                <div className="empty-state-title">No activity yet</div>
                <div className="empty-state-desc">Start the auto-bidder to begin scanning jobs</div>
              </div>
            )}
          </div>

          {/* Quick actions */}
          <div className="quick-actions" style={{ marginTop: 16 }}>
            <a href="/analyze" className="quick-action-card">
              <div className="quick-action-icon">🔍</div>
              <div className="quick-action-text">
                <div className="quick-action-title">Job Analyzer</div>
                <div className="quick-action-desc">Paste a job URL → get AI score, red flags, and proposal tips</div>
              </div>
            </a>
            <a href="/proposals" className="quick-action-card">
              <div className="quick-action-icon">📝</div>
              <div className="quick-action-text">
                <div className="quick-action-title">Proposals</div>
                <div className="quick-action-desc">Review drafts → Approve → Submit to Upwork (you click submit)</div>
              </div>
            </a>
            <a href="/profile" className="quick-action-card">
              <div className="quick-action-icon">👤</div>
              <div className="quick-action-text">
                <div className="quick-action-title">Profile</div>
                <div className="quick-action-desc">Sync your Upwork profile so proposals match your skills</div>
              </div>
            </a>
            <a href="/settings" className="quick-action-card">
              <div className="quick-action-icon">⚙️</div>
              <div className="quick-action-text">
                <div className="quick-action-title">Settings</div>
                <div className="quick-action-desc">Add API keys, set filters, choose proposal style</div>
              </div>
            </a>
          </div>
        </>
      )}

      {toast && (
        <div className={`toast toast-${toast.type}`}>{toast.msg}</div>
      )}
    </div>
  );
}
