import { useState } from 'react';
import { api } from '../api';

type Step = 'choose' | 'scanning' | 'results' | 'confirm' | 'drafting' | 'reviewing' | 'done';

export default function AutoScan() {
  const [step, setStep] = useState<Step>('choose');
  const [jobCount, setJobCount] = useState(10);
  const [scanning, setScanning] = useState(false);
  const [scanResult, setScanResult] = useState<{ jobs: any[]; total: number; high_rank_count: number; high_threshold: number } | null>(null);
  const [confirming, setConfirming] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [drafts, setDrafts] = useState<any[]>([]);
  const [currentDraftIndex, setCurrentDraftIndex] = useState(0);
  const [toast, setToast] = useState<{ type: string; msg: string } | null>(null);

  const showToast = (type: string, msg: string) => {
    setToast({ type, msg });
    setTimeout(() => setToast(null), 4000);
  };

  const handleScan = async () => {
    if (jobCount < 1 || jobCount > 50) {
      showToast('error', 'Enter a number between 1 and 50');
      return;
    }
    setScanning(true);
    try {
      const res = await api.bulkScan(jobCount);
      setScanResult(res);
      setStep('results');
    } catch (err: any) {
      showToast('error', err.message || 'Scan failed — check your Upwork API key');
    } finally {
      setScanning(false);
    }
  };

  const handleConfirm = async () => {
    if (!scanResult) return;
    setConfirming(true);
    try {
      const res = await api.bulkGenerateDrafts(jobCount);
      setDrafts(res.drafts);
      if (res.drafts.length === 0) {
        showToast('info', 'No high-scoring jobs found — no drafts generated');
        setStep('done');
      } else {
        setCurrentDraftIndex(0);
        setStep('reviewing');
      }
    } catch (err: any) {
      showToast('error', err.message || 'Failed to generate drafts');
      setConfirming(false);
    } finally {
      setConfirming(false);
    }
  };

  const handleSkipDraft = () => {
    if (currentDraftIndex < drafts.length - 1) {
      setCurrentDraftIndex(prev => prev + 1);
    } else {
      setStep('done');
    }
  };

  const handleSendDraft = async () => {
    const draft = drafts[currentDraftIndex];
    if (!draft) return;
    try {
      await api.submitProposal(draft.proposal_id);
      showToast('success', `Proposal for "${draft.title}" submitted`);
      if (currentDraftIndex < drafts.length - 1) {
        setCurrentDraftIndex(prev => prev + 1);
      } else {
        setStep('done');
      }
    } catch (err: any) {
      showToast('error', err.message || 'Submission failed');
    }
  };

  const handleDiscardDraft = () => {
    const draft = drafts[currentDraftIndex];
    if (!draft) return;
    api.discardProposal(draft.proposal_id).then(() => {
      if (currentDraftIndex < drafts.length - 1) {
        setCurrentDraftIndex(prev => prev + 1);
      } else {
        setStep('done');
      }
    }).catch(() => {});
  };

  const reset = () => {
    setStep('choose');
    setJobCount(10);
    setScanResult(null);
    setDrafts([]);
    setCurrentDraftIndex(0);
  };

  return (
    <div className="autoscan-page">
      <div className="page-header">
        <div>
          <h1 className="page-title">Auto-Scan</h1>
          <p className="page-subtitle">Search jobs, score them, generate drafts, and send them — step by step</p>
        </div>
        <button className="btn btn-ghost" onClick={reset} style={{ marginLeft: 'auto' }}>Reset</button>
      </div>

      {toast && <div className={`toast toast-${toast.type}`}>{toast.msg}</div>}

      {/* Step 1: Choose how many jobs */}
      {step === 'choose' && (
        <div className="scan-choose">
          <div className="card">
            <h2 className="card-title">How many jobs to search?</h2>
            <p style={{ fontSize: 13, color: '#8888a0', marginBottom: 16 }}>
              The app will search Upwork for this many new jobs, score each one with Claude,
              and tell you how many are worth bidding on.
            </p>
            <div className="form-group" style={{ maxWidth: 200 }}>
              <label className="label">Number of jobs</label>
              <input
                className="input"
                type="number"
                min={1}
                max={50}
                value={jobCount}
                onChange={e => setJobCount(parseInt(e.target.value) || 1)}
              />
            </div>
            <button
              className="btn btn-primary"
              onClick={handleScan}
              style={{ marginTop: 16, width: '100%' }}
            >
              {scanning ? (
                <><div className="spinner" style={{ width: 16, height: 16, borderWidth: 2 }}></div> Searching {jobCount} jobs...</>
              ) : (
                `Search ${jobCount} Jobs`
              )}
            </button>
            <div style={{ marginTop: 12, padding: '8px 12px', background: 'rgba(108,92,231,0.08)', borderRadius: 6, color: '#a29bfe', fontSize: 13 }}>
              ⚡ Searches via Upwork GraphQL API · Scores each job 0-100 · Shows high-rank count
            </div>
          </div>
        </div>
      )}

      {/* Step 2: Scanning */}
      {step === 'scanning' && (
        <div className="loading-state" style={{ textAlign: 'center', padding: '60px 24px' }}>
          <div className="spinner" style={{ width: 40, height: 40, borderWidth: 3 }}></div>
          <p style={{ marginTop: 16, color: '#8888a0' }}>Searching {jobCount} jobs and scoring each one...</p>
          <p style={{ fontSize: 12, color: '#5a5a75', marginTop: 4 }}>This may take a minute if Claude is busy</p>
        </div>
      )}

      {/* Step 3: Results */}
      {step === 'results' && scanResult && (
        <div className="scan-results">
          <div className="card">
            <h2 className="card-title">Scan Complete</h2>
            <div className="results-summary">
              <div className="result-stat">
                <div className="result-stat-value">{scanResult.total}</div>
                <div className="result-stat-label">Jobs Found</div>
              </div>
              <div className="result-stat">
                <div className="result-stat-value" style={{ color: '#00b894' }}>{scanResult.high_rank_count}</div>
                <div className="result-stat-label">High Rank (≥{scanResult.high_threshold})</div>
              </div>
              <div className="result-stat">
                <div className="result-stat-value" style={{ color: '#e17055' }}>{scanResult.total - scanResult.high_rank_count}</div>
                <div className="result-stat-label">Low Rank</div>
              </div>
            </div>
            <div style={{ marginTop: 16, padding: '12px 16px', background: 'rgba(0,184,148,0.06)', borderRadius: 8, border: '1px solid rgba(0,184,148,0.15)' }}>
              <span style={{ fontSize: 14, color: '#00b894', fontWeight: 600 }}>
                {scanResult.high_rank_count} jobs scored {scanResult.high_threshold}+ — good candidates for proposals
              </span>
            </div>

            {/* Job list */}
            <div style={{ marginTop: 16 }}>
              <h3 style={{ fontSize: 14, fontWeight: 600, color: '#8888a0', marginBottom: 10 }}>
                All {scanResult.total} jobs scanned:
              </h3>
              <div className="job-list">
                {scanResult.jobs.map((job, i) => (
                  <div key={i} className={`job-list-item ${job.score >= scanResult.high_threshold ? 'high' : 'low'}`}>
                    <div className="job-list-score">
                      <span className={`score-badge ${job.score >= 85 ? 'A' : job.score >= 70 ? 'B' : job.score >= 55 ? 'C' : 'D'}`}>
                        {job.score}
                      </span>
                    </div>
                    <div className="job-list-info">
                      <div className="job-list-title">{job.title}</div>
                      <div className="job-list-meta">
                        {job.budget && <span>${job.budget}</span>}
                        {job.skills.length > 0 && <span>{job.skills.slice(0, 3).join(', ')}</span>}
                      </div>
                      {job.red_flags && job.red_flags.length > 0 && (
                        <div className="job-list-flags">
                          {job.red_flags.slice(0, 2).map((f: string, i: number) => (
                            <span key={i} className="flag-tag">{f}</span>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <button
              className="btn btn-primary"
              onClick={handleConfirm}
              style={{ marginTop: 20, width: '100%' }}
            >
              {confirming ? (
                <><div className="spinner" style={{ width: 16, height: 16, borderWidth: 2 }}></div> Generating drafts...</>
              ) : (
                `Generate Proposal Drafts for ${scanResult.high_rank_count} Jobs`
              )}
            </button>
            <button className="btn btn-secondary" onClick={reset} style={{ marginTop: 8 }}>
              Scan Different Jobs
            </button>
          </div>
        </div>
      )}

      {/* Step 4: Reviewing drafts one-by-one */}
      {step === 'reviewing' && drafts.length > 0 && (
        <div className="draft-review">
          <div className="card">
            <h2 className="card-title">
              Draft {currentDraftIndex + 1} of {drafts.length}
            </h2>
            <div style={{ fontSize: 13, color: '#8888a0', marginBottom: 12 }}>
              Review this proposal and decide: send it to Upwork, or skip it?
            </div>

            <div className="draft-header">
              <div className={`score-badge-lg ${drafts[currentDraftIndex].score >= 85 ? 'A' : drafts[currentDraftIndex].score >= 70 ? 'B' : 'C'}`}>
                {drafts[currentDraftIndex].score}
              </div>
              <div>
                <h3 style={{ fontSize: 18, fontWeight: 700, color: '#e0e0f0', margin: 0 }}>
                  {drafts[currentDraftIndex].title}
                </h3>
                <div style={{ fontSize: 13, color: '#8888a0' }}>
                  {drafts[currentDraftIndex].budget && <span>Budget: ${drafts[currentDraftIndex].budget}</span>}
                  {drafts[currentDraftIndex].skills.length > 0 && <span> · {drafts[currentDraftIndex].skills.join(', ')}</span>}
                </div>
              </div>
            </div>

            {/* Cover letter */}
            <div className="draft-cover-letter">
              <h4 style={{ fontSize: 13, fontWeight: 600, color: '#8888a0', marginBottom: 8 }}>Cover Letter</h4>
              <div className="prose" style={{ fontSize: 14, lineHeight: 1.7, whiteSpace: 'pre-wrap' }}>
                {drafts[currentDraftIndex].cover_letter}
              </div>
            </div>

            {/* Screening answers */}
            {drafts[currentDraftIndex].screening_answers && Object.keys(drafts[currentDraftIndex].screening_answers).length > 0 && (
              <div className="draft-screening">
                <h4 style={{ fontSize: 13, fontWeight: 600, color: '#8888a0', marginBottom: 8 }}>Screening Answers</h4>
                {(Object.entries(drafts[currentDraftIndex].screening_answers) as [string, string][]).map(([q, a]) => (
                  <div key={q} className="screening-qa">
                    <div className="screening-q" style={{ fontWeight: 500, color: '#c8c8e0', marginBottom: 2 }}>{q}</div>
                    <div className="screening-a" style={{ color: '#8888a0' }}>{a}</div>
                  </div>
                ))}
              </div>
            )}

            {/* Actions */}
            <div className="draft-actions">
              <button
                className="btn btn-success btn-lg"
                onClick={handleSendDraft}
                style={{ flex: 1 }}
              >
                <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor" style={{ marginRight: 6 }}>
                  <polygon points="5 3 19 12 5 21 5 3"/>
                </svg>
                Send to Upwork
              </button>
              <button
                className="btn btn-secondary btn-lg"
                onClick={handleSkipDraft}
                style={{ flex: 1 }}
              >
                Skip This One
              </button>
            </div>
            <div style={{ fontSize: 12, color: '#5a5a75', textAlign: 'center', marginTop: 8 }}>
              {currentDraftIndex + 1} of {drafts.length} drafts reviewed · {drafts.length - currentDraftIndex - 1} remaining
            </div>
          </div>
        </div>
      )}

      {/* Step 5: Done */}
      {step === 'done' && (
        <div className="scan-done">
          <div className="card" style={{ textAlign: 'center', padding: '40px 24px' }}>
            <div style={{ fontSize: 48, marginBottom: 16 }}>✅</div>
            <h2 className="card-title" style={{ marginBottom: 8 }}>All Done</h2>
            <p style={{ fontSize: 14, color: '#8888a0', marginBottom: 24 }}>
              {drafts.length} proposal{drafts.length !== 1 ? 's' : ''} processed.
              {drafts.filter((d: any) => d.sent).length > 0
                ? ` ${drafts.filter((d: any) => d.sent).length} submitted to Upwork.`
                : 'No proposals were submitted.'}
            </p>
            <div className="done-actions">
              <button className="btn btn-primary" onClick={() => window.location.href = '/proposals'}>
                View All Proposals
              </button>
              <button className="btn btn-secondary" onClick={reset}>
                Start New Scan
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
