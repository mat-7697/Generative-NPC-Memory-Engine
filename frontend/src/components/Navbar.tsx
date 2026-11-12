'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth';

const NAV_ITEMS = [
  { label: 'Dashboard', href: '/dashboard', icon: '⚡' },
  { label: 'NPC Dialogue', href: '/chat', icon: '💬' },
  { label: 'Market & Vault', href: '/inventory', icon: '🎒' },
  { label: 'Quest Log', href: '/quests', icon: '📜' },
  { label: 'Memory Core', href: '/memory', icon: '🧠' },
];

export default function Navbar() {
  const pathname = usePathname();
  const router = useRouter();
  const { user, token, logout } = useAuth();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  // If not authenticated or on login/register pages, do not display full nav bar
  if (!token || pathname === '/login' || pathname === '/register') {
    return null;
  }

  const handleLogout = () => {
    logout();
    router.push('/login');
  };

  return (
    <header className="sticky top-0 z-50 w-full glass-panel border-b border-white/10 backdrop-blur-md">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          {/* Logo & Game Branding */}
          <div className="flex items-center gap-3">
            <Link
              href="/dashboard"
              className="flex items-center gap-2.5 group focus:outline-none"
            >
              <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-violet-600 via-indigo-600 to-cyan-400 p-[1px] shadow-lg shadow-violet-500/20 group-hover:shadow-violet-500/40 transition">
                <div className="w-full h-full bg-[#0e0e17] rounded-xl flex items-center justify-center text-lg">
                  🤖
                </div>
              </div>
              <div className="flex flex-col">
                <span className="text-base font-extrabold tracking-wider bg-clip-text text-transparent bg-gradient-to-r from-violet-300 via-indigo-200 to-cyan-300">
                  GEN NPC
                </span>
                <span className="text-[10px] text-slate-400 tracking-widest font-mono uppercase">
                  Memory Engine
                </span>
              </div>
            </Link>

            {/* Desktop Navigation Links */}
            <nav className="hidden md:flex items-center gap-1 ml-6">
              {NAV_ITEMS.map((item) => {
                const isActive = pathname === item.href;
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    className={`flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-xs font-medium transition duration-150 ${
                      isActive
                        ? 'bg-violet-600/25 text-violet-300 border border-violet-500/40 shadow-sm shadow-violet-500/20'
                        : 'text-slate-300 hover:text-white hover:bg-white/5 border border-transparent'
                    }`}
                  >
                    <span>{item.icon}</span>
                    <span>{item.label}</span>
                  </Link>
                );
              })}

              {/* Admin Link (Only for admins) */}
              {user?.role === 'admin' && (
                <Link
                  href="/admin"
                  className={`flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-xs font-semibold tracking-wide transition duration-150 ${
                    pathname === '/admin'
                      ? 'bg-amber-500/20 text-amber-300 border border-amber-500/50 shadow-sm shadow-amber-500/20'
                      : 'text-amber-400/90 hover:text-amber-300 hover:bg-amber-500/10 border border-amber-500/20'
                  }`}
                >
                  <span>🛡️</span>
                  <span>Admin Hub</span>
                </Link>
              )}
            </nav>
          </div>

          {/* User Status Bar & Economy Pill */}
          <div className="hidden lg:flex items-center gap-4">
            {/* Gold Balance */}
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-amber-500/10 border border-amber-500/30 text-amber-300 text-xs font-bold shadow-sm shadow-amber-500/10">
              <span className="text-amber-400 text-sm">🪙</span>
              <span>{user?.gold?.toLocaleString() ?? 0}</span>
              <span className="text-[10px] text-amber-400/70 font-normal">GOLD</span>
            </div>

            {/* Player Level & XP Badge */}
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-cyan-500/10 border border-cyan-500/30 text-cyan-300 text-xs font-medium">
              <span className="text-xs">⚔️</span>
              <span>Lv. {user?.level ?? 1}</span>
              <span className="text-[10px] text-cyan-400/70">({user?.xp ?? 0} XP)</span>
            </div>

            {/* User Profile & Role */}
            <div className="flex items-center gap-3 pl-2 border-l border-white/10">
              <div className="flex flex-col text-right">
                <span className="text-xs font-semibold text-slate-100 flex items-center justify-end gap-1.5">
                  {user?.username || 'Hero'}
                  {user?.role === 'admin' ? (
                    <span className="px-1.5 py-0.2 text-[9px] uppercase font-bold rounded bg-amber-500/20 text-amber-300 border border-amber-500/40">
                      ADMIN
                    </span>
                  ) : (
                    <span className="px-1.5 py-0.2 text-[9px] uppercase font-bold rounded bg-violet-500/20 text-violet-300 border border-violet-500/40">
                      PLAYER
                    </span>
                  )}
                </span>
                <span className="text-[10px] text-slate-400">ID #{user?.player_id}</span>
              </div>

              {/* Logout Button */}
              <button
                onClick={handleLogout}
                title="Disconnect Account"
                className="p-2 rounded-lg bg-red-500/10 hover:bg-red-500/20 text-red-400 hover:text-red-300 border border-red-500/20 transition text-xs"
              >
                🚪
              </button>
            </div>
          </div>

          {/* Mobile Menu Button */}
          <div className="flex md:hidden items-center gap-2">
            <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-amber-500/10 border border-amber-500/30 text-amber-300 text-xs font-bold">
              <span>🪙</span>
              <span>{user?.gold ?? 0}</span>
            </div>
            <button
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              className="p-2 rounded-lg bg-white/5 border border-white/10 text-slate-300 hover:text-white"
            >
              {mobileMenuOpen ? '✕' : '☰'}
            </button>
          </div>
        </div>
      </div>

      {/* Mobile Dropdown Menu */}
      {mobileMenuOpen && (
        <div className="md:hidden glass-panel border-b border-white/10 px-4 pt-2 pb-4 space-y-2">
          <div className="flex items-center justify-between pb-3 border-b border-white/10 mb-2">
            <div className="text-xs text-slate-200">
              <span className="font-bold text-violet-300">{user?.username}</span> (Lv. {user?.level})
            </div>
            <button
              onClick={handleLogout}
              className="text-xs text-red-400 hover:underline"
            >
              Logout
            </button>
          </div>
          {NAV_ITEMS.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              onClick={() => setMobileMenuOpen(false)}
              className={`flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium ${
                pathname === item.href
                  ? 'bg-violet-600/30 text-violet-300'
                  : 'text-slate-300 hover:bg-white/5'
              }`}
            >
              <span>{item.icon}</span>
              <span>{item.label}</span>
            </Link>
          ))}
          {user?.role === 'admin' && (
            <Link
              href="/admin"
              onClick={() => setMobileMenuOpen(false)}
              className="flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-semibold text-amber-300 bg-amber-500/10 border border-amber-500/20"
            >
              <span>🛡️</span>
              <span>Admin Hub</span>
            </Link>
          )}
        </div>
      )}
    </header>
  );
}
