import React, { createContext, useState, useContext, useEffect } from 'react';
import { authAPI } from '../services/api';

const AuthContext = createContext(null);

export const useAuth = () => useContext(AuthContext);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = localStorage.getItem('racecloud_token');
    const savedUser = localStorage.getItem('racecloud_user');
    if (token && savedUser) {
      try {
        setUser(JSON.parse(savedUser));
      } catch {
        localStorage.removeItem('racecloud_token');
        localStorage.removeItem('racecloud_user');
      }
    }
    setLoading(false);
  }, []);

  const login = async (email, password) => {
    const res = await authAPI.login({ email, password });
    const { token, user: userData } = res.data;
    localStorage.setItem('racecloud_token', token);
    localStorage.setItem('racecloud_user', JSON.stringify(userData));
    setUser(userData);
    return userData;
  };

  const register = async (username, email, password) => {
    const res = await authAPI.register({ username, email, password });
    const { token, user: userData } = res.data;
    localStorage.setItem('racecloud_token', token);
    localStorage.setItem('racecloud_user', JSON.stringify(userData));
    setUser(userData);
    return userData;
  };

  const logout = () => {
    localStorage.removeItem('racecloud_token');
    localStorage.removeItem('racecloud_user');
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, login, register, logout, loading }}>
      {children}
    </AuthContext.Provider>
  );
}
