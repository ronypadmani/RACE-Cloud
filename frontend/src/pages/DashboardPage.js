import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, AreaChart, Area
} from 'recharts';
import { awsAPI, analysisAPI, forecastAPI } from '../services/api';
import dashboardEvents from '../services/dashboardEvents';
import './DashboardPage.css';

const COLORS = ['#3b82f6', '#8b5cf6', '#10b981', '#f59e0b', '#ef4444', '#06b6d4', '#ec4899', '#6366f1'];

/* ── Custom Recharts Tooltip ─────────────────────────────── */
const CustomTooltip = ({ active, payload, label, prefix = '$' }) => {
  if (!active || !payload?.length) return null;
  return (
    <div className="custom-tooltip">
      <p className="tooltip-label">{label}</p>
      {payload.map((p, i) => (
        <p key={i} className="tooltip-value" style={{ color: p.color }}>
          {p.name}: {prefix}{Number(p.value).toFixed(2)}
        </p>
      ))}
    </div>
  );
};

/* ── Severity mini-bar for the KPI card ──────────────────── */
const SeverityBar = ({ high = 0, medium = 0, low = 0 }) => {
  const total = high + medium + low;
  if (total === 0) return null;
  return (
    <div className="severity-bar">
      {high > 0 && <div className="sev-segment sev-high" style={{ flex: high }} title={`High: ${high}`} />}
      {medium > 0 && <div className="sev-segment sev-medium" style={{ flex: medium }} title={`Medium: ${medium}`} />}
      {low > 0 && <div className="sev-segment sev-low" style={{ flex: low }} title={`Low: ${low}`} />}
    </div>
  );
};

export default function DashboardPage() {
  const [awsStatus, setAwsStatus] = useState(null);
  const [resources, setResources] = useState(null);
  const [costs, setCosts] = useState(null);
  const [costBreakdown, setCostBreakdown] = useState(null);
  const [recommendations, setRecommendations] = useState(null);
  const [forecastData, setForecastData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [analyzing, setAnalyzing] = useState(false);
  const [error, setError] = useState('');
  const navigate = useNavigate();

  const fetchData = useCallback(async () => {
    try {
      setLoading(true);
      const statusRes = await awsAPI.getStatus();
      setAwsStatus(statusRes.data);

      if (!statusRes.data.validated) {
        setLoading(false);
        return;
      }

      const [resRes, costRes, breakdownRes, recRes, forecastRes] = await Promise.all([
        awsAPI.getResources().catch(() => null),
        awsAPI.getCosts().catch(() => null),
        awsAPI.getCostBreakdown().catch(() => null),
        analysisAPI.getRecommendations().catch(() => null),
        forecastAPI.getBudgetStatus().catch(() => null),
      ]);

      if (resRes) setResources(resRes.data);
      if (costRes) setCosts(costRes.data);
      if (breakdownRes) setCostBreakdown(breakdownRes.data);
      if (recRes) setRecommendations(recRes.data);
      if (forecastRes) setForecastData(forecastRes.data);
    } catch (err) {
      setError('Failed to load dashboard data');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

  /* ── Auto-refresh when recommendations change on another page ── */
  useEffect(() => {
    const refresh = () => fetchData();
    dashboardEvents.on('recommendations-changed', refresh);

    const onVisibility = () => {
      if (document.visibilityState === 'visible') fetchData();
    };
    document.addEventListener('visibilitychange', onVisibility);

    return () => {
      dashboardEvents.off('recommendations-changed', refresh);
      document.removeEventListener('visibilitychange', onVisibility);
    };
  }, [fetchData]);

  const runAnalysis = async () => {
    setAnalyzing(true);
    try {
      await analysisAPI.runAnalysis();
      dashboardEvents.emit('recommendations-changed', { refresh: true });
      await fetchData();
    } catch (err) {
      setError('Analysis failed. Check your AWS credentials.');
    } finally {
      setAnalyzing(false);
    }
  };

  if (loading) {
    return <div className="loading-spinner"><div className="spinner"></div></div>;
  }

  /* ── Not-connected state ─────────────────────────────────── */
  if (!awsStatus?.validated) {
    return (
      <div className="dashboard-empty">
        <div className="empty-icon">☁️</div>
        <h2>Connect Your AWS Account</h2>
        <p>Set up your AWS credentials to start monitoring resources and costs.</p>
        <div style={{ display: 'flex', gap: 12, justifyContent: 'center', marginTop: 20 }}>
          <button className="btn btn-primary btn-lg" onClick={() => navigate('/aws-setup')}>
            🔑 Set Up AWS Credentials
          </button>
          <button className="btn btn-secondary btn-lg" onClick={() => navigate('/iam-guide')}>
            📘 IAM Guide
          </button>
        </div>
      </div>
    );
  }

  /* ── Derived data ────────────────────────────────────────── */
  const summary = resources?.summary || {};
  const monthlyCosts = costs?.monthly?.monthly_costs || [];
  const dailyTrend = costs?.daily_trend?.daily_costs || [];
  const serviceBreakdown = costBreakdown?.service_breakdown?.breakdown || [];
  const regionBreakdown = costBreakdown?.region_breakdown?.regions || [];
  const totalMonthlyCost = monthlyCosts.length > 0
    ? monthlyCosts[monthlyCosts.length - 1]?.total_cost || 0
    : 0;
  const previousMonthCost = monthlyCosts.length > 1
    ? monthlyCosts[monthlyCosts.length - 2]?.total_cost || 0
    : 0;
  const totalSavings = recommendations?.total_estimated_savings || 0;
  const recCount = recommendations?.total_count || 0;
  const sevBreakdown = recommendations?.severity_breakdown || {};
  const totalResources =
    (summary.ec2_total || 0) +
    (summary.ebs_volumes || 0) +
    (summary.s3_buckets || 0) +
    (summary.rds_instances || 0) +
    (summary.elastic_ips || 0);

  const costDelta = previousMonthCost > 0
    ? (((totalMonthlyCost - previousMonthCost) / previousMonthCost) * 100).toFixed(1)
    : null;

  /* Service breakdown for legend table */
  const topServices = serviceBreakdown.slice(0, 6);
  const serviceTotalCost = serviceBreakdown.reduce((s, v) => s + v.cost, 0);

  return (
    <div className="dashboard-page">
      {/* ── Page Header ──────────────────────────────────────── */}
      <div className="dashboard-header">
        <div className="header-left">
          <h1>Dashboard</h1>
          <p className="header-subtitle">
            AWS Cost &amp; Resource Overview
            <span className="header-region">Region: {awsStatus?.region}</span>
          </p>
        </div>
        <div className="header-actions">
          <button
            className="btn btn-primary"
            onClick={runAnalysis}
            disabled={analyzing}
          >
            {analyzing ? '⏳ Analyzing…' : '🔄 Run Analysis'}
          </button>
        </div>
      </div>

      {error && <div className="alert alert-error">{error}</div>}

      {/* ── Primary KPI Row ──────────────────────────────────── */}
      <div className="kpi-grid kpi-primary">
        {/* Monthly Cost */}
        <div className="kpi-card">
          <div className="kpi-top">
            <div className="kpi-icon icon-blue">💰</div>
            <div className="kpi-label">Monthly Cost</div>
          </div>
          <div className="kpi-value">${totalMonthlyCost.toFixed(2)}</div>
          {costDelta !== null && (
            <div className={`kpi-delta ${Number(costDelta) > 0 ? 'delta-up' : 'delta-down'}`}>
              {Number(costDelta) > 0 ? '▲' : '▼'} {Math.abs(costDelta)}% vs prev month
            </div>
          )}
        </div>

        {/* Potential Savings */}
        <div className="kpi-card">
          <div className="kpi-top">
            <div className="kpi-icon icon-green">💡</div>
            <div className="kpi-label">Potential Savings</div>
          </div>
          <div className="kpi-value kpi-savings">${totalSavings.toFixed(2)}<span className="kpi-unit">/mo</span></div>
          <div className="kpi-delta delta-neutral">
            {recCount} optimization {recCount === 1 ? 'issue' : 'issues'}
          </div>
        </div>

        {/* Total Resources */}
        <div className="kpi-card">
          <div className="kpi-top">
            <div className="kpi-icon icon-indigo">🖥️</div>
            <div className="kpi-label">Total Resources</div>
          </div>
          <div className="kpi-value">{totalResources}</div>
          <div className="kpi-delta delta-neutral">
            {summary.ec2_running || 0} EC2 running
          </div>
        </div>

        {/* Active Alerts */}
        <div className="kpi-card">
          <div className="kpi-top">
            <div className="kpi-icon icon-amber">⚠️</div>
            <div className="kpi-label">Active Alerts</div>
          </div>
          <div className="kpi-value">{recCount}</div>
          <SeverityBar
            high={sevBreakdown.high || 0}
            medium={sevBreakdown.medium || 0}
            low={sevBreakdown.low || 0}
          />
        </div>
      </div>

      {/* ── Forecast Banner ──────────────────────────────────── */}
      {forecastData?.has_budget && (
        <div className={`forecast-banner ${forecastData.alert_level === 'HIGH' ? 'banner-danger' : forecastData.alert_level === 'MEDIUM' ? 'banner-warning' : 'banner-ok'}`}>
          <div className="forecast-banner-left">
            <span className="banner-icon">🔮</span>
            <div>
              <strong>Predicted: ${forecastData.predicted_cost?.toFixed(2) || '—'}/mo</strong>
              <span className="banner-vs">
                Budget: ${forecastData.monthly_limit?.toFixed(2) || '—'} · {forecastData.percentage?.toFixed(0) || 0}%
              </span>
            </div>
          </div>
          {forecastData.alert_level === 'HIGH' && (
            <span className="badge badge-high">Over Budget</span>
          )}
          {forecastData.alert_level === 'MEDIUM' && (
            <span className="badge badge-medium">Warning</span>
          )}
          <button className="btn btn-secondary btn-sm" onClick={() => navigate('/forecast')}>
            View Forecast →
          </button>
        </div>
      )}

      {/* ── Resource Inventory Strip ─────────────────────────── */}
      <div className="resource-strip">
        <div className="strip-title">Resource Inventory</div>
        <div className="strip-items">
          <div className="strip-item"><span className="strip-count">{summary.ec2_total || 0}</span> EC2</div>
          <div className="strip-divider" />
          <div className="strip-item"><span className="strip-count">{summary.ebs_volumes || 0}</span> EBS</div>
          <div className="strip-divider" />
          <div className="strip-item"><span className="strip-count">{summary.s3_buckets || 0}</span> S3</div>
          <div className="strip-divider" />
          <div className="strip-item"><span className="strip-count">{summary.rds_instances || 0}</span> RDS</div>
          <div className="strip-divider" />
          <div className="strip-item"><span className="strip-count">{summary.elastic_ips || 0}</span> EIP</div>
        </div>
      </div>

      {/* ── Charts Row 1: Cost Trend + Service Breakdown ───── */}
      <div className="chart-row">
        {/* Daily Cost Trend — area chart */}
        <div className="card chart-card chart-wide">
          <div className="card-header">
            <div>
              <div className="card-title">Cost Trend</div>
              <div className="card-subtitle">Daily spend — last 30 days</div>
            </div>
          </div>
          {dailyTrend.length > 0 ? (
            <ResponsiveContainer width="100%" height={280}>
              <AreaChart data={dailyTrend}>
                <defs>
                  <linearGradient id="gradCost" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.15} />
                    <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" vertical={false} />
                <XAxis
                  dataKey="date"
                  tick={{ fontSize: 11, fill: '#94a3b8' }}
                  tickFormatter={v => v.substring(5)}
                  axisLine={false}
                  tickLine={false}
                />
                <YAxis
                  tick={{ fontSize: 11, fill: '#94a3b8' }}
                  tickFormatter={v => `$${v}`}
                  axisLine={false}
                  tickLine={false}
                  width={50}
                />
                <Tooltip content={<CustomTooltip prefix="$" />} />
                <Area
                  type="monotone"
                  dataKey="cost"
                  name="Daily Cost"
                  stroke="#3b82f6"
                  fill="url(#gradCost)"
                  strokeWidth={2.5}
                  dot={false}
                  activeDot={{ r: 5, stroke: '#fff', strokeWidth: 2 }}
                />
              </AreaChart>
            </ResponsiveContainer>
          ) : monthlyCosts.length > 0 ? (
            <ResponsiveContainer width="100%" height={280}>
              <BarChart data={monthlyCosts}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" vertical={false} />
                <XAxis dataKey="period_start" tick={{ fontSize: 11, fill: '#94a3b8' }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fontSize: 11, fill: '#94a3b8' }} tickFormatter={v => `$${v}`} axisLine={false} tickLine={false} width={50} />
                <Tooltip content={<CustomTooltip prefix="$" />} />
                <Bar dataKey="total_cost" name="Monthly Cost" fill="#3b82f6" radius={[6, 6, 0, 0]} barSize={48} />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="chart-empty">No cost data available</div>
          )}
        </div>

        {/* Service Breakdown — donut + legend */}
        <div className="card chart-card chart-narrow">
          <div className="card-header">
            <div>
              <div className="card-title">Cost by Service</div>
              <div className="card-subtitle">Last 30 days</div>
            </div>
          </div>
          {topServices.length > 0 ? (
            <div className="donut-container">
              <div className="donut-wrapper">
                <ResponsiveContainer width="100%" height={180}>
                  <PieChart>
                    <Pie
                      data={topServices}
                      cx="50%"
                      cy="50%"
                      innerRadius={50}
                      outerRadius={80}
                      dataKey="cost"
                      nameKey="service"
                      stroke="none"
                      paddingAngle={2}
                    >
                      {topServices.map((_, idx) => (
                        <Cell key={idx} fill={COLORS[idx % COLORS.length]} />
                      ))}
                    </Pie>
                    <Tooltip content={<CustomTooltip prefix="$" />} />
                  </PieChart>
                </ResponsiveContainer>
                <div className="donut-center-label">
                  <span className="donut-total">${serviceTotalCost.toFixed(0)}</span>
                  <span className="donut-total-label">Total</span>
                </div>
              </div>
              {/* Legend table */}
              <div className="service-legend">
                {topServices.map((svc, i) => (
                  <div key={i} className="legend-row">
                    <span className="legend-dot" style={{ background: COLORS[i % COLORS.length] }} />
                    <span className="legend-name">{svc.service?.length > 22 ? svc.service.substring(0, 22) + '…' : svc.service}</span>
                    <span className="legend-value">${svc.cost.toFixed(2)}</span>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <div className="chart-empty">No breakdown data available</div>
          )}
        </div>
      </div>

      {/* ── Charts Row 2: Monthly Bar + Region Bar ────────── */}
      <div className="chart-row">
        {/* Monthly Bar */}
        <div className="card chart-card chart-half">
          <div className="card-header">
            <div>
              <div className="card-title">Monthly Spend</div>
              <div className="card-subtitle">Last 3 months</div>
            </div>
          </div>
          {monthlyCosts.length > 0 ? (
            <ResponsiveContainer width="100%" height={240}>
              <BarChart data={monthlyCosts}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" vertical={false} />
                <XAxis
                  dataKey="period_start"
                  tick={{ fontSize: 11, fill: '#94a3b8' }}
                  axisLine={false}
                  tickLine={false}
                />
                <YAxis
                  tick={{ fontSize: 11, fill: '#94a3b8' }}
                  tickFormatter={v => `$${v}`}
                  axisLine={false}
                  tickLine={false}
                  width={50}
                />
                <Tooltip content={<CustomTooltip prefix="$" />} />
                <Bar dataKey="total_cost" name="Monthly Cost" fill="#8b5cf6" radius={[6, 6, 0, 0]} barSize={40} />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="chart-empty">No monthly data</div>
          )}
        </div>

        {/* Region Breakdown */}
        <div className="card chart-card chart-half">
          <div className="card-header">
            <div>
              <div className="card-title">Cost by Region</div>
              <div className="card-subtitle">Last 30 days</div>
            </div>
          </div>
          {regionBreakdown.length > 0 ? (
            <ResponsiveContainer width="100%" height={240}>
              <BarChart data={regionBreakdown} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" horizontal={false} />
                <XAxis type="number" tick={{ fontSize: 11, fill: '#94a3b8' }} tickFormatter={v => `$${v}`} axisLine={false} tickLine={false} />
                <YAxis type="category" dataKey="region" tick={{ fontSize: 11, fill: '#94a3b8' }} width={100} axisLine={false} tickLine={false} />
                <Tooltip content={<CustomTooltip prefix="$" />} />
                <Bar dataKey="cost" name="Cost" fill="#10b981" radius={[0, 6, 6, 0]} barSize={24} />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="chart-empty">No region data</div>
          )}
        </div>
      </div>

      {/* ── Recommendations Table ────────────────────────────── */}
      {recommendations && recommendations.recommendations?.length > 0 && (
        <div className="card recommendations-section">
          <div className="card-header">
            <div>
              <div className="card-title">Top Optimization Recommendations</div>
              <div className="card-subtitle">
                {recCount} issues — ${totalSavings.toFixed(2)}/mo potential savings
              </div>
            </div>
            <button className="btn btn-secondary btn-sm" onClick={() => navigate('/recommendations')}>
              View All →
            </button>
          </div>
          <div className="table-container">
            <table className="rec-table">
              <thead>
                <tr>
                  <th>Resource</th>
                  <th>Type</th>
                  <th>Recommendation</th>
                  <th>Severity</th>
                  <th className="th-right">Savings/mo</th>
                </tr>
              </thead>
              <tbody>
                {recommendations.recommendations.slice(0, 5).map((rec, i) => (
                  <tr key={i}>
                    <td><code>{rec.resource_id}</code></td>
                    <td><span className="type-pill">{rec.resource_type}</span></td>
                    <td className="rec-text-cell">{rec.recommendation_text}</td>
                    <td>
                      <span className={`badge badge-${rec.severity.toLowerCase()}`}>
                        {rec.severity}
                      </span>
                    </td>
                    <td className="savings-cell">${rec.estimated_savings.toFixed(2)}</td>
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
