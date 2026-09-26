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

  const showToast = (type: string, msg: string) => {
    setToast({ type, msg });
    setTimeout(() => setToast(null), 3000);
  };

  const toggleAutobid = async () => {
    try {
      if (running) {
        await api.stopAutobid();
        showToast('success', 'Auto-bidder stopped');
      } else {
        await api.startAutobid();
        showToast('success', 'Auto-bidder started — scanning for jobs');
      }
      fetchStats();
    } catch (err: any) {
      showToast('error', err.message || 'Failed to toggle');
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
          <p className="page-subtitle">Monitor your Upwork autopilot activity</p>
        </div>
      </div>

      {/* Start/Stop banner */}
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
          <span className="banner-status">{running ? 'Running — scanning for jobs' : 'Stopped — click start to begin'}</span>
        </div>
        <button
          className={`btn btn-lg ${running ? 'btn-danger' : 'btn-success'} banner-btn`}
          onClick={toggleAutobid}
        >
          {running ? 'Stop' : 'Start'}
        </button>
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
              <div className="stat-label">Today's Proposals</div>
            </div>
            <div className="stat-card">
              <div className="stat-value">{stats?.today_submitted ?? 0}</div>
              <div className="stat-label">Today's Submitted</div>
            </div>
            <div className="stat-card">
              <div className="stat-value">{stats?.week_activity ?? 0}</div>
              <div className="stat-label">This Week Activity</div>
            </div>
            <div className="stat-card">
              <div className="stat-value">{stats?.by_status?.submitted ?? 0}</div>
              <div className="stat-label">Total Submitted</div>
            </div>
          </div>

          {/* Status breakdown */}
          <div className="card" style={{ marginTop: 16 }}>
            <div className="card-header">
              <h2 className="card-title">Proposal Status Breakdown</h2>
            </div>
            <div className="status-bars">
              {(['pending', 'approved', 'improved', 'submitted', 'discarded'] as const).map(s => {
                const count = stats?.by_status?.[s] ?? 0;
                const pct = stats?.today_proposals ? Math.round((count / stats.today_proposals) * 100) : 0;
                return (
                  <div key={s} className="status-bar-row">
                    <span className={`badge badge-${s}`}>{s}</span>
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
              <button className="btn btn-ghost btn-sm" onClick={() => window.location.reload()}>Refresh</button>
            </div>
            {stats?.recent_activity && stats.recent_activity.length > 0 ? (
              <div className="activity-list">
                {stats.recent_activity.map(a => (
                  <div key={a.id} className="activity-item">
                    <div className="activity-time">
                      {new Date(a.created_at).toLocaleString()}
                    </div>
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
                <div className="quick-action-desc">Paste a job URL and get an AI score + red flags</div>
              </div>
            </a>
            <a href="/proposals" className="quick-action-card">
              <div className="quick-action-icon">📝</div>
              <div className="quick-action-text">
                <div className="quick-action-title">Proposals</div>
                <div className="quick-action-desc">Review, improve, and submit proposal drafts</div>
              </div>
            </a>
            <a href="/profile" className="quick-action-card">
              <div className="quick-action-icon">👤</div>
              <div className="quick-action-text">
                <div className="quick-action-title">Profile</div>
                <div className="quick-action-desc">Sync and view your Upwork freelancer profile</div>
              </div>
            </a>
            <a href="/settings" className="quick-action-card">
              <div className="quick-action-icon">⚙️</div>
              <div className="quick-action-text">
                <div className="quick-action-title">Settings</div>
                <div className="quick-action-desc">Configure API keys, filters, and proposal style</div>
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
