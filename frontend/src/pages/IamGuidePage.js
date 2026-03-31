import React, { useState, useEffect } from 'react';
import { iamAPI } from '../services/api';
import './IamGuidePage.css';

export default function IamGuidePage() {
  const [guide, setGuide] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    iamAPI.getGuide()
      .then(res => setGuide(res.data))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="loading-spinner"><div className="spinner"></div></div>;

  if (!guide) {
    return (
      <div className="iam-guide-page">
        <h1>📘 IAM Setup Guide</h1>
        <p>Could not load guide. Make sure the backend is running.</p>
      </div>
    );
  }

  return (
    <div className="iam-guide-page">
      <div className="page-header">
        <h1>📘 {guide.title}</h1>
        <p>{guide.description}</p>
      </div>

      {/* Prerequisites */}
      <div className="card guide-section">
        <h2>Prerequisites</h2>
        <ul className="prereq-list">
          {guide.prerequisites.map((p, i) => (
            <li key={i}>{p}</li>
          ))}
        </ul>
      </div>

      {/* Important Notes */}
      <div className="card guide-section warning-card">
        <h2>⚠️ Important Notes</h2>
        <ul className="notes-list">
          {guide.important_notes.map((n, i) => (
            <li key={i}>{n}</li>
          ))}
        </ul>
      </div>

      {/* Steps */}
      <div className="steps-container">
        {guide.steps.map((step) => (
          <div key={step.step} className="card step-card">
            <div className="step-header">
              <div className="step-number">{step.step}</div>
              <div className="step-icon">{step.icon}</div>
            </div>
            <div className="step-body">
              <h3>{step.title}</h3>
              <p className="step-description">{step.description}</p>
              <p className="step-details">{step.details}</p>
              {step.policies && (
                <div className="step-policies">
                  <h4>Required Policies:</h4>
                  {step.policies.map((pol, i) => (
                    <div key={i} className="policy-item">
                      <code>{pol.name}</code>
                      <span>{pol.description}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        ))}
      </div>

      {/* Security Assurance */}
      <div className="card guide-section security-section">
        <h2>🛡️ {guide.security_assurance.title}</h2>
        <ul className="security-list">
          {guide.security_assurance.points.map((p, i) => (
            <li key={i}>{p}</li>
          ))}
        </ul>
      </div>
    </div>
  );
}
