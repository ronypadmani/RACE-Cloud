import React, { useState, useEffect } from 'react';
import { reportsAPI } from '../services/api';
import './ReportPage.css';

export default function ReportPage() {
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(true);
  const [downloading, setDownloading] = useState(false);
  const [downloadingPdf, setDownloadingPdf] = useState(false);
  const [emailing, setEmailing] = useState(false);
  const [emailStatus, setEmailStatus] = useState(null);

  useEffect(() => {
    reportsAPI.getLatest()
      .then(res => setReport(res.data))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const handleDownload = async () => {
    setDownloading(true);
    try {
      const res = await reportsAPI.downloadReport();
      const blob = new Blob([res.data], { type: 'text/html' });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `RACE-Cloud_Report_${new Date().toISOString().slice(0, 10)}.html`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
    } catch {
      alert('Failed to download report');
    } finally {
      setDownloading(false);
    }
  };

  const handleDownloadPdf = async () => {
    setDownloadingPdf(true);
    try {
      const res = await reportsAPI.downloadPdf();
      const blob = new Blob([res.data], { type: 'application/pdf' });
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `racecloud_cost_report_${new Date().toISOString().replace(/[:.]/g, '').slice(0, 15)}.pdf`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
    } catch {
      alert('Failed to download PDF report');
    } finally {
      setDownloadingPdf(false);
    }
  };

  const handleEmailReport = async () => {
    setEmailing(true);
    setEmailStatus(null);
    try {
      const res = await reportsAPI.emailReport();
      setEmailStatus({ success: true, message: res.data.message });
    } catch (err) {
      const msg = err.response?.data?.message || 'Failed to send email';
      setEmailStatus({ success: false, message: msg });
    } finally {
      setEmailing(false);
    }
  };

  if (loading) return <div className="loading-spinner"><div className="spinner"></div></div>;

  if (!report || !report.optimization_recommendations) {
    return (
      <div className="report-page">
        <div className="page-header">
          <h1>📄 Optimization Report</h1>
          <p>Run an analysis first to generate a report.</p>
        </div>
        <div className="card" style={{ textAlign: 'center', padding: 60 }}>
          <div style={{ fontSize: 48, marginBottom: 16 }}>📋</div>
          <h3>No Report Available</h3>
          <p style={{ color: 'var(--gray-500)', marginTop: 8 }}>
            Go to Dashboard and run an analysis to generate your first report.
          </p>
        </div>
      </div>
    );
  }

  const meta = report.report_metadata || {};
  const account = report.account_summary || {};
  const recs = report.optimization_recommendations || [];
  const summary = report.summary_statistics || {};
  const severityBreakdown = summary.severity_breakdown || {};

  return (
    <div className="report-page">
      <div className="page-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <h1>📄 Optimization Report</h1>
          <p>Generated: {meta.generated_at ? new Date(meta.generated_at).toLocaleString() : 'N/A'}</p>
        </div>
        <div className="report-actions">
          <button
            className="btn btn-primary"
            onClick={handleDownloadPdf}
            disabled={downloadingPdf}
          >
            {downloadingPdf ? '\u23F3 Generating...' : '\uD83D\uDCC4 Download PDF'}
          </button>
          <button
            className="btn btn-success"
            onClick={handleDownload}
            disabled={downloading}
          >
            {downloading ? '\u23F3 Downloading...' : '\u2B07\uFE0F Download HTML'}
          </button>
          <button
            className="btn btn-email"
            onClick={handleEmailReport}
            disabled={emailing}
          >
            {emailing ? '\u23F3 Sending...' : '\u2709\uFE0F Email Report'}
          </button>
        </div>
      </div>

      {emailStatus && (
        <div className={`email-status ${emailStatus.success ? 'email-success' : 'email-error'}`}>
          {emailStatus.success ? '\u2705' : '\u274C'} {emailStatus.message}
        </div>
      )}

      {/* Account Summary */}
      <div className="card report-section">
        <h2>📋 Account Summary</h2>
        <div className="report-info-grid">
          <div className="report-info-item">
            <span className="report-info-label">Account ID</span>
            <span className="report-info-value">{account.account_id}</span>
          </div>
          <div className="report-info-item">
            <span className="report-info-label">Region</span>
            <span className="report-info-value">{account.region}</span>
          </div>
          <div className="report-info-item">
            <span className="report-info-label">Analysis Date</span>
            <span className="report-info-value">{account.analysis_date || 'N/A'}</span>
          </div>
          <div className="report-info-item">
            <span className="report-info-label">Prepared For</span>
            <span className="report-info-value">{account.prepared_for}</span>
          </div>
        </div>
      </div>

      {/* Summary Stats */}
      <div className="report-stats">
        <div className="report-stat-card savings">
          <div className="report-stat-number">${(summary.total_estimated_monthly_savings || 0).toFixed(2)}</div>
          <div className="report-stat-label">Total Estimated Monthly Savings</div>
        </div>
        <div className="report-stat-card">
          <div className="report-stat-number">{summary.total_issues_found || 0}</div>
          <div className="report-stat-label">Total Issues Found</div>
        </div>
        <div className="report-stat-card high">
          <div className="report-stat-number">{severityBreakdown.HIGH || 0}</div>
          <div className="report-stat-label">High Severity</div>
        </div>
        <div className="report-stat-card medium">
          <div className="report-stat-number">{severityBreakdown.MEDIUM || 0}</div>
          <div className="report-stat-label">Medium Severity</div>
        </div>
        <div className="report-stat-card low">
          <div className="report-stat-number">{severityBreakdown.LOW || 0}</div>
          <div className="report-stat-label">Low Severity</div>
        </div>
      </div>

      {/* Recommendations Table */}
      <div className="card report-section">
        <h2>🔍 Optimization Recommendations</h2>
        {recs.length > 0 ? (
          <div className="table-container">
            <table>
              <thead>
                <tr>
                  <th>#</th>
                  <th>Resource</th>
                  <th>Type</th>
                  <th>Suggested Action</th>
                  <th>Severity</th>
                  <th>Est. Savings/mo</th>
                </tr>
              </thead>
              <tbody>
                {recs.map((rec, i) => (
                  <tr key={i}>
                    <td>{i + 1}</td>
                    <td><code>{rec.resource}</code></td>
                    <td>{rec.resource_type}</td>
                    <td style={{ maxWidth: 320, fontSize: 13, lineHeight: 1.5 }}>{rec.suggested_action}</td>
                    <td>
                      <span className={`badge badge-${rec.severity.toLowerCase()}`}>{rec.severity}</span>
                    </td>
                    <td style={{ fontWeight: 600 }}>${rec.estimated_savings.toFixed(2)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p style={{ textAlign: 'center', color: 'var(--gray-400)', padding: 32 }}>
            No optimization issues found. Your AWS resources are well-configured! ✅
          </p>
        )}
      </div>

      {/* Disclaimer */}
      <div className="card report-section disclaimer-card">
        <h2>⚠️ Advisory Disclaimer</h2>
        <p>{report.disclaimer}</p>
      </div>
    </div>
  );
}
