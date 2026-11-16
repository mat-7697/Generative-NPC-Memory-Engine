'use client';

import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { api, User } from '@/lib/api';

interface AuthContextType {
  user: User | null;
  token: string | null;
  loading: boolean;
  login: (credentials: { username: string; password: string }) => Promise<void>;
  register: (data: { username: string; email: string; password: string }) => Promise<void>;
  logout: () => void;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchProfile = useCallback(async () => {
    try {
      const profile = await api.players.getMe();
      setUser(profile);
    } catch {
      setUser(null);
      setToken(null);
      if (typeof window !== 'undefined') {
        localStorage.removeItem('token');
        localStorage.removeItem('access_token');
      }
    }
  }, []);

  const refreshUser = useCallback(async () => {
    if (!token && typeof window !== 'undefined') {
      const stored = localStorage.getItem('token') || localStorage.getItem('access_token');
      if (!stored) return;
    }
    await fetchProfile();
  }, [token, fetchProfile]);

  useEffect(() => {
    const initializeAuth = async () => {
      if (typeof window !== 'undefined') {
        const storedToken = localStorage.getItem('token') || localStorage.getItem('access_token');
        if (storedToken) {
          setToken(storedToken);
          try {
            const profile = await api.players.getMe();
            setUser(profile);
          } catch {
            localStorage.removeItem('token');
            localStorage.removeItem('access_token');
            setToken(null);
            setUser(null);
          }
        }
      }
      setLoading(false);
    };

    initializeAuth();
  }, []);

  const login = async (credentials: { username: string; password: string }) => {
    setLoading(true);
    try {
      const res = await api.auth.login(credentials);
      if (typeof window !== 'undefined') {
        localStorage.setItem('token', res.access_token);
        localStorage.setItem('access_token', res.access_token);
      }
      setToken(res.access_token);
      const profile = await api.players.getMe();
      setUser(profile);
    } finally {
      setLoading(false);
    }
  };

  const register = async (data: { username: string; email: string; password: string }) => {
    setLoading(true);
    try {
      const res = await api.auth.register(data);
      if (typeof window !== 'undefined') {
        localStorage.setItem('token', res.access_token);
        localStorage.setItem('access_token', res.access_token);
      }
      setToken(res.access_token);
      const profile = await api.players.getMe();
      setUser(profile);
    } finally {
      setLoading(false);
    }
  };

  const logout = () => {
    if (typeof window !== 'undefined') {
      localStorage.removeItem('token');
      localStorage.removeItem('access_token');
    }
    setToken(null);
    setUser(null);
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        loading,
        login,
        register,
        logout,
        refreshUser,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextType {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
