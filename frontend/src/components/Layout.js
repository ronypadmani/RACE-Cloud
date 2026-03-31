import React from 'react';
import { Outlet, NavLink, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import './Layout.css';

export default function Layout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const navItems = [
    { path: '/dashboard', label: 'Dashboard', icon: '📊' },
    { path: '/decisions', label: 'Decisions', icon: '🧠' },
    { path: '/resources', label: 'Resources', icon: '🖥️' },
    { path: '/recommendations', label: 'Recommendations', icon: '💡' },
    { path: '/forecast', label: 'Forecast', icon: '🔮' },
    { path: '/dependency-insights', label: 'Dependencies', icon: '🔗' },
    { path: '/report', label: 'Report', icon: '📄' },
    { path: '/aws-setup', label: 'AWS Setup', icon: '🔑' },
    { path: '/iam-guide', label: 'IAM Guide', icon: '📘' },
  ];

  return (
    <div className="layout">
      {/* Sidebar */}
      <aside className="sidebar">
        <div className="sidebar-brand">
          <span className="brand-icon">☁️</span>
          <div>
            <h1 className="brand-title">RACE-Cloud</h1>
            <p className="brand-subtitle">Cost Optimizer</p>
          </div>
        </div>

        <nav className="sidebar-nav">
          {navItems.map(({ path, label, icon }) => (
            <NavLink
              key={path}
              to={path}
              className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}
            >
              <span className="nav-icon">{icon}</span>
              <span className="nav-label">{label}</span>
            </NavLink>
          ))}
        </nav>

        <div className="sidebar-footer">
          <div className="user-info">
            <div className="user-avatar">
              {user?.username?.charAt(0).toUpperCase() || 'U'}
            </div>
            <div>
              <p className="user-name">{user?.username || 'User'}</p>
              <p className="user-email">{user?.email || ''}</p>
            </div>
          </div>
          <button onClick={handleLogout} className="btn-logout">
            Logout
          </button>
        </div>
      </aside>

      {/* Main Content */}
      <main className="main-content">
        <Outlet />
      </main>
    </div>
  );
}
