import axios from 'axios';

const API_BASE = process.env.REACT_APP_API_URL || '/api';

const api = axios.create({
  baseURL: API_BASE,
  headers: { 'Content-Type': 'application/json' },
});

// Attach JWT token to every request
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('racecloud_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Handle 401 responses (expired token)
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (
      error.response?.status === 401 &&
      !error.config?.url?.includes('/auth/login') &&
      !error.config?.url?.includes('/auth/register')
    ) {
      localStorage.removeItem('racecloud_token');
      localStorage.removeItem('racecloud_user');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

// ── Auth ──────────────────────────────────────────────────────────
export const authAPI = {
  register: (data) => api.post('/auth/register', data),
  login: (data) => api.post('/auth/login', data),
  getProfile: () => api.get('/auth/me'),
};

// ── AWS ──────────────────────────────────────────────────────────
export const awsAPI = {
  submitCredentials: (data) => api.post('/aws/credentials', data),
  getStatus: () => api.get('/aws/status'),
  getRegions: () => api.get('/aws/regions'),
  getResources: () => api.get('/aws/resources'),
  getCosts: () => api.get('/aws/costs'),
  getCostBreakdown: () => api.get('/aws/costs/breakdown'),
};

// ── Analysis ─────────────────────────────────────────────────────
export const analysisAPI = {
  runAnalysis: () => api.post('/analysis/run'),
  getRecommendations: () => api.get('/analysis/recommendations'),
  dismissRecommendation: (id) => api.put(`/analysis/recommendations/${id}/dismiss`),
  getRules: () => api.get('/analysis/rules'),
};

// ── Reports ──────────────────────────────────────────────────────
export const reportsAPI = {
  getLatest: () => api.get('/reports/latest'),
  downloadReport: () =>
    api.get('/reports/download', { responseType: 'blob' }),
  downloadPdf: () =>
    api.get('/reports/download-pdf', { responseType: 'blob' }),
  emailReport: () => api.post('/reports/email'),
  getHistory: () => api.get('/reports/history'),
};

// ── IAM Guide ────────────────────────────────────────────────────
export const iamAPI = {
  getGuide: () => api.get('/iam/guide'),
};
// ── Forecast & Budget ────────────────────────────────────────
export const forecastAPI = {
  getPrediction: () => api.get('/forecast/cost'),
  getAnomalies: () => api.get('/forecast/anomalies'),
  setBudget: (data) => api.post('/forecast/budget', data),
  getBudgetStatus: () => api.get('/forecast/budget/status'),
};
// ── Dependency & Simulation ──────────────────────────────
export const dependencyAPI = {
  getChains: () => api.get('/analysis/dependency-chains'),
  simulateAction: (data) => api.post('/simulation/run', data),
  simulateChain: (chain) => api.post('/simulation/run-chain', { chain }),
};

// ── Decision Intelligence ────────────────────────────────
export const decisionAPI = {
  getPlan: () => api.get('/decision/plan'),
  recordBehavior: (data) => api.post('/decision/behavior', data),
  aiSuggest: (data) => api.post('/decision/ai-suggest', data),
  intelligence: (data) => api.post('/decision/intelligence', data),
};

// ── Demo Mode ────────────────────────────────────────────
export const demoAPI = {
  getStatus: () => api.get('/demo/status'),
  switchScenario: (scenario) => api.post('/demo/switch', { scenario }),
};

export default api;
