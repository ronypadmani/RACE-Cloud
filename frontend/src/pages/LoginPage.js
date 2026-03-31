import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import './AuthPages.css';

export default function LoginPage() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const { login } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await login(email, password);
      navigate('/dashboard');
    } catch (err) {
      setError(err.response?.data?.error || 'Login failed. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-page">
      <div className="auth-container">
        <div className="auth-left">
          <div className="auth-brand">
            <span className="auth-brand-icon">☁️</span>
            <h1>RACE-Cloud</h1>
            <p>Resource Analysis & Cost Explorer for Cloud</p>
          </div>
          <div className="auth-features">
            <div className="auth-feature">
              <span>📊</span>
              <div>
                <h3>Real-time Monitoring</h3>
                <p>Monitor AWS resources and costs in real-time</p>
              </div>
            </div>
            <div className="auth-feature">
              <span>💡</span>
              <div>
                <h3>Smart Recommendations</h3>
                <p>Get actionable cost optimization suggestions</p>
              </div>
            </div>
            <div className="auth-feature">
              <span>🛡️</span>
              <div>
                <h3>Read-Only & Secure</h3>
                <p>Advisory only — never modifies your AWS resources</p>
              </div>
            </div>
          </div>
        </div>

        <div className="auth-right">
          <div className="auth-form-container">
            <h2>Welcome back</h2>
            <p className="auth-subtitle">Sign in to your RACE-Cloud account</p>

            {error && <div className="alert alert-error">{error}</div>}

            <form onSubmit={handleSubmit}>
              <div className="form-group">
                <label className="form-label">Email Address</label>
                <input
                  type="email"
                  className="form-input"
                  placeholder="you@example.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                />
              </div>

              <div className="form-group">
                <label className="form-label">Password</label>
                <input
                  type="password"
                  className="form-input"
                  placeholder="Enter your password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                />
              </div>

              <button
                type="submit"
                className="btn btn-primary btn-lg"
                style={{ width: '100%' }}
                disabled={loading}
              >
                {loading ? 'Signing in...' : 'Sign In'}
              </button>
            </form>

            <p className="auth-switch">
              Don't have an account? <Link to="/register">Create one</Link>
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
