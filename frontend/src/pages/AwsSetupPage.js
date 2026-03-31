import React, { useState, useEffect } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { awsAPI } from '../services/api';
import './AwsSetupPage.css';

const REGIONS = [
  { value: 'us-east-1', label: 'US East (N. Virginia)' },
  { value: 'us-east-2', label: 'US East (Ohio)' },
  { value: 'us-west-1', label: 'US West (N. California)' },
  { value: 'us-west-2', label: 'US West (Oregon)' },
  { value: 'eu-west-1', label: 'EU (Ireland)' },
  { value: 'eu-west-2', label: 'EU (London)' },
  { value: 'eu-central-1', label: 'EU (Frankfurt)' },
  { value: 'ap-south-1', label: 'Asia Pacific (Mumbai)' },
  { value: 'ap-southeast-1', label: 'Asia Pacific (Singapore)' },
  { value: 'ap-southeast-2', label: 'Asia Pacific (Sydney)' },
  { value: 'ap-northeast-1', label: 'Asia Pacific (Tokyo)' },
  { value: 'sa-east-1', label: 'South America (São Paulo)' },
  { value: 'ca-central-1', label: 'Canada (Central)' },
];

export default function AwsSetupPage() {
  const [accessKey, setAccessKey] = useState('');
  const [secretKey, setSecretKey] = useState('');
  const [region, setRegion] = useState('us-east-1');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [status, setStatus] = useState(null);
  const navigate = useNavigate();

  useEffect(() => {
    awsAPI.getStatus()
      .then(res => setStatus(res.data))
      .catch(() => {});
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setSuccess('');
    setLoading(true);

    try {
      const res = await awsAPI.submitCredentials({
        access_key: accessKey,
        secret_key: secretKey,
        region,
      });
      setSuccess(`Credentials validated! Account: ${res.data.account_id}, Region: ${res.data.region}`);
      setAccessKey('');
      setSecretKey('');
      setTimeout(() => navigate('/dashboard'), 2000);
    } catch (err) {
      setError(err.response?.data?.details || err.response?.data?.error || 'Validation failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="aws-setup-page">
      <div className="page-header">
        <h1>🔑 AWS Credentials Setup</h1>
        <p>Connect your AWS account to start monitoring resources and costs</p>
      </div>

      {/* Current Status */}
      {status && (
        <div className={`card status-card ${status.validated ? 'connected' : 'disconnected'}`}>
          <div className="status-indicator">
            <span className={`status-dot ${status.validated ? 'active' : 'inactive'}`}></span>
            <span className="status-text">
              {status.validated ? 'Connected' : 'Not Connected'}
            </span>
          </div>
          {status.validated && (
            <div className="status-details">
              <span>Region: {status.region}</span>
              <span>Account: {status.account_id}</span>
              <span>Last Sync: {status.last_synced || 'Never'}</span>
            </div>
          )}
        </div>
      )}

      {/* Info Banner */}
      <div className="alert alert-info" style={{ marginBottom: 24 }}>
        <strong>Need help creating IAM credentials?</strong>{' '}
        <Link to="/iam-guide">Follow our step-by-step IAM setup guide →</Link>
      </div>

      {/* Credential Form */}
      <div className="card" style={{ maxWidth: 640 }}>
        <h2 style={{ marginBottom: 4 }}>Enter IAM Credentials</h2>
        <p style={{ color: 'var(--gray-500)', fontSize: 14, marginBottom: 24 }}>
          Your credentials are encrypted before storage. We only make read-only API calls.
        </p>

        {error && <div className="alert alert-error">{error}</div>}
        {success && <div className="alert alert-success">{success}</div>}

        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label className="form-label">IAM Access Key ID</label>
            <input
              type="text"
              className="form-input"
              placeholder="AKIA..."
              value={accessKey}
              onChange={(e) => setAccessKey(e.target.value)}
              required
              autoComplete="off"
            />
          </div>

          <div className="form-group">
            <label className="form-label">IAM Secret Access Key</label>
            <input
              type="password"
              className="form-input"
              placeholder="Enter your secret access key"
              value={secretKey}
              onChange={(e) => setSecretKey(e.target.value)}
              required
              autoComplete="off"
            />
          </div>

          <div className="form-group">
            <label className="form-label">AWS Region</label>
            <select
              className="form-select"
              value={region}
              onChange={(e) => setRegion(e.target.value)}
            >
              {REGIONS.map(r => (
                <option key={r.value} value={r.value}>{r.label}</option>
              ))}
            </select>
          </div>

          <button
            type="submit"
            className="btn btn-primary btn-lg"
            style={{ width: '100%' }}
            disabled={loading}
          >
            {loading ? 'Validating...' : 'Validate & Save Credentials'}
          </button>
        </form>

        <div className="security-note">
          <h4>🛡️ Security Assurance</h4>
          <ul>
            <li>Credentials are encrypted using AES (Fernet encryption)</li>
            <li>Never stored in plain text anywhere</li>
            <li>Only used for read-only API calls via boto3</li>
            <li>You can revoke the IAM key anytime from AWS Console</li>
          </ul>
        </div>
      </div>
    </div>
  );
}
