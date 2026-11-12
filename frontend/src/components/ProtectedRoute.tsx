'use client';

import React, { useEffect } from 'react';
import { useRouter, usePathname } from 'next/navigation';
import { useAuth } from '@/lib/auth';

interface ProtectedRouteProps {
  children: React.ReactNode;
  requireAdmin?: boolean;
}

export default function ProtectedRoute({
  children,
  requireAdmin = false,
}: ProtectedRouteProps) {
  const { user, token, loading } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (!loading) {
      if (!token) {
        router.push(`/login?redirect=${encodeURIComponent(pathname)}`);
      } else if (requireAdmin && user && user.role !== 'admin') {
        router.push('/dashboard');
      }
    }
  }, [loading, token, user, requireAdmin, router, pathname]);

  if (loading || !token) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[#0a0a0f] text-slate-200">
        <div className="flex flex-col items-center gap-4">
          <div className="relative w-16 h-16">
            <div className="absolute inset-0 rounded-full border-2 border-violet-500/20 animate-ping"></div>
            <div className="w-16 h-16 rounded-full border-4 border-t-violet-500 border-r-cyan-400 border-b-transparent border-l-transparent animate-spin"></div>
            <div className="absolute inset-0 flex items-center justify-center font-bold text-xs text-violet-400">
              NPC
            </div>
          </div>
          <p className="text-sm text-slate-400 font-medium tracking-wide animate-pulse">
            Syncing Neural Memory Matrix...
          </p>
        </div>
      </div>
    );
  }

  if (requireAdmin && user?.role !== 'admin') {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[#0a0a0f] text-slate-200">
        <div className="glass-card p-8 rounded-xl max-w-md text-center border border-red-500/30">
          <div className="text-red-400 text-3xl mb-3">⚠️</div>
          <h2 className="text-xl font-bold text-slate-100 mb-2">Access Denied</h2>
          <p className="text-sm text-slate-400 mb-4">
            Administrator clearance required to access this console.
          </p>
          <button
            onClick={() => router.push('/dashboard')}
            className="px-4 py-2 bg-violet-600 hover:bg-violet-500 text-white rounded-lg text-sm transition font-medium"
          >
            Return to Safety
          </button>
        </div>
      </div>
    );
  }

  return <>{children}</>;
}
