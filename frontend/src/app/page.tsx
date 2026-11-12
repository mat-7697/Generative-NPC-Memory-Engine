'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth';
import Link from 'next/link';

export default function HomePage() {
  const router = useRouter();
  const { token, loading } = useAuth();

  useEffect(() => {
    if (!loading) {
      if (token) {
        router.replace('/dashboard');
      } else {
        router.replace('/login');
      }
    }
  }, [token, loading, router]);

  return (
    <div className="min-h-[80vh] flex flex-col items-center justify-center text-center px-4">
      <div className="glass-card max-w-lg w-full p-8 rounded-2xl border border-violet-500/20 shadow-2xl relative overflow-hidden">
        <div className="absolute -top-24 -left-24 w-48 h-48 bg-violet-600/20 rounded-full blur-3xl pointer-events-none"></div>
        <div className="absolute -bottom-24 -right-24 w-48 h-48 bg-cyan-600/20 rounded-full blur-3xl pointer-events-none"></div>

        <div className="w-16 h-16 mx-auto mb-6 rounded-2xl bg-gradient-to-tr from-violet-600 to-cyan-400 p-[1px] shadow-lg shadow-violet-500/30">
          <div className="w-full h-full bg-[#0d0d15] rounded-2xl flex items-center justify-center text-3xl">
            🧠
          </div>
        </div>

        <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight bg-clip-text text-transparent bg-gradient-to-r from-violet-300 via-indigo-200 to-cyan-300 mb-3">
          Generative NPC Memory Engine
        </h1>

        <p className="text-sm text-slate-400 mb-6 leading-relaxed">
          Hybrid relational PostgreSQL database & Qdrant semantic vector memory
          synthesizer. Initializing neural connection...
        </p>

        <div className="flex items-center justify-center gap-3">
          <Link
            href="/login"
            className="px-5 py-2.5 rounded-xl bg-violet-600 hover:bg-violet-500 text-white font-medium text-xs tracking-wide shadow-lg shadow-violet-600/30 transition duration-150"
          >
            Enter Realm (Login)
          </Link>
          <Link
            href="/register"
            className="px-5 py-2.5 rounded-xl bg-white/5 hover:bg-white/10 text-slate-300 hover:text-white font-medium text-xs tracking-wide border border-white/10 transition duration-150"
          >
            Register Hero
          </Link>
        </div>
      </div>
    </div>
  );
}
