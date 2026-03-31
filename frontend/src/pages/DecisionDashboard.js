import React, { useState, useEffect, useCallback } from 'react';
import { decisionAPI, analysisAPI, demoAPI } from '../services/api';
import './DecisionDashboard.css';

const RESOURCE_ICONS = {
  EC2: '🖥️', EBS: '💾', S3: '🪣', RDS: '🗄️', EIP: '🌐', COST: '💰',
};

const EFFORT_COLORS = {
  LOW: 'effort-low', MEDIUM: 'effort-medium', HIGH: 'effort-high',
};

const SCAL_COLORS = {
  Low: '#f59e0b', Medium: '#3b82f6', High: '#22c55e', 'Very High': '#8b5cf6',
};

const COMPLEXITY_COLORS = {
  Simple: '#22c55e', Moderate: '#3b82f6', Complex: '#f59e0b', Enterprise: '#8b5cf6',
};

const PRIORITIES = [
  { value: 'cheap', label: '💰 Cost', desc: 'Minimize spending' },
  { value: 'balanced', label: '⚖️ Balanced', desc: 'Best trade-off' },
  { value: 'performance', label: '🚀 Performance', desc: 'Max scalability' },
];

const AI_PROVIDER_LABEL = {
  ollama: '🟢 Local AI (LLaMA)',
  gemini: '🔵 Gemini API',
  cached: '⚡ Cached',
  unknown: '☁️ AI',
};

export default function DecisionDashboard() {
  /* ── Top Actions state ────────────────────────────────── */
  const [plan, setPlan] = useState(null);
  const [loading, setLoading] = useState(true);
  const [analyzing, setAnalyzing] = useState(false);
  const [expertMode, setExpertMode] = useState(false);
  const [expandedIdx, setExpandedIdx] = useState(null);
  const [actioned, setActioned] = useState({});

  /* ── Demo Mode state ──────────────────────────────────── */
  const [demoMode, setDemoMode] = useState(false);
  const [demoScenario, setDemoScenario] = useState('');
  const [demoScenarios, setDemoScenarios] = useState([]);

  /* ── AI Suggestion state ──────────────────────────────── */
  const [aiInput, setAiInput] = useState('');
  const [aiBudget, setAiBudget] = useState(100);
  const [aiPriority, setAiPriority] = useState('balanced');
  const [aiResult, setAiResult] = useState(null);
  const [aiLoading, setAiLoading] = useState(false);
  const [aiError, setAiError] = useState('');

  const fetchPlan = useCallback(() => {
    setLoading(true);
    decisionAPI.getPlan()
      .then(res => setPlan(res.data))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => { fetchPlan(); }, [fetchPlan]);

  useEffect(() => {
    demoAPI.getStatus()
      .then(res => {
        setDemoMode(res.data.demo_mode);
        setDemoScenario(res.data.current_scenario || '');
        setDemoScenarios(res.data.available_scenarios || []);
      })
      .catch(() => {});
  }, []);

  const switchScenario = async (scenario) => {
    setDemoScenario(scenario);
    setAnalyzing(true);
    try {
      await demoAPI.switchScenario(scenario);
      await analysisAPI.runAnalysis();
      fetchPlan();
    } catch {} finally { setAnalyzing(false); }
  };

  const runAnalysis = async () => {
    setAnalyzing(true);
    try {
      await analysisAPI.runAnalysis();
      fetchPlan();
    } catch {} finally { setAnalyzing(false); }
  };

  const recordAction = async (action, actionType) => {
    try {
      await decisionAPI.recordBehavior({
        rule_id: action.rule_id,
        recommendation_id: action.recommendation_id,
        action_type: actionType,
      });
      setActioned(prev => ({ ...prev, [action.recommendation_id]: actionType }));
      if (actionType === 'dismissed') setTimeout(fetchPlan, 400);
    } catch {}
  };

  const generateAI = async () => {
    if (!aiInput.trim()) return;
    setAiLoading(true);
    setAiError('');
    setAiResult(null);
    try {
      const res = await decisionAPI.aiSuggest({
        user_input: aiInput.trim(),
        budget: aiBudget,
        priority: aiPriority,
      });
      setAiResult(res.data);
    } catch (err) {
      const msg = err.response?.data?.error || 'Failed to generate suggestion. Please try again.';
      setAiError(msg);
    } finally { setAiLoading(false); }
  };

  if (loading) {
    return (
      <div className="decision-skeleton">
        <div className="skel-header" />
        <div className="skel-row"><div className="skel-card" /><div className="skel-card" /><div className="skel-card" /></div>
        <div className="skel-block" />
      </div>
    );
  }

  const actions = plan?.top_actions || [];
  const topActions = actions.slice(0, 3);
  const otherActions = actions.slice(3);
  const totalSavings = plan?.total_savings || 0;

  const ai = aiResult?.ai_suggestion;
  const costOpts = aiResult?.cost_options;
  const regionComp = aiResult?.region_comparison;
  const finalRec = aiResult?.final_recommendation;
  const confidence = aiResult?.confidence;
  const aiProvider = aiResult?.ai_provider || 'unknown';
  const archLayers = ai?.architecture_layers || [];

  return (
    <div className="decision-page">

      {/* ════════════════════════════════════════════════════════
          HEADER
          ════════════════════════════════════════════════════════ */}
      <div className="decision-header">
        <div>
          <h1>🧠 AI Decision Intelligence</h1>
          <p className="decision-subtitle">
            AI-powered cloud architect — generate architectures, compare costs, and optimize your AWS.
            {demoMode && <span className="demo-badge">🎭 Demo Mode Active</span>}
          </p>
        </div>
        <div className="decision-header-actions">
          {demoMode && demoScenarios.length > 0 && (
            <select
              className="demo-scenario-select"
              value={demoScenario}
              onChange={e => switchScenario(e.target.value)}
              disabled={analyzing}
            >
              {demoScenarios.map(s => (
                <option key={s} value={s}>
                  {s.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())}
                </option>
              ))}
            </select>
          )}
          <div className="mode-toggle" title={expertMode ? 'Switch to Simple mode' : 'Switch to Expert mode'}>
            <span className={!expertMode ? 'mode-active' : ''}>Simple</span>
            <label className="toggle-switch">
              <input type="checkbox" checked={expertMode} onChange={() => setExpertMode(!expertMode)} />
              <span className="toggle-slider" />
            </label>
            <span className={expertMode ? 'mode-active' : ''}>Expert</span>
          </div>
          <button className="btn btn-primary" onClick={runAnalysis} disabled={analyzing}>
            {analyzing ? '⏳ Analyzing...' : '🔄 Refresh'}
          </button>
        </div>
      </div>

      {/* ════════════════════════════════════════════════════════
          SECTION 1 — TOP ACTIONS (existing recommendations)
          ════════════════════════════════════════════════════════ */}
      {actions.length > 0 && (
        <div className="savings-banner">
          <div className="savings-banner-icon">💵</div>
          <div>
            <div className="savings-amount">${totalSavings.toFixed(2)}<span>/mo</span></div>
            <div className="savings-label">
              potential savings across {actions.length} action{actions.length !== 1 ? 's' : ''}
            </div>
          </div>
          <div className="savings-bar-wrapper">
            <div className="savings-bar">
              {topActions.map((a, i) => {
                const pct = totalSavings > 0 ? (a.estimated_savings / totalSavings) * 100 : 0;
                return (
                  <div key={i} className={`savings-segment seg-${i}`}
                    style={{ width: `${pct}%` }}
                    title={`${a.title}: $${a.estimated_savings.toFixed(2)}/mo`} />
                );
              })}
            </div>
          </div>
        </div>
      )}

      {actions.length > 0 ? (
        <>
          <h2 className="section-title">🎯 Top Actions</h2>
          <div className="top-actions-grid">
            {topActions.map((action, idx) => {
              const done = actioned[action.recommendation_id];
              return (
                <div key={idx} className={`top-action-card rank-${idx} ${done ? 'actioned' : ''}`}>
                  {idx === 0 && <div className="card-ribbon">#1 Priority</div>}
                  <div className="ta-icon">{RESOURCE_ICONS[action.resource_type] || '📦'}</div>
                  <h3 className="ta-title">{action.title}</h3>
                  <code className="ta-resource">{action.resource_id}</code>
                  <div className="ta-metrics">
                    <div className="ta-metric">
                      <span className="ta-metric-value">${action.estimated_savings.toFixed(2)}</span>
                      <span className="ta-metric-label">savings/mo</span>
                    </div>
                    <div className="ta-metric">
                      <span className="ta-metric-value">{action.confidence}%</span>
                      <span className="ta-metric-label">confidence</span>
                    </div>
                    <div className="ta-metric">
                      <span className={`effort-badge ${EFFORT_COLORS[action.effort]}`}>{action.effort}</span>
                      <span className="ta-metric-label">effort</span>
                    </div>
                  </div>
                  <div className="confidence-track">
                    <div className="confidence-fill" style={{ width: `${action.confidence}%` }} />
                  </div>
                  <p className="ta-explanation">
                    {expertMode ? action.explanation_expert : action.explanation_beginner}
                  </p>
                  {!done ? (
                    <div className="ta-buttons">
                      <button className="btn btn-primary btn-sm" onClick={() => recordAction(action, 'applied')}>✅ I did this</button>
                      <button className="btn btn-secondary btn-sm" onClick={() => recordAction(action, 'dismissed')}>✖ Dismiss</button>
                    </div>
                  ) : (
                    <div className="ta-done-label">{done === 'applied' ? '✅ Marked as done' : '✖ Dismissed'}</div>
                  )}
                </div>
              );
            })}
          </div>

          {otherActions.length > 0 && (
            <>
              <h2 className="section-title" style={{ marginTop: 32 }}>📋 More Actions</h2>
              <div className="other-actions-list">
                {otherActions.map((action, idx) => {
                  const globalIdx = idx + 3;
                  const isExpanded = expandedIdx === globalIdx;
                  const done = actioned[action.recommendation_id];
                  return (
                    <div key={idx} className={`other-action-row ${done ? 'actioned' : ''}`}>
                      <div className="oar-left">
                        <span className="oar-rank">#{globalIdx + 1}</span>
                        <span className="oar-icon">{RESOURCE_ICONS[action.resource_type] || '📦'}</span>
                        <div className="oar-info">
                          <span className="oar-title">{action.title}</span>
                          <code className="oar-resource">{action.resource_id}</code>
                        </div>
                      </div>
                      <div className="oar-right">
                        <span className={`effort-badge ${EFFORT_COLORS[action.effort]}`}>{action.effort}</span>
                        <span className="oar-savings">${action.estimated_savings.toFixed(2)}/mo</span>
                        <button className="btn btn-ghost btn-sm"
                          onClick={() => setExpandedIdx(isExpanded ? null : globalIdx)}>
                          {isExpanded ? '▲ Less' : '▼ Details'}
                        </button>
                        {!done && (
                          <>
                            <button className="btn btn-primary btn-sm" onClick={() => recordAction(action, 'applied')}>✅</button>
                            <button className="btn btn-secondary btn-sm" onClick={() => recordAction(action, 'dismissed')}>✖</button>
                          </>
                        )}
                        {done && <span className="oar-done">{done === 'applied' ? '✅' : '✖'}</span>}
                      </div>
                      {isExpanded && (
                        <div className="oar-expand">
                          {expertMode ? action.explanation_expert : action.explanation_beginner}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </>
          )}
        </>
      ) : (
        <div className="card empty-card">
          <div className="empty-icon">✅</div>
          <h3>No actions needed right now</h3>
          <p>Run an analysis to generate your action plan, or try the AI advisor below.</p>
        </div>
      )}

      {/* ════════════════════════════════════════════════════════
          SECTION 2 — AI INPUT
          ════════════════════════════════════════════════════════ */}
      <div className="ai-section">
        <h2 className="section-title">✨ AI Cloud Architect</h2>
        <p className="ai-subtitle">
          Describe your project and the AI will deeply understand your requirements, generate the optimal AWS architecture, and calculate real-time costs.
        </p>

        <div className="ai-input-card">
          <textarea
            className="ai-textarea"
            placeholder="e.g. I want to build a real-time chat application with user authentication, file sharing, and push notifications for 10,000 daily active users..."
            value={aiInput}
            onChange={e => setAiInput(e.target.value)}
            rows={4}
          />

          <div className="ai-controls">
            <div className="ai-control">
              <label className="ai-label">Monthly Budget</label>
              <div className="ai-budget-row">
                <input type="range" min={10} max={1000} step={10}
                  value={aiBudget} onChange={e => setAiBudget(Number(e.target.value))}
                  className="ai-slider" />
                <span className="ai-budget-value">${aiBudget}</span>
              </div>
            </div>

            <div className="ai-control">
              <label className="ai-label">Priority</label>
              <div className="ai-priority-row">
                {PRIORITIES.map(p => (
                  <button key={p.value}
                    className={`ai-priority-btn ${aiPriority === p.value ? 'active' : ''}`}
                    onClick={() => setAiPriority(p.value)}
                    title={p.desc}>
                    {p.label}
                  </button>
                ))}
              </div>
            </div>

            <button className="btn btn-primary ai-generate-btn"
              onClick={generateAI}
              disabled={aiLoading || !aiInput.trim()}>
              {aiLoading ? '🤖 AI is thinking...' : '✨ Generate with AI'}
            </button>
          </div>
        </div>

        {aiError && <div className="ai-error">{aiError}</div>}

        {/* ── Loading Animation ─────────────────────────────── */}
        {aiLoading && (
          <div className="ai-thinking">
            <div className="ai-thinking-brain">🧠</div>
            <div className="ai-thinking-dots"><span /><span /><span /></div>
            <p>AI is analyzing your requirements...</p>
            <p className="ai-thinking-sub">Understanding project scope, generating architecture, calculating costs across regions</p>
          </div>
        )}

        {/* ════════════════════════════════════════════════════════
            SECTION 3 — AI ARCHITECTURE OUTPUT
            ════════════════════════════════════════════════════════ */}
        {aiResult && !aiLoading && (
          <div className="ai-results">

            {/* Meta bar */}
            <div className="ai-meta-bar">
              <div className="ai-meta-item">
                <span className="ai-meta-label">Project Type</span>
                <span className="ai-meta-value ai-project-type">{ai?.project_type}</span>
              </div>
              <div className="ai-meta-item">
                <span className="ai-meta-label">Confidence</span>
                <span className="ai-meta-value">{confidence}%</span>
              </div>
              <div className="ai-meta-item">
                <span className="ai-meta-label">Complexity</span>
                <span className="ai-meta-value" style={{
                  color: COMPLEXITY_COLORS[ai?.complexity] || '#6b7280'
                }}>{ai?.complexity}</span>
              </div>
              <div className="ai-meta-item">
                <span className="ai-meta-label">Pricing</span>
                <span className="ai-meta-value">
                  {aiResult.pricing_source === 'live' ? '🟢 Live AWS' : '🔵 Estimated'}
                </span>
              </div>
              <div className="ai-meta-item">
                <span className="ai-meta-label">AI Engine</span>
                <span className="ai-meta-value">{AI_PROVIDER_LABEL[aiProvider] || aiProvider}</span>
              </div>
              {aiResult.cached && (
                <span className="ai-cached-badge" title="Result served from 24h cache">⚡ Cached</span>
              )}
            </div>

            {/* Architecture card */}
            <div className="ai-arch-card">
              <h3 className="ai-arch-title">🏗️ Suggested Architecture</h3>

              {/* Architecture layers */}
              {archLayers.length > 0 ? (
                <div className="ai-arch-layers">
                  {archLayers.map((layer, i) => (
                    <div key={i} className="ai-arch-layer">
                      <span className="ai-layer-arrow">{i > 0 ? '→' : ''}</span>
                      <span className="ai-layer-text">{layer}</span>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="ai-arch-desc">{ai?.architecture}</p>
              )}

              {expertMode && ai?.reasoning && (
                <div className="ai-reasoning">
                  <strong>💡 Reasoning:</strong> {ai.reasoning}
                </div>
              )}

              {/* Services */}
              <div className="ai-services-row">
                {ai?.services?.map((svc, i) => (
                  <span key={i} className="ai-service-chip" title={svc}>
                    {ai.service_icons?.[svc] || '☁️'} {svc}
                  </span>
                ))}
              </div>

              {/* Scalability + Estimated Usage */}
              <div className="ai-info-row">
                <div className="ai-info-item">
                  <span className="ai-label">Scalability</span>
                  <span className="ai-scal-badge" style={{
                    background: (SCAL_COLORS[ai?.scalability] || '#6b7280') + '18',
                    color: SCAL_COLORS[ai?.scalability] || '#6b7280',
                  }}>{ai?.scalability}</span>
                </div>
                {expertMode && ai?.estimated_usage && (
                  <>
                    <div className="ai-info-item">
                      <span className="ai-label">Compute</span>
                      <span className="ai-info-value">{ai.estimated_usage.compute_hours?.toLocaleString()} hrs/mo</span>
                    </div>
                    <div className="ai-info-item">
                      <span className="ai-label">Storage</span>
                      <span className="ai-info-value">{ai.estimated_usage.storage_gb?.toLocaleString()} GB</span>
                    </div>
                    <div className="ai-info-item">
                      <span className="ai-label">Requests</span>
                      <span className="ai-info-value">{ai.estimated_usage.requests?.toLocaleString()}/mo</span>
                    </div>
                  </>
                )}
              </div>
            </div>

            {/* ════════════════════════════════════════════════════
                SECTION 4 — 3 COST OPTION CARDS
                ════════════════════════════════════════════════════ */}
            <h3 className="section-title" style={{ marginTop: 24 }}>💰 Cost Options</h3>
            {costOpts && costOpts.every(o => o.estimated_cost > aiBudget) && (
              <div className="ai-budget-warning">
                ⚠️ All options exceed your ${aiBudget} budget. Consider simplifying requirements.
              </div>
            )}
            <div className="ai-cost-grid">
              {costOpts?.map((opt, i) => {
                const isWithin = opt.estimated_cost <= aiBudget;
                const scalColor = SCAL_COLORS[opt.scalability] || '#6b7280';
                const isHighlighted = opt.type?.toLowerCase() === aiPriority;
                return (
                  <div key={i} className={`ai-cost-card tier-${opt.type?.toLowerCase()} ${isHighlighted ? 'highlighted' : ''}`}>
                    {isHighlighted && <div className="cost-card-ribbon">⭐ Recommended</div>}
                    <div className="ai-cost-header">
                      <span className="ai-cost-icon">{opt.icon}</span>
                      <h4 className="ai-cost-label">{opt.label}</h4>
                    </div>
                    <div className="ai-cost-price">
                      ${opt.estimated_cost?.toFixed(2)}<span>/mo</span>
                    </div>
                    {isWithin
                      ? <div className="ai-within-budget">✓ Within budget</div>
                      : <div className="ai-over-budget">Over budget</div>
                    }
                    <div className="ai-cost-detail">
                      <span className="ai-cost-detail-label">Region</span>
                      <span className="ai-cost-detail-value">{opt.region}</span>
                    </div>
                    <div className="ai-cost-detail">
                      <span className="ai-cost-detail-label">Scalability</span>
                      <span className="ai-scal-badge sm" style={{ background: scalColor + '18', color: scalColor }}>
                        {opt.scalability}
                      </span>
                    </div>
                    <div className="ai-cost-detail">
                      <span className="ai-cost-detail-label">Services</span>
                      <span className="ai-cost-detail-value">{opt.services?.length || 0}</span>
                    </div>

                    {/* Per-service breakdown (expert mode) */}
                    {expertMode && opt.breakdown && (
                      <div className="ai-breakdown">
                        {Object.entries(opt.breakdown).map(([svc, cost]) => (
                          <div key={svc} className="ai-breakdown-row">
                            <span>{ai?.service_icons?.[svc] || '☁️'} {svc}</span>
                            <span>${cost.toFixed(2)}</span>
                          </div>
                        ))}
                      </div>
                    )}

                    <p className="ai-cost-desc">{opt.description}</p>
                  </div>
                );
              })}
            </div>

            {/* Region comparison table */}
            {expertMode && regionComp && regionComp.length > 0 && (
              <div className="ai-region-compare">
                <h4>🌍 Region Comparison</h4>
                <table className="ai-region-table">
                  <thead>
                    <tr>
                      <th>Region</th>
                      <th>💰 Cheap</th>
                      <th>⚖️ Balanced</th>
                      <th>🚀 Performance</th>
                    </tr>
                  </thead>
                  <tbody>
                    {regionComp.map((r, i) => (
                      <tr key={i}>
                        <td className="ai-region-name">{r.region}</td>
                        <td>${r.CHEAP?.toFixed(2)}</td>
                        <td>${r.BALANCED?.toFixed(2)}</td>
                        <td>${r.PERFORMANCE?.toFixed(2)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {/* ════════════════════════════════════════════════════
                SECTION 5 — FINAL RECOMMENDATION
                ════════════════════════════════════════════════════ */}
            {finalRec && (
              <div className="ai-final-rec">
                <div className="ai-final-rec-icon">🎯</div>
                <div>
                  <h4>Final Recommendation</h4>
                  <p>{finalRec}</p>
                </div>
              </div>
            )}

            {/* Top Actions from existing recommendations (merged) */}
            {aiResult.top_actions && aiResult.top_actions.length > 0 && (
              <div className="ai-existing-actions">
                <h4>📋 Active Optimization Actions</h4>
                <div className="ai-existing-actions-list">
                  {aiResult.top_actions.map((a, i) => (
                    <div key={i} className="ai-existing-action-row">
                      <span className="ai-ea-icon">{RESOURCE_ICONS[a.resource_type] || '📦'}</span>
                      <span className="ai-ea-title">{a.title}</span>
                      <span className="ai-ea-savings">${a.estimated_savings?.toFixed(2)}/mo</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
