import { useState, useEffect } from 'react';
import { api } from '../api';
import type { DashboardStats, JobAnalysis, Profile, Proposal, AutobidSettings } from '../api';
import type { Profile as ProfileType } from '../api';

export default function Profile() {
  const [profile, setProfile] = useState<ProfileType | null>(null);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [toast, setToast] = useState<{ type: string; msg: string } | null>(null);

  const showToast = (type: string, msg: string) => {
    setToast({ type, msg });
    setTimeout(() => setToast(null), 4000);
  };

  const fetchProfile = async () => {
    setLoading(true);
    try {
      const p = await api.getProfile();
      setProfile(p);
    } catch {
      setProfile(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchProfile(); }, []);

  const handleSync = async () => {
    setSyncing(true);
    try {
      const res = await api.syncProfile();
      setProfile(res.profile);
      showToast('success', 'Profile synced successfully');
    } catch (err: any) {
      showToast('error', err.message || 'Sync failed — check your Upwork API key');
    } finally {
      setSyncing(false);
    }
  };

  if (loading) {
    return (
      <div className="profile-page">
        <div className="page-header">
          <h1 className="page-title">Profile</h1>
          <p className="page-subtitle">Your Upwork freelancer profile</p>
        </div>
        <div className="loading-state" style={{ textAlign: 'center', padding: 48 }}>
          <div className="spinner" style={{ width: 32, height: 32, borderWidth: 3 }}></div>
          <p>Loading profile...</p>
        </div>
      </div>
    );
  }

  if (!profile) {
    return (
      <div className="profile-page">
        <div className="page-header">
          <h1 className="page-title">Profile</h1>
          <p className="page-subtitle">Your Upwork freelancer profile</p>
        </div>
        <div className="card" style={{ textAlign: 'center', padding: 48 }}>
          <div style={{ fontSize: 48, marginBottom: 12 }}>👤</div>
          <h2 style={{ fontSize: 18, fontWeight: 600, marginBottom: 8 }}>No profile synced</h2>
          <p style={{ color: '#8888a0', marginBottom: 20 }}>
            Connect your Upwork account to let the AI analyze jobs against your profile.
          </p>
          <p style={{ fontSize: 13, color: '#5a5a75', marginBottom: 20 }}>
            You need to save your Upwork API key in Settings first.
          </p>
          <button className="btn btn-primary" onClick={() => window.location.href = '/settings'}>
            Go to Settings
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="profile-page">
      <div className="page-header">
        <div>
          <h1 className="page-title">Profile</h1>
          <p className="page-subtitle">Your Upwork freelancer profile — used for job matching and proposal generation</p>
        </div>
        <button
          className={`btn btn-secondary ${syncing ? 'loading' : ''}`}
          onClick={handleSync}
          disabled={syncing}
        >
          {syncing ? <><div className="spinner" style={{ width: 16, height: 16, borderWidth: 2 }}></div> Syncing...</> : 'Sync Profile'}
        </button>
      </div>

      <div className="profile-grid">
        {/* Basic info */}
        <div className="card">
          <h2 className="card-title" style={{ marginBottom: 16 }}>Profile Overview</h2>
          <div className="profile-basic">
            <div className="profile-avatar">
              <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                <path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2"/>
                <circle cx="12" cy="7" r="4"/>
              </svg>
            </div>
            <div className="profile-name">
              {profile.firstname} {profile.lastname}
            </div>
            <div className="profile-title">{profile.title}</div>
          </div>

          <div className="profile-section" style={{ marginTop: 20 }}>
            <div className="profile-field">
              <span className="profile-label">Overview</span>
              <p className="profile-overview prose">{profile.overview || 'No overview set'}</p>
            </div>
          </div>

          <div className="profile-section" style={{ marginTop: 16 }}>
            <div className="profile-field">
              <span className="profile-label">Skills ({profile.skills.length})</span>
              <div className="skills-tags">
                {profile.skills.map(s => (
                  <span key={s} className="skill-tag">{s}</span>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* Stats */}
        <div className="card">
          <h2 className="card-title" style={{ marginBottom: 16 }}>Performance Stats</h2>
          <div className="stats-grid" style={{ gap: 8 }}>
            <div className="stat-card" style={{ padding: 12 }}>
              <div className="stat-value" style={{ fontSize: 20 }}>
                {profile.jk_score != null ? profile.jk_score : '—'}
              </div>
              <div className="stat-label">JSS Score</div>
            </div>
            <div className="stat-card" style={{ padding: 12 }}>
              <div className="stat-value" style={{ fontSize: 20 }}>${profile.total_earned}</div>
              <div className="stat-label">Total Earned</div>
            </div>
            <div className="stat-card" style={{ padding: 12 }}>
              <div className="stat-value" style={{ fontSize: 20 }}>{profile.jobs_hired_count}</div>
              <div className="stat-label">Jobs Hired</div>
            </div>
            <div className="stat-card" style={{ padding: 12 }}>
              <div className="stat-value" style={{ fontSize: 20 }}>{profile.jobs_count}</div>
              <div className="stat-label">Total Jobs</div>
            </div>
          </div>
        </div>

        {/* Meta */}
        <div className="card">
          <h2 className="card-title" style={{ marginBottom: 16 }}>Profile Details</h2>
          <div className="profile-meta">
            <div className="meta-row">
              <span className="meta-label">Region</span>
              <span className="meta-value">{profile.region || '—'}</span>
            </div>
            <div className="meta-row">
              <span className="meta-label">Portfolio</span>
              <span className="meta-value">
                {profile.portfolio_url ? (
                  <a href={profile.portfolio_url} target="_blank" rel="noopener" style={{ color: '#a29bfe' }}>
                    View portfolio
                  </a>
                ) : '—'}
              </span>
            </div>
            <div className="meta-row">
              <span className="meta-label">Profile ID</span>
              <span className="meta-value">{profile.id}</span>
            </div>
            <div className="meta-row">
              <span className="meta-label">Skills Count</span>
              <span className="meta-value">{profile.skills.length}</span>
            </div>
          </div>
        </div>
      </div>

      {toast && <div className={`toast toast-${toast.type}`}>{toast.msg}</div>}
    </div>
  );
}
