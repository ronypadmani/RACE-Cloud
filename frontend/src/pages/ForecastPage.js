import React, { useState, useEffect, useCallback } from 'react';
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, ReferenceLine, Dot
} from 'recharts';
import { forecastAPI } from '../services/api';
import './ForecastPage.css';

/* ── Custom Tooltip ──────────────────────────────────────── */
const ChartTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null;
  const d = payload[0]?.payload;
  return (
    <div className="custom-tooltip">
      <p className="tooltip-label">{label}</p>
      <p className="tooltip-value" style={{ color: '#3b82f6' }}>
        Cost: ${Number(d?.cost || 0).toFixed(4)}
      </p>
      {d?.is_anomaly && (
        <p className="tooltip-value" style={{ color: '#ef4444' }}>⚠ Anomaly detected</p>
      )}
    </div>
  );
};

/* ── Anomaly dot renderer ────────────────────────────────── */
const AnomalyDot = (props) => {
  const { cx, cy, payload } = props;
  if (payload?.is_anomaly) {
    return <Dot cx={cx} cy={cy} r={6} fill="#ef4444" stroke="#fff" strokeWidth={2} />;
  }
  return null;
};

export default function ForecastPage() {
  const [prediction, setPrediction] = useState(null);
  const [anomalies, setAnomalies] = useState(null);
  const [budgetStatus, setBudgetStatus] = useState(null);
  const [budgetInput, setBudgetInput] = useState('');
  const [loading, setLoading] = useState(true);
  const [savingBudget, setSavingBudget] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  const fetchData = useCallback(async () => {
    try {
      setLoading(true);
      setError('');
      const [predRes, anomRes, budgetRes] = await Promise.all([
        forecastAPI.getPrediction().catch(() => null),
        forecastAPI.getAnomalies().catch(() => null),
        forecastAPI.getBudgetStatus().catch(() => null),
      ]);

      if (predRes) setPrediction(predRes.data);
      if (anomRes) setAnomalies(anomRes.data);
      if (budgetRes) {
        setBudgetStatus(budgetRes.data);
        if (budgetRes.data?.monthly_limit) {
          setBudgetInput(String(budgetRes.data.monthly_limit));
        }
      }
    } catch {
      setError('Failed to load forecast data. Ensure AWS credentials are configured.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

  const handleSetBudget = async (e) => {
    e.preventDefault();
    const val = parseFloat(budgetInput);
    if (isNaN(val) || val < 0) {
      setError('Enter a valid budget amount');
      return;
    }
    setSavingBudget(true);
    setError('');
    setSuccess('');
    try {
      await forecastAPI.setBudget({ monthly_limit: val });
      setSuccess('Budget updated successfully!');
      const res = await forecastAPI.getBudgetStatus();
      if (res) setBudgetStatus(res.data);
    } catch {
      setError('Failed to save budget');
    } finally {
      setSavingBudget(false);
      setTimeout(() => setSuccess(''), 3000);
    }
  };

  if (loading) {
    return <div className="loading-spinner"><div className="spinner"></div></div>;
  }

  /* ── Derived values ────────────────────────────────────── */
  const predictedCost = prediction?.predicted_monthly_cost || 0;
  const dailyAvg = prediction?.predicted_daily_avg || prediction?.daily_average || 0;
  const confidence = prediction?.confidence || 'low';
  const method = prediction?.method || 'none';
  const trend = prediction?.trend || 'stable';
  const anomalyCount = anomalies?.anomaly_count || 0;
  const chartData = anomalies?.daily_costs_with_threshold || [];
  const threshold = anomalies?.threshold || 0;
  const budgetPct = budgetStatus?.percentage || 0;
  const alertLevel = budgetStatus?.alert_level || 'NONE';
  const hasBudget = budgetStatus?.has_budget || false;

  const trendIcon = trend === 'increasing' ? '📈' : trend === 'decreasing' ? '📉' : '➡️';
  const confidenceColor = confidence === 'high' ? '#10b981' : confidence === 'medium' ? '#f59e0b' : '#94a3b8';

  return (
    <div className="forecast-page">
      {/* ── Header ───────────────────────────────────────── */}
      <div className="forecast-header">
        <div>
          <h1>Cost Forecast & Budget</h1>
          <p className="header-subtitle">Proactive cost prediction, anomaly detection, and budget tracking</p>
        </div>
        <button className="btn btn-primary" onClick={fetchData}>🔄 Refresh</button>
      </div>

      {error && <div className="alert alert-error">{error}</div>}
      {success && <div className="alert alert-success">{success}</div>}

      {/* ── Budget Alert Banner ──────────────────────────── */}
      {hasBudget && alertLevel === 'HIGH' && (
        <div className="budget-alert alert-high">
          <span className="alert-icon">🚨</span>
          <div>
            <strong>Budget Exceeded!</strong>
            <p>{budgetStatus?.message}</p>
          </div>
        </div>
      )}
      {hasBudget && alertLevel === 'MEDIUM' && (
        <div className="budget-alert alert-medium">
          <span className="alert-icon">⚠️</span>
          <div>
            <strong>Budget Warning</strong>
            <p>{budgetStatus?.message}</p>
          </div>
        </div>
      )}

      {/* ── KPI Cards ────────────────────────────────────── */}
      <div className="forecast-kpi-grid">
        {/* Predicted Cost */}
        <div className="kpi-card">
          <div className="kpi-top">
            <div className="kpi-icon icon-purple">🔮</div>
            <div className="kpi-label">Predicted Monthly Cost</div>
          </div>
          <div className="kpi-value">${predictedCost.toFixed(2)}</div>
          <div className="kpi-delta delta-neutral">
            {trendIcon} {trend} trend · {method.replace('_', ' ')}
          </div>
        </div>

        {/* Daily Average */}
        <div className="kpi-card">
          <div className="kpi-top">
            <div className="kpi-icon icon-blue">📊</div>
            <div className="kpi-label">Predicted Daily Avg</div>
          </div>
          <div className="kpi-value">${dailyAvg.toFixed(2)}</div>
          <div className="kpi-delta delta-neutral">
            Based on {prediction?.data_points || 0} data points
          </div>
        </div>

        {/* Confidence */}
        <div className="kpi-card">
          <div className="kpi-top">
            <div className="kpi-icon icon-green">🎯</div>
            <div className="kpi-label">Confidence</div>
          </div>
          <div className="kpi-value" style={{ color: confidenceColor, textTransform: 'capitalize' }}>
            {confidence}
          </div>
          <div className="kpi-delta delta-neutral">
            R² = {prediction?.r_squared?.toFixed(2) || 'N/A'}
          </div>
        </div>

        {/* Anomalies */}
        <div className="kpi-card">
          <div className="kpi-top">
            <div className="kpi-icon icon-red">⚡</div>
            <div className="kpi-label">Cost Anomalies</div>
          </div>
          <div className="kpi-value" style={{ color: anomalyCount > 0 ? '#ef4444' : '#10b981' }}>
            {anomalyCount}
          </div>
          <div className="kpi-delta delta-neutral">
            in last 30 days
          </div>
        </div>
      </div>

      {/* ── Budget Section ───────────────────────────────── */}
      <div className="forecast-row">
        <div className="card budget-card">
          <div className="card-header">
            <div>
              <div className="card-title">💰 Monthly Budget</div>
              <div className="card-subtitle">Set your spending limit and track against predictions</div>
            </div>
          </div>

          <form className="budget-form" onSubmit={handleSetBudget}>
            <div className="budget-input-row">
              <span className="input-prefix">$</span>
              <input
                type="number"
                min="0"
                step="0.01"
                value={budgetInput}
                onChange={e => setBudgetInput(e.target.value)}
                placeholder="Enter monthly budget"
                className="budget-input"
              />
              <button type="submit" className="btn btn-primary" disabled={savingBudget}>
                {savingBudget ? 'Saving…' : 'Set Budget'}
              </button>
            </div>
          </form>

          {hasBudget && (
            <div className="budget-progress-section">
              <div className="budget-progress-header">
                <span>Predicted: ${predictedCost.toFixed(2)}</span>
                <span>Budget: ${budgetStatus?.monthly_limit?.toFixed(2)}</span>
              </div>
              <div className="budget-progress-track">
                <div
                  className={`budget-progress-fill ${alertLevel === 'HIGH' ? 'fill-danger' : alertLevel === 'MEDIUM' ? 'fill-warning' : 'fill-ok'}`}
                  style={{ width: `${Math.min(budgetPct, 100)}%` }}
                />
              </div>
              <div className="budget-progress-footer">
                <span className={`budget-pct ${alertLevel === 'HIGH' ? 'pct-danger' : alertLevel === 'MEDIUM' ? 'pct-warning' : 'pct-ok'}`}>
                  {budgetPct.toFixed(1)}% of budget
                </span>
                {budgetStatus?.remaining != null && (
                  <span className="budget-remaining">
                    {budgetStatus.remaining >= 0
                      ? `$${budgetStatus.remaining.toFixed(2)} remaining`
                      : `$${Math.abs(budgetStatus.remaining).toFixed(2)} over budget`}
                  </span>
                )}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* ── Anomaly Chart ────────────────────────────────── */}
      <div className="card chart-card">
        <div className="card-header">
          <div>
            <div className="card-title">⚡ Daily Cost &amp; Anomalies</div>
            <div className="card-subtitle">
              Last 30 days · Threshold: ${threshold.toFixed(4)} · {anomalyCount} anomal{anomalyCount === 1 ? 'y' : 'ies'}
            </div>
          </div>
        </div>
        {chartData.length > 0 ? (
          <ResponsiveContainer width="100%" height={320}>
            <AreaChart data={chartData}>
              <defs>
                <linearGradient id="gradForecast" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.15} />
                  <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" vertical={false} />
              <XAxis
                dataKey="date"
                tick={{ fontSize: 11, fill: '#94a3b8' }}
                tickFormatter={v => v.substring(5)}
                axisLine={false} tickLine={false}
              />
              <YAxis
                tick={{ fontSize: 11, fill: '#94a3b8' }}
                tickFormatter={v => `$${v}`}
                axisLine={false} tickLine={false} width={55}
              />
              <Tooltip content={<ChartTooltip />} />
              <ReferenceLine
                y={threshold}
                stroke="#ef4444"
                strokeDasharray="6 4"
                label={{ value: 'Threshold', position: 'insideTopRight', fill: '#ef4444', fontSize: 11 }}
              />
              <Area
                type="monotone"
                dataKey="cost"
                name="Daily Cost"
                stroke="#3b82f6"
                fill="url(#gradForecast)"
                strokeWidth={2.5}
                dot={<AnomalyDot />}
                activeDot={{ r: 5, stroke: '#fff', strokeWidth: 2 }}
              />
            </AreaChart>
          </ResponsiveContainer>
        ) : (
          <div className="chart-empty">No cost data available for anomaly detection</div>
        )}
      </div>

      {/* ── Anomaly Table ────────────────────────────────── */}
      {anomalies?.anomalies?.length > 0 && (
        <div className="card">
          <div className="card-header">
            <div>
              <div className="card-title">🔍 Detected Anomalies</div>
              <div className="card-subtitle">{anomalyCount} unusual spending day{anomalyCount !== 1 ? 's' : ''}</div>
            </div>
          </div>
          <div className="table-container">
            <table className="anomaly-table">
              <thead>
                <tr>
                  <th>Date</th>
                  <th>Actual Cost</th>
                  <th>Expected</th>
                  <th>Deviation</th>
                  <th>Severity</th>
                </tr>
              </thead>
              <tbody>
                {anomalies.anomalies.map((a, i) => (
                  <tr key={i}>
                    <td>{a.date}</td>
                    <td className="cost-cell">${a.cost.toFixed(4)}</td>
                    <td>${a.expected.toFixed(4)}</td>
                    <td>{a.deviation.toFixed(2)}σ</td>
                    <td>
                      <span className={`badge badge-${a.severity.toLowerCase()}`}>{a.severity}</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
