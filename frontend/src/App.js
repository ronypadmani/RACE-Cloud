import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import Layout from './components/Layout';
import LoginPage from './pages/LoginPage';
import RegisterPage from './pages/RegisterPage';
import DashboardPage from './pages/DashboardPage';
import AwsSetupPage from './pages/AwsSetupPage';
import IamGuidePage from './pages/IamGuidePage';
import RecommendationsPage from './pages/RecommendationsPage';
import ReportPage from './pages/ReportPage';
import ResourcesPage from './pages/ResourcesPage';
import ForecastPage from './pages/ForecastPage';
import DependencyInsightsPage from './pages/DependencyInsightsPage';
import DecisionDashboard from './pages/DecisionDashboard';

function ProtectedRoute({ children }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="loading-spinner"><div className="spinner"></div></div>;
  return user ? children : <Navigate to="/login" />;
}

function PublicRoute({ children }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="loading-spinner"><div className="spinner"></div></div>;
  return user ? <Navigate to="/dashboard" /> : children;
}

function App() {
  return (
    <AuthProvider>
      <Router>
        <Routes>
          {/* Public routes */}
          <Route path="/login" element={<PublicRoute><LoginPage /></PublicRoute>} />
          <Route path="/register" element={<PublicRoute><RegisterPage /></PublicRoute>} />

          {/* Protected routes inside Layout */}
          <Route path="/" element={<ProtectedRoute><Layout /></ProtectedRoute>}>
            <Route index element={<Navigate to="/dashboard" />} />
            <Route path="dashboard" element={<DashboardPage />} />
            <Route path="aws-setup" element={<AwsSetupPage />} />
            <Route path="iam-guide" element={<IamGuidePage />} />
            <Route path="resources" element={<ResourcesPage />} />
            <Route path="recommendations" element={<RecommendationsPage />} />
            <Route path="forecast" element={<ForecastPage />} />
            <Route path="dependency-insights" element={<DependencyInsightsPage />} />
            <Route path="decisions" element={<DecisionDashboard />} />
            <Route path="report" element={<ReportPage />} />
          </Route>

          <Route path="*" element={<Navigate to="/dashboard" />} />
        </Routes>
      </Router>
    </AuthProvider>
  );
}

export default App;
