import { useState, useEffect } from 'react';
import { api } from '../api';
import type { Proposal } from '../api';

export default function Proposals() {
  const [proposals, setProposals] = useState<Proposal[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<string>('all');
  const [submitting, setSubmitting] = useState<Record<number, boolean>>({});
  const [toast, setToast] = useState<{ type: string; msg: string } | null>(null);

  const showToast = (type: string, msg: string) => {
    setToast({ type, msg });
    setTimeout(() => setToast(null), 3000);
  };

  const fetchProposals = (status?: string) => {
    setLoading(true);
    api.listProposals(status ?? undefined, 100, 0)
      .then(setProposals)
      .catch(() => setProposals([]))
      .finally(() => setLoading(false));
  };

  useEffect(() => { fetchProposals(filter === 'all' ? undefined : filter); }, [filter]);

  const handleApprove = async (id: number) => {
    try {
      await api.approveProposal(id);
      showToast('success', 'Proposal approved — ready to submit');
      fetchProposals(filter === 'all' ? undefined : filter);
    } catch (err: any) { showToast('error', err.message || 'Failed to approve'); }
  };

  const handleDiscard = async (id: number) => {
    try {
      await api.discardProposal(id);
      showToast('success', 'Proposal discarded');
      fetchProposals(filter === 'all' ? undefined : filter);
    } catch (err: any) { showToast('error', err.message || 'Failed to discard'); }
  };

  const handleImprove = async (id: number, feedback: string) => {
    if (!feedback.trim()) return;
    try {
      const res = await api.improveProposal(id, feedback);
      showToast('success', 'Proposal improved');
      fetchProposals(filter === 'all' ? undefined : filter);
    } catch (err: any) { showToast('error', err.message || 'Failed to improve'); }
  };

  const handleSubmit = async (id: number) => {
    setSubmitting(prev => ({ ...prev, [id]: true }));
    try {
      const res = await api.submitProposal(id);
      if (res.success) {
        showToast('success', `Proposal submitted via ${res.provider}!`);
        fetchProposals(filter === 'all' ? undefined : filter);
      } else {
        showToast('error', res.error || 'Submission failed');
      }
    } catch (err: any) { showToast('error', err.message || 'Failed to submit'); }
    finally {
      setSubmitting(prev => ({ ...prev, [id]: false }));
    }
  };

  const badgeClass = (status: string) => {
    return `badge badge-${status === 'pending' ? 'pending' : status === 'approved' || status === 'improved' ? 'approved' : status === 'submitted' ? 'submitted' : 'discarded'}`;
  };

  const filtered = proposals.filter(p => filter === 'all' || p.status === filter);

  return (
    <div className="proposals-page">
      <div className="page-header">
        <div>
          <h1 className="page-title">Proposals</h1>
          <p className="page-subtitle">Review, improve, and submit your AI-generated proposals</p>
        </div>
      </div>

      {/* Filter tabs */}
      <div className="filter-tabs" style={{ marginTop: 20 }}>
        {(['all', 'pending', 'approved', 'improved', 'submitted', 'discarded'] as const).map(s => (
          <button
            key={s}
            className={`filter-tab ${filter === s ? 'active' : ''}`}
            onClick={() => setFilter(s)}
          >
            {s.charAt(0).toUpperCase() + s.slice(1)}
            <span className="filter-count">
              {s === 'all' ? proposals.length : proposals.filter(p => p.status === s).length}
            </span>
          </button>
        ))}
      </div>

      {loading ? (
        <div className="loading-state"><div className="spinner"></div><p>Loading proposals...</p></div>
      ) : filtered.length === 0 ? (
        <div className="card">
          <div className="empty-state">
            <div className="empty-state-icon">📝</div>
            <div className="empty-state-title">No proposals</div>
            <div className="empty-state-desc">
              {filter === 'all'
                ? 'Auto-bidder drafts will appear here when it finds matching jobs'
                : `No ${filter} proposals`}
            </div>
          </div>
        </div>
      ) : (
        <div className="proposals-list">
          {filtered.map(p => (
            <ProposalCard
              key={p.id}
              proposal={p}
              onApprove={() => handleApprove(p.id)}
              onDiscard={() => handleDiscard(p.id)}
              onImprove={(feedback) => handleImprove(p.id, feedback)}
              onSubmit={() => handleSubmit(p.id)}
              isSubmitting={submitting[p.id] ?? false}
            />
          ))}
        </div>
      )}

      {toast && <div className={`toast toast-${toast.type}`}>{toast.msg}</div>}
    </div>
  );
}

function ProposalCard({
  proposal,
  onApprove,
  onDiscard,
  onImprove,
  onSubmit,
  isSubmitting,
}: {
  proposal: Proposal;
  onApprove: () => void;
  onDiscard: () => void;
  onImprove: (feedback: string) => void;
  onSubmit: () => void;
  isSubmitting: boolean;
}) {
  const [improveText, setImproveText] = useState('');

  const badgeClass = (status: string) =>
    `badge badge-${status === 'pending' ? 'pending' : status === 'approved' || status === 'improved' ? 'approved' : status === 'submitted' ? 'submitted' : 'discarded'}`;

  return (
    <div className={`proposal-card card ${proposal.status === 'submitted' ? 'submitted-card' : ''}`}>
      {/* Header */}
      <div className="proposal-header">
        <div className="proposal-info">
          <h3 className="proposal-title">{proposal.job_title}</h3>
          <div className="proposal-meta">
            <span className="proposal-budget">{proposal.budget}</span>
            <span className="proposal-skills">{proposal.skills.join(', ')}</span>
          </div>
          <div className="proposal-time">
            Created {new Date(proposal.created_at).toLocaleString()}
            {proposal.submitted_at ? ` · Submitted ${new Date(proposal.submitted_at).toLocaleString()}` : ''}
          </div>
        </div>
        <div className="proposal-actions-header">
          <span className={badgeClass(proposal.status)}>{proposal.status}</span>
        </div>
      </div>

      {/* Job description preview */}
      <div className="proposal-desc-preview">
        {proposal.job_description.slice(0, 300)}...
      </div>

      {/* Screening questions */}
      {proposal.screening_questions && proposal.screening_questions.length > 0 && (
        <div className="screening-section">
          <h4 style={{ fontSize: 13, fontWeight: 600, color: '#8888a0', marginBottom: 8 }}>
            Screening Questions ({proposal.screening_questions.length})
          </h4>
          <div className="screening-qs">
            {proposal.screening_questions.map((q, i) => (
              <div key={i} className="screening-q">
                <span className="screening-q-text">{q.question}</span>
                {proposal.generated_answers[q.question] ? (
                  <span className="screening-a">{proposal.generated_answers[q.question]}</span>
                ) : proposal.status === 'submitted' ? (
                  <span className="screening-a" style={{ color: '#00b894' }}>✓ Answered</span>
                ) : (
                  <span className="screening-a-empty">—</span>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Cover letter */}
      <div className="cover-letter-section">
        <h4 style={{ fontSize: 13, fontWeight: 600, color: '#8888a0', marginBottom: 8 }}>
          Cover Letter
        </h4>
        <div className="cover-letter-text prose">
          {proposal.status === 'improved' && proposal.improved_cover_letter
            ? proposal.improved_cover_letter
            : proposal.cover_letter}
        </div>
      </div>

      {/* Action bar */}
      <div className="proposal-actions">
        {proposal.status === 'pending' && (
          <>
            <button className="btn btn-success btn-sm" onClick={onApprove}>
              ✓ Approve & Submit
            </button>
            <button className="btn btn-secondary btn-sm" onClick={onDiscard}>
              Discard
            </button>
          </>
        )}

        {proposal.status === 'approved' && (
          <>
            <button
              className="btn btn-success btn-sm"
              onClick={onSubmit}
              disabled={isSubmitting}
            >
              {isSubmitting ? (
                <><div className="spinner" style={{ width: 14, height: 14, borderWidth: 2 }}></div> Submitting...</>
              ) : (
                '🚀 Submit to Upwork'
              )}
            </button>
            <button className="btn btn-secondary btn-sm" onClick={onDiscard}>
              Discard
            </button>
          </>
        )}

        {proposal.status === 'improved' && (
          <>
            <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
              <input
                className="input improve-input"
                placeholder="What should be changed?"
                value={improveText}
                onChange={e => setImproveText(e.target.value)}
              />
              <button
                className="btn btn-primary btn-sm"
                onClick={() => {
                  onImprove(improveText);
                  setImproveText('');
                }}
                disabled={!improveText.trim()}
              >
                Improve
              </button>
            </div>
            <button
              className="btn btn-success btn-sm"
              onClick={onSubmit}
              disabled={isSubmitting}
            >
              {isSubmitting ? (
                <><div className="spinner" style={{ width: 14, height: 14, borderWidth: 2 }}></div> Submitting...</>
              ) : (
                '🚀 Submit to Upwork'
              )}
            </button>
          </>
        )}

        {proposal.status === 'submitted' && (
          <div className="submitted-badge">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#00b894" strokeWidth="2">
              <polyline points="20 6 9 17 4 12" />
            </svg>
            Submitted successfully
          </div>
        )}

        {proposal.status === 'discarded' && (
          <div className="discarded-badge">Discarded</div>
        )}
      </div>
    </div>
  );
}
