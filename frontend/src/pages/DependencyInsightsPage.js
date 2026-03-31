import React, { useState, useEffect, useCallback } from 'react';
import { dependencyAPI } from '../services/api';
import './DependencyInsightsPage.css';

export default function DependencyInsightsPage() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('ALL');
  const [simulating, setSimulating] = useState({});   // keyed by chain index
  const [simResults, setSimResults] = useState({});    // keyed by chain index

  const fetchChains = useCallback(() => {
    setLoading(true);
    dependencyAPI.getChains()
      .then(res => setData(res.data))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => { fetchChains(); }, [fetchChains]);

  const simulateChain = async (chain, idx) => {
    setSimulating(prev => ({ ...prev, [idx]: true }));
    try {
      const res = await dependencyAPI.simulateChain(chain);
      setSimResults(prev => ({ ...prev, [idx]: res.data }));
    } catch {
      setSimResults(prev => ({ ...prev, [idx]: { error: 'Simulation failed' } }));
    } finally {
      setSimulating(prev => ({ ...prev, [idx]: false }));
    }
  };

  if (loading) {
    return <div className="loading-spinner"><div className="spinner"></div></div>;
  }

  const chains = data?.chains || [];
  const filtered = filter === 'ALL'
    ? chains
    : chains.filter(c => c.impact === filter);

  const impactBreakdown = data?.impact_breakdown || { high: 0, medium: 0, low: 0 };

  const chainTypeLabel = (type) => {
    const labels = {
      DEAD_INFRASTRUCTURE: '💀 Dead Infrastructure',
      ORPHAN_VOLUME: '📦 Orphan Volume',
      IDLE_EIP: '🌐 Idle Elastic IP',
    };
    return labels[type] || type;
  };

  const resourceIcon = (type) => {
    const icons = { EC2: '🖥️', EBS: '💾', EIP: '🌐' };
    return icons[type] || '❓';
  };

  return (
    <div className="dependency-page">
      {/* Header */}
      <div className="page-header" style={{ display: 'flex', justifyContent: 'space-between' }}>
        <div>
          <h1>🔗 Dependency Insights</h1>
          <p>
            {data?.total_chains || 0} waste chains detected — ${(data?.total_waste || 0).toFixed(2)}/mo total waste
          </p>
        </div>
        <button className="btn btn-primary" onClick={fetchChains} disabled={loading}>
          🔄 Refresh
        </button>
      </div>

      {/* Impact filter */}
      <div className="filter-bar">
        <button className={`filter-btn ${filter === 'ALL' ? 'active' : ''}`} onClick={() => setFilter('ALL')}>
          All ({chains.length})
        </button>
        <button className={`filter-btn high ${filter === 'HIGH' ? 'active' : ''}`} onClick={() => setFilter('HIGH')}>
          🔴 High ({impactBreakdown.high})
        </button>
        <button className={`filter-btn medium ${filter === 'MEDIUM' ? 'active' : ''}`} onClick={() => setFilter('MEDIUM')}>
          🟡 Medium ({impactBreakdown.medium})
        </button>
        <button className={`filter-btn low ${filter === 'LOW' ? 'active' : ''}`} onClick={() => setFilter('LOW')}>
          🔵 Low ({impactBreakdown.low})
        </button>
      </div>

      {/* Chain cards */}
      {filtered.length === 0 ? (
        <div className="card" style={{ textAlign: 'center', padding: 60 }}>
          <div style={{ fontSize: 48, marginBottom: 16 }}>✅</div>
          <h3>No waste chains detected</h3>
          <p style={{ color: 'var(--gray-500)', marginTop: 8 }}>
            {chains.length === 0
              ? 'Your infrastructure looks clean — no cross-service waste found.'
              : 'No chains match the selected filter.'}
          </p>
        </div>
      ) : (
        <div className="chain-list">
          {filtered.map((chain, idx) => {
            const sim = simResults[idx];
            return (
              <div key={idx} className={`card chain-card impact-${chain.impact.toLowerCase()}`}>
                {/* Chain header */}
                <div className="chain-header">
                  <div className="chain-meta">
                    <span className={`badge badge-${chain.impact.toLowerCase()}`}>{chain.impact}</span>
                    <span className="chain-type">{chainTypeLabel(chain.chain_type)}</span>
                  </div>
                  <div className="chain-waste">${chain.total_waste.toFixed(2)}/mo</div>
                </div>

                <p className="chain-trigger">{chain.trigger}</p>

                {/* Resources in chain */}
                <div className="chain-resources">
                  {chain.resources.map((res, ri) => (
                    <div key={ri} className="resource-chip">
                      <span className="resource-icon">{resourceIcon(res.type)}</span>
                      <span className="resource-type">{res.type}</span>
                      <code className="resource-id">{res.id}</code>
                      {res.detail && <span className="resource-detail">{res.detail}</span>}
                    </div>
                  ))}
                </div>

                {/* Recommendation */}
                <p className="chain-recommendation">{chain.recommendation}</p>

                {/* Simulate button + result */}
                <div className="chain-actions">
                  <button
                    className="btn btn-secondary btn-sm"
                    disabled={simulating[idx]}
                    onClick={() => simulateChain(chain, idx)}
                  >
                    {simulating[idx] ? '⏳ Simulating...' : '🧪 Simulate Fix'}
                  </button>

                  {sim && !sim.error && (
                    <div className="sim-result">
                      <div className="sim-box current">
                        <span className="sim-label">Current</span>
                        <span className="sim-value">${sim.current_cost.toFixed(2)}</span>
                      </div>
                      <span className="sim-arrow">→</span>
                      <div className="sim-box projected">
                        <span className="sim-label">After Fix</span>
                        <span className="sim-value">${sim.new_cost.toFixed(2)}</span>
                      </div>
                      <div className="sim-box savings">
                        <span className="sim-label">Savings</span>
                        <span className="sim-value">${sim.savings.toFixed(2)}/mo</span>
                      </div>
                    </div>
                  )}
                  {sim && sim.error && (
                    <span className="sim-error">{sim.error}</span>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
