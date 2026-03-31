import React, { useState, useEffect } from 'react';
import { analysisAPI } from '../services/api';
import './RecommendationsPage.css';

export default function RecommendationsPage() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [analyzing, setAnalyzing] = useState(false);
  const [filter, setFilter] = useState('ALL');

  const fetchData = () => {
    analysisAPI.getRecommendations()
      .then(res => setData(res.data))
      .catch(() => {})
      .finally(() => setLoading(false));
  };

  useEffect(() => { fetchData(); }, []);

  const runAnalysis = async () => {
    setAnalyzing(true);
    try {
      await analysisAPI.runAnalysis();
      fetchData();
    } catch {
    } finally {
      setAnalyzing(false);
    }
  };

  const dismissRec = async (id) => {
    try {
      await analysisAPI.dismissRecommendation(id);
      fetchData();
    } catch {}
  };

  if (loading) return <div className="loading-spinner"><div className="spinner"></div></div>;

  const recommendations = data?.recommendations || [];
  const filtered = filter === 'ALL'
    ? recommendations
    : recommendations.filter(r => r.severity === filter);

  const severityBreakdown = data?.severity_breakdown || { high: 0, medium: 0, low: 0 };

  return (
    <div className="recommendations-page">
      <div className="page-header" style={{ display: 'flex', justifyContent: 'space-between' }}>
        <div>
          <h1>💡 Optimization Recommendations</h1>
          <p>{data?.total_count || 0} issues found — ${(data?.total_estimated_savings || 0).toFixed(2)}/mo potential savings</p>
        </div>
        <button className="btn btn-primary" onClick={runAnalysis} disabled={analyzing}>
          {analyzing ? '⏳ Analyzing...' : '🔄 Re-run Analysis'}
        </button>
      </div>

      {/* Severity Filter */}
      <div className="filter-bar">
        <button
          className={`filter-btn ${filter === 'ALL' ? 'active' : ''}`}
          onClick={() => setFilter('ALL')}
        >
          All ({recommendations.length})
        </button>
        <button
          className={`filter-btn high ${filter === 'HIGH' ? 'active' : ''}`}
          onClick={() => setFilter('HIGH')}
        >
          🔴 High ({severityBreakdown.high})
        </button>
        <button
          className={`filter-btn medium ${filter === 'MEDIUM' ? 'active' : ''}`}
          onClick={() => setFilter('MEDIUM')}
        >
          🟡 Medium ({severityBreakdown.medium})
        </button>
        <button
          className={`filter-btn low ${filter === 'LOW' ? 'active' : ''}`}
          onClick={() => setFilter('LOW')}
        >
          🔵 Low ({severityBreakdown.low})
        </button>
      </div>

      {/* Recommendation Cards */}
      {filtered.length === 0 ? (
        <div className="card" style={{ textAlign: 'center', padding: 60 }}>
          <div style={{ fontSize: 48, marginBottom: 16 }}>✅</div>
          <h3>No optimization issues found</h3>
          <p style={{ color: 'var(--gray-500)', marginTop: 8 }}>
            {recommendations.length === 0
              ? 'Run an analysis to check for optimization opportunities.'
              : 'No issues match the selected filter.'}
          </p>
        </div>
      ) : (
        <div className="rec-list">
          {filtered.map((rec) => (
            <div key={rec.id} className={`card rec-card severity-${rec.severity.toLowerCase()}`}>
              <div className="rec-header">
                <div className="rec-meta">
                  <span className={`badge badge-${rec.severity.toLowerCase()}`}>{rec.severity}</span>
                  <span className="rec-type">{rec.resource_type}</span>
                  <code className="rec-resource">{rec.resource_id}</code>
                </div>
                <div className="rec-savings">${rec.estimated_savings.toFixed(2)}/mo</div>
              </div>
              <p className="rec-text">{rec.recommendation_text}</p>
              <div className="rec-footer">
                <span className="rec-rule">{rec.rule_id}</span>
                <button className="btn btn-secondary btn-sm" onClick={() => dismissRec(rec.id)}>
                  Dismiss
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
