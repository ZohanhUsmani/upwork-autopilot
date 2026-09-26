import { useState, useEffect } from 'react';
import { api } from '../api';
import type { AutobidSettings } from '../api';

export default function Settings() {
  const [credentials, setCredentials] = useState({
    claude_api_key: '',
    upwork_api_key: '',
    composio_api_key: '',
  });
  const [settings, setSettings] = useState<AutobidSettings | null>(null);
  const [saving, setSaving] = useState(false);
  const [verifying, setVerifying] = useState(false);
  const [profileLoaded, setProfileLoaded] = useState(false);
  const [toast, setToast] = useState<{ type: string; msg: string } | null>(null);

  const showToast = (type: string, msg: string) => {
    setToast({ type, msg });
    setTimeout(() => setToast(null), 4000);
  };

  const loadSettings = async () => {
    try {
      const s = await api.getAutobidSettings();
      setSettings(s);
    } catch {}
  };

  const loadCredentials = async () => {
    // Credentials aren't exposed via API for security — user must re-enter
    // We just check if they're configured by testing the API
    try {
      await api.verifyUpwork();
      setProfileLoaded(true);
    } catch {
      setProfileLoaded(false);
    }
  };

  useEffect(() => { loadSettings(); }, []);

  const saveCredentials = async () => {
    setSaving(true);
    try {
      await api.saveCredentials({
        claude_api_key: credentials.claude_api_key || undefined,
        upwork_api_key: credentials.upwork_api_key || undefined,
        composio_api_key: credentials.composio_api_key || undefined,
      });
      showToast('success', 'Credentials saved');
      if (credentials.upwork_api_key) {
        await loadCredentials();
      }
      // Clear sensitive fields from state
      setCredentials(prev => ({ ...prev, claude_api_key: '', upwork_api_key: '', composio_api_key: '' }));
    } catch (err: any) {
      showToast('error', err.message || 'Failed to save credentials');
    } finally {
      setSaving(false);
    }
  };

  const saveSettings = async (data: Partial<AutobidSettings>) => {
    setSaving(true);
    try {
      await api.saveAutobidSettings(data);
      showToast('success', 'Settings saved');
      loadSettings();
    } catch (err: any) {
      showToast('error', err.message || 'Failed to save settings');
    } finally {
      setSaving(false);
    }
  };

  const updateSetting = (key: keyof AutobidSettings, value: any) => {
    if (!settings) return;
    setSettings(prev => prev ? { ...prev, [key]: value } : null);
  };

  return (
    <div className="settings-page">
      <div className="page-header">
        <div>
          <h1 className="page-title">Settings</h1>
          <p className="page-subtitle">Configure API keys, auto-bidder filters, and proposal style</p>
        </div>
      </div>

      <div className="grid-2" style={{ marginTop: 24 }}>
        {/* Credentials */}
        <div className="card">
          <h2 className="card-title" style={{ marginBottom: 16 }}>API Credentials</h2>
          <p style={{ fontSize: 13, color: '#8888a0', marginBottom: 16 }}>
            These are stored encrypted on the server. Your keys never leave the VPS.
          </p>

          <div className="form-group">
            <label className="label">Claude API Key</label>
            <input
              className="input"
              type="password"
              placeholder="sk-ant-api03-..."
              value={credentials.claude_api_key}
              onChange={e => setCredentials(prev => ({ ...prev, claude_api_key: e.target.value }))}
            />
            <div style={{ fontSize: 12, color: '#5a5a75', marginTop: 4 }}>
              Get yours at{' '}
              <a href="https://console.anthropic.com" target="_blank" rel="noopener" style={{ color: '#a29bfe' }}>
                console.anthropic.com
              </a>
            </div>
          </div>

          <div className="form-group" style={{ marginTop: 12 }}>
            <label className="label">Upwork API Key (OAuth Access Token)</label>
            <input
              className="input"
              type="password"
              placeholder="OAuth access token from developers.upwork.com"
              value={credentials.upwork_api_key}
              onChange={e => setCredentials(prev => ({ ...prev, upwork_api_key: e.target.value }))}
            />
            <div style={{ fontSize: 12, color: '#5a5a75', marginTop: 4 }}>
              Register at{' '}
              <a href="https://developers.upwork.com" target="_blank" rel="noopener" style={{ color: '#a29bfe' }}>
                developers.upwork.com
              </a>
              {' · '}Get an OAuth access token via the API console
            </div>
          </div>

          <div className="form-group" style={{ marginTop: 12 }}>
            <label className="label">Composio API Key (optional)</label>
            <input
              className="input"
              type="password"
              placeholder="Composio project API key"
              value={credentials.composio_api_key}
              onChange={e => setCredentials(prev => ({ ...prev, composio_api_key: e.target.value }))}
            />
            <div style={{ fontSize: 12, color: '#5a5a75', marginTop: 4 }}>
              Required only if you want Composio as a submission provider.
              Get at{' '}
              <a href="https://dashboard.composio.dev" target="_blank" rel="noopener" style={{ color: '#a29bfe' }}>
                dashboard.composio.dev
              </a>
            </div>
          </div>

          <button
            className={`btn btn-primary ${saving ? 'loading' : ''}`}
            onClick={saveCredentials}
            disabled={saving}
            style={{ marginTop: 16, width: '100%' }}
          >
            {saving ? <><div className="spinner" style={{ width: 16, height: 16, borderWidth: 2 }}></div> Saving...</> : 'Save Credentials'}
          </button>

          {profileLoaded && (
            <div style={{ marginTop: 12, padding: '8px 12px', background: 'rgba(0,184,148,0.1)', borderRadius: 6, color: '#00b894', fontSize: 13, display: 'flex', alignItems: 'center', gap: 6 }}>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <polyline points="20 6 9 17 4 12"/>
              </svg>
              Upwork connected
            </div>
          )}
        </div>

        {/* Auto-bidder settings */}
        <div className="card">
          <h2 className="card-title" style={{ marginBottom: 16 }}>Auto-Bidder Filters</h2>
          <p style={{ fontSize: 13, color: '#8888a0', marginBottom: 16 }}>
            Jobs that match these criteria and score above the threshold will be drafted for your review.
          </p>

          <div className="form-group">
            <label className="label">Minimum Score</label>
            <input
              className="input"
              type="number"
              min={0}
              max={100}
              value={settings?.min_score ?? 70}
              onChange={e => updateSetting('min_score', parseInt(e.target.value) || 0)}
            />
            <div style={{ fontSize: 12, color: '#5a5a75', marginTop: 4 }}>
              Only draft proposals for jobs scoring above this (0-100)
            </div>
          </div>

          <div className="form-group" style={{ marginTop: 12 }}>
            <label className="label">Max Budget (USD)</label>
            <input
              className="input"
              type="number"
              min={0}
              value={settings?.max_budget_usd ?? 5000}
              onChange={e => updateSetting('max_budget_usd', parseInt(e.target.value) || 0)}
            />
          </div>

          <div className="form-group" style={{ marginTop: 12 }}>
            <label className="label">Skills Filter (comma-separated)</label>
            <input
              className="input"
              placeholder="e.g. Python, React, AWS, TypeScript"
              value={(settings?.skills_filter ?? []).join(', ')}
              onChange={e => updateSetting('skills_filter', e.target.value.split(',').map(s => s.trim()).filter(Boolean))}
            />
          </div>

          <div className="form-group" style={{ marginTop: 12 }}>
            <label className="label">Job Types</label>
            <div style={{ display: 'flex', gap: 8 }}>
              {['FIXED', 'HOURLY', 'PART_TIME', 'FULL_TIME'].map(t => (
                <label key={t} className="checkbox-label">
                  <input
                    type="checkbox"
                    checked={(settings?.job_types ?? ['FIXED', 'HOURLY']).includes(t)}
                    onChange={e => {
                      const current = (settings?.job_types ?? ['FIXED', 'HOURLY']) as string[];
                      if (e.target.checked) {
                        updateSetting('job_types', [...current, t]);
                      } else {
                        updateSetting('job_types', current.filter(c => c !== t));
                      }
                    }}
                  />
                  {t}
                </label>
              ))}
            </div>
          </div>

          <div className="form-group" style={{ marginTop: 12 }}>
            <label className="label">Max Proposals Per Day</label>
            <input
              className="input"
              type="number"
              min={1}
              max={100}
              value={settings?.max_proposals_per_day ?? 10}
              onChange={e => updateSetting('max_proposals_per_day', parseInt(e.target.value) || 1)}
            />
          </div>

          <div className="form-group" style={{ marginTop: 12 }}>
            <label className="checkbox-label">
              <input
                type="checkbox"
                checked={settings?.new_jobs_only ?? true}
                onChange={e => updateSetting('new_jobs_only', e.target.checked)}
              />
              Only scan new jobs (posted within 7 days)
            </label>
          </div>

          <button
            className={`btn btn-primary ${saving ? 'loading' : ''}`}
            onClick={() => {
              if (!settings) return;
              saveSettings(settings);
            }}
            disabled={saving}
            style={{ marginTop: 16, width: '100%' }}
          >
            {saving ? <><div className="spinner" style={{ width: 16, height: 16, borderWidth: 2 }}></div> Saving...</> : 'Save Filters'}
          </button>
        </div>
      </div>

      {/* Proposal style */}
      <div className="card" style={{ marginTop: 16 }}>
        <h2 className="card-title" style={{ marginBottom: 16 }}>Proposal Style & Instructions</h2>

        <div className="form-group">
          <label className="label">Proposal Style</label>
          <select
            className="select"
            value={settings?.proposal_style ?? ''}
            onChange={e => updateSetting('proposal_style', e.target.value)}
          >
            <option value="">Default (professional, direct, confident)</option>
            <option value="friendly">Friendly & conversational</option>
            <option value="formal">Formal & business-like</option>
            <option value="short">Short & punchy (under 100 words)</option>
            <option value="detailed">Detailed & thorough</option>
          </select>
        </div>

        <div className="form-group" style={{ marginTop: 12 }}>
          <label className="label">Custom Instructions (optional)</label>
          <textarea
            className="textarea"
            rows={4}
            placeholder="e.g. Always mention my 5 years of React experience. Never quote a price below $50/hr. Address the client by first name."
            value={settings?.custom_instructions ?? ''}
            onChange={e => updateSetting('custom_instructions', e.target.value)}
          />
        </div>

        <button
          className={`btn btn-primary ${saving ? 'loading' : ''}`}
          onClick={() => {
            if (!settings) return;
            saveSettings(settings);
          }}
          disabled={saving || !settings}
          style={{ marginTop: 16 }}
        >
          {saving ? <><div className="spinner" style={{ width: 16, height: 16, borderWidth: 2 }}></div> Saving...</> : 'Save Style'}
        </button>
      </div>

      {toast && <div className={`toast toast-${toast.type}`}>{toast.msg}</div>}
    </div>
  );
}
