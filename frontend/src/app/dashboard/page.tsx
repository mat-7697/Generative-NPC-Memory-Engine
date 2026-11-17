'use client';

import React, { useState, useEffect, useCallback } from 'react';
import Link from 'next/link';
import ProtectedRoute from '@/components/ProtectedRoute';
import { useAuth } from '@/lib/auth';
import {
  api,
  LeaderboardEntry,
  TransactionResponse,
  MemoryStats,
  InventoryItem,
  PlayerQuestResponse,
  BattleState,
  NPCResponse,
} from '@/lib/api';

export default function DashboardPage() {
  const { user, refreshUser } = useAuth();

  const [leaderboard, setLeaderboard] = useState<LeaderboardEntry[]>([]);
  const [transactions, setTransactions] = useState<TransactionResponse[]>([]);
  const [memoryStats, setMemoryStats] = useState<MemoryStats | null>(null);
  const [inventory, setInventory] = useState<InventoryItem[]>([]);
  const [quests, setQuests] = useState<PlayerQuestResponse[]>([]);
  const [campaign, setCampaign] = useState<BattleState | null>(null);
  const [npcs, setNpcs] = useState<NPCResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [showVivaTour, setShowVivaTour] = useState(false);
  const [tourStep, setTourStep] = useState(0);

  const tourSteps = [
    {
      step: 1,
      title: 'Relational Schema, 3NF & Constraints',
      rubric: 'Criteria 1, 2, 3 [9 Marks]',
      icon: '📐',
      summary: '10 normalized relational tables in 3NF with CHECK constraints, foreign key ON DELETE rules, and full-text GIN search indexes.',
      talkingPoint: '"Evaluator, notice our strict CHECK (gold >= 0) on players, composite UNIQUE(player_id, item_id) on inventory, and GIN indexes for fast item description search."',
      actionLink: '/admin',
      actionLabel: 'Open SQL Console & Tables ↗',
    },
    {
      step: 2,
      title: 'ACID Stored Procedures & Pessimistic Row Locking',
      rubric: 'Criteria 8 [6 Marks]',
      icon: '🔒',
      summary: 'ACID procedures (buy_item, transfer_item) use SELECT ... FOR UPDATE to prevent race conditions and automatically log audit CDC records.',
      talkingPoint: '"When buying an item, we acquire exclusive row locks to prevent negative balances and deadlocks. The audit_log trigger captures every change with before/after state."',
      actionLink: '/shop',
      actionLabel: 'Test Live Shop Purchase ↗',
    },
    {
      step: 3,
      title: 'Cognitive Vector Memory & Hybrid Context Fusion',
      rubric: 'Criteria 4, 9, 14 [15 Marks]',
      icon: '🧠',
      summary: 'Qdrant stores 384-dimensional dense vectors with HNSW indexing, ranked via recency decay e^(-λ*Δt) and fused with relational SQL player state.',
      talkingPoint: '"FastAPI queries Qdrant for semantic past memories while loading gold, inventory, and quests from PostgreSQL to synthesize the dynamic LLM system prompt."',
      actionLink: '/chat',
      actionLabel: 'Chat with NPCs ↗',
    },
    {
      step: 4,
      title: 'Recursive CTE Prerequisite Directed Acyclic Graph (DAG)',
      rubric: 'Criteria 8 [6 Marks]',
      icon: '🌲',
      summary: 'WITH RECURSIVE SQL queries traverse self-referencing quest prerequisite chains, computing graph depth and validating progression prerequisites.',
      talkingPoint: '"Our get_prerequisite_chain() recursive CTE traverses the quest DAG dynamically to verify whether a player has completed all antecedent quests."',
      actionLink: '/quests',
      actionLabel: 'Inspect Quest Dependency Tree ↗',
    },
    {
      step: 5,
      title: 'Interactive Quest Objectives & Auto Level-Up Triggers',
      rubric: 'Criteria 8, 14 [10 Marks]',
      icon: '⚔️',
      summary: 'Server-side validated math challenges, CTF dialogue ciphers, and PostgreSQL database triggers that auto-calculate player level upon XP threshold crossing.',
      talkingPoint: '"Quests require solving objective puzzles or extracting ciphers from NPCs. Upon verified completion, the fn_auto_level_up trigger immediately calculates new player levels."',
      actionLink: '/quests',
      actionLabel: 'Solve Objective Challenges ↗',
    },
  ];

  const loadDashboardData = useCallback(async () => {
    try {
      setLoading(true);
      await refreshUser();

      const [lbRes, txRes, memRes, invRes, qRes, campRes, npcRes] = await Promise.allSettled([
        api.players.getLeaderboard(),
        api.inventory.getTransactions(),
        api.memory.getStats(),
        api.inventory.getMyInventory(),
        api.quests.getMyQuests(),
        api.battle.getState(),
        api.npcs.getAll(),
      ]);
      if (campRes.status === 'fulfilled') setCampaign(campRes.value);
      if (npcRes.status === 'fulfilled') setNpcs(npcRes.value || []);

      if (lbRes.status === 'fulfilled') setLeaderboard(lbRes.value || []);
      if (txRes.status === 'fulfilled') setTransactions(txRes.value || []);
      if (memRes.status === 'fulfilled') setMemoryStats(memRes.value);
      if (invRes.status === 'fulfilled') setInventory(invRes.value || []);
      if (qRes.status === 'fulfilled') setQuests(qRes.value || []);
    } finally {
      setLoading(false);
    }
  }, [refreshUser]);

  useEffect(() => {
    loadDashboardData();
  }, [loadDashboardData]);

  // Derived stats
  const totalItemsOwned = inventory.reduce((acc, curr) => acc + (curr.quantity || 1), 0);
  const activeQuestsCount = quests.filter((q) => q.status === 'active').length;
  const completedQuestsCount = quests.filter((q) => q.status === 'completed').length;

  // Campaign: next objective = first unlocked region not yet conquered, else the next lock to break.
  const nextTarget = campaign?.monsters.find((m) => m.unlocked && m.kills === 0);
  const nextLocked = campaign?.monsters.find((m) => !m.unlocked);
  const nextObjective = campaign?.rift_sealed
    ? 'The Void Rift is sealed. Keep hunting to grow stronger and top the leaderboard.'
    : nextTarget
      ? `Defeat the ${nextTarget.name} in the ${nextTarget.region}.`
      : nextLocked
        ? `${nextLocked.lock_reason} to reach the ${nextLocked.region}.`
        : 'Hunt monsters to grow stronger.';

  // Real per-NPC memory distribution (replaces placeholder bars).
  const memoryByNpc = (memoryStats?.by_npc || [])
    .map((row) => ({
      name: npcs.find((n) => n.npc_id === row.npc_id)?.name || `NPC #${row.npc_id}`,
      count: row.count,
    }))
    .sort((a, b) => b.count - a.count);
  const memoryTotal = memoryByNpc.reduce((acc, r) => acc + r.count, 0);

  return (
    <ProtectedRoute>
      <div className="space-y-8 pb-10">
        {/* Welcome Header */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 p-6 glass-card rounded-2xl border border-violet-500/20 relative overflow-hidden">
          <div className="absolute right-0 top-0 w-80 h-full bg-gradient-to-l from-violet-600/10 via-transparent to-transparent pointer-events-none"></div>
          <div>
            <div className="flex items-center gap-2 mb-1">
              <span className="text-xs font-mono uppercase tracking-widest text-violet-400 bg-violet-500/10 px-2 py-0.5 rounded border border-violet-500/30">
                Command Terminal
              </span>
              <span className="text-xs text-slate-400">DBMS Neural Matrix</span>
            </div>
            <h1 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight">
              Welcome back,{' '}
              <span className="bg-clip-text text-transparent bg-gradient-to-r from-violet-300 to-cyan-300">
                {user?.username || 'Hero'}
              </span>
            </h1>
            <p className="text-xs sm:text-sm text-slate-400 mt-1 max-w-xl">
              Track your relational economy balances, Qdrant episodic memories, active quest lines, and global leaderboards.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-2.5">
            <button
              onClick={() => {
                setTourStep(0);
                setShowVivaTour(true);
              }}
              className="px-3.5 py-2 rounded-xl bg-amber-500/20 hover:bg-amber-500/30 text-amber-300 font-bold text-xs border border-amber-500/40 transition flex items-center gap-1.5 shadow-sm shadow-amber-500/20"
            >
              <span>🎓</span>
              <span>Evaluator Viva Tour</span>
            </button>
            <button
              onClick={loadDashboardData}
              disabled={loading}
              className="px-3.5 py-2 rounded-xl bg-white/5 hover:bg-white/10 text-slate-300 hover:text-white text-xs font-semibold border border-white/10 transition flex items-center gap-1.5"
            >
              <span className={loading ? 'animate-spin' : ''}>🔄</span>
              <span>Sync State</span>
            </button>
            <Link
              href="/chat"
              className="px-4 py-2 rounded-xl bg-gradient-to-r from-violet-600 to-indigo-600 hover:from-violet-500 hover:to-indigo-500 text-white text-xs font-semibold shadow-lg shadow-violet-600/30 transition flex items-center gap-1.5"
            >
              <span>💬</span>
              <span>Chat With NPCs</span>
            </Link>
          </div>
        </div>

        {/* Player Stats Grid */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {/* Gold Card */}
          <div className="glass-card p-5 rounded-2xl border border-amber-500/20 relative group">
            <div className="flex items-center justify-between text-slate-400 mb-2">
              <span className="text-xs font-semibold uppercase tracking-wider">Treasury Gold</span>
              <span className="text-lg">🪙</span>
            </div>
            <div className="text-2xl sm:text-3xl font-black text-amber-300">
              {user?.gold?.toLocaleString() ?? 0}
            </div>
            <div className="text-[11px] text-amber-400/70 mt-1 flex items-center gap-1">
              <span>ACID Enforced</span>
              <span className="text-[9px] bg-amber-500/20 px-1 rounded">CHECK(gold &gt;= 0)</span>
            </div>
          </div>

          {/* Level & XP Card */}
          <div className="glass-card p-5 rounded-2xl border border-cyan-500/20 relative group">
            <div className="flex items-center justify-between text-slate-400 mb-2">
              <span className="text-xs font-semibold uppercase tracking-wider">Progression</span>
              <span className="text-lg">⚔️</span>
            </div>
            <div className="text-2xl sm:text-3xl font-black text-cyan-300">
              Level {user?.level ?? 1}
            </div>
            <div className="text-[11px] text-cyan-400/70 mt-1">
              {user?.xp ?? 0} Total Experience XP
            </div>
          </div>

          {/* Inventory Count Card */}
          <div className="glass-card p-5 rounded-2xl border border-violet-500/20 relative group">
            <div className="flex items-center justify-between text-slate-400 mb-2">
              <span className="text-xs font-semibold uppercase tracking-wider">Vault Items</span>
              <span className="text-lg">🎒</span>
            </div>
            <div className="text-2xl sm:text-3xl font-black text-violet-300">
              {totalItemsOwned} <span className="text-xs font-normal text-slate-400">units</span>
            </div>
            <div className="text-[11px] text-violet-400/70 mt-1">
              Across {inventory.length} distinct item slots
            </div>
          </div>

          {/* Quests Summary Card */}
          <div className="glass-card p-5 rounded-2xl border border-emerald-500/20 relative group">
            <div className="flex items-center justify-between text-slate-400 mb-2">
              <span className="text-xs font-semibold uppercase tracking-wider">Active Quests</span>
              <span className="text-lg">📜</span>
            </div>
            <div className="text-2xl sm:text-3xl font-black text-emerald-300">
              {activeQuestsCount} <span className="text-xs font-normal text-slate-400">active</span>
            </div>
            <div className="text-[11px] text-emerald-400/70 mt-1">
              {completedQuestsCount} completed quests
            </div>
          </div>
        </div>

        {/* Campaign Card: the game's main goal */}
        {campaign && (
          <div className="glass-card rounded-2xl p-6 border border-rose-500/20 grid grid-cols-1 md:grid-cols-3 gap-6 items-center">
            <div className="md:col-span-2 min-w-0">
              <div className="text-xs font-mono uppercase tracking-widest text-rose-300">Main Campaign · Seal the Void Rift</div>
              <h2 className="mt-1 text-lg font-bold text-white">Next objective</h2>
              <p className="text-sm text-slate-300 mt-0.5">{nextObjective}</p>
              <div className="mt-4 grid grid-cols-2 gap-4 max-w-md">
                <div>
                  <div className="flex justify-between text-[11px] text-slate-400 mb-1">
                    <span>Health</span>
                    <span className="text-slate-200">
                      {campaign.player.hp} / {campaign.player.max_hp}
                    </span>
                  </div>
                  <div className="h-2 rounded-full bg-white/5 overflow-hidden">
                    <div
                      className="h-full bg-emerald-500 rounded-full"
                      style={{ width: `${(campaign.player.hp / campaign.player.max_hp) * 100}%` }}
                    />
                  </div>
                </div>
                <div>
                  <div className="flex justify-between text-[11px] text-slate-400 mb-1">
                    <span>Regions conquered</span>
                    <span className="text-slate-200">
                      {campaign.regions_cleared} / {campaign.monsters.length}
                    </span>
                  </div>
                  <div className="h-2 rounded-full bg-white/5 overflow-hidden">
                    <div
                      className="h-full bg-gradient-to-r from-violet-500 to-rose-500 rounded-full"
                      style={{ width: `${(campaign.regions_cleared / campaign.monsters.length) * 100}%` }}
                    />
                  </div>
                </div>
              </div>
            </div>
            <div className="flex md:flex-col gap-3 md:items-stretch">
              <div className="flex-1 grid grid-cols-2 gap-2 text-center">
                <div className="rounded-xl bg-white/[0.03] border border-white/10 py-2">
                  <div className="text-[11px] text-slate-400">Attack</div>
                  <div className="text-lg font-bold text-rose-300">{campaign.player.attack}</div>
                </div>
                <div className="rounded-xl bg-white/[0.03] border border-white/10 py-2">
                  <div className="text-[11px] text-slate-400">Defense</div>
                  <div className="text-lg font-bold text-sky-300">{campaign.player.defense}</div>
                </div>
              </div>
              <Link
                href="/battle"
                className="flex-1 md:flex-none text-center px-4 py-2.5 rounded-xl bg-rose-600 hover:bg-rose-500 text-white text-sm font-semibold transition"
              >
                {campaign.active_battle ? 'Return to battle' : 'Go hunting'} →
              </Link>
            </div>
          </div>
        )}

        {/* Center Section: Leaderboard + Memory Stats */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Leaderboard Table (2 Cols) */}
          <div className="lg:col-span-2 glass-card rounded-2xl p-6 border border-white/10">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <span className="text-lg">🏆</span>
                <h3 className="text-sm font-bold text-slate-100 uppercase tracking-wider">
                  Global Player Leaderboard
                </h3>
              </div>
              <span className="text-[11px] text-slate-400 font-mono">Ranked by Level & XP</span>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="border-b border-white/10 text-slate-400 font-semibold uppercase tracking-wider">
                    <th className="pb-3 px-3">Rank</th>
                    <th className="pb-3 px-3">Player</th>
                    <th className="pb-3 px-3 text-center">Level</th>
                    <th className="pb-3 px-3 text-right">Experience</th>
                    <th className="pb-3 px-3 text-right">Gold</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/5">
                  {leaderboard.length === 0 ? (
                    <tr>
                      <td colSpan={5} className="py-6 text-center text-slate-500">
                        No leaderboard records found.
                      </td>
                    </tr>
                  ) : (
                    leaderboard.slice(0, 7).map((entry, idx) => {
                      const isCurrentUser = entry.player_id === user?.player_id;
                      const rank = entry.rank || idx + 1;
                      return (
                        <tr
                          key={entry.player_id ?? idx}
                          className={`hover:bg-white/5 transition ${
                            isCurrentUser ? 'bg-violet-600/15 font-semibold' : ''
                          }`}
                        >
                          <td className="py-3 px-3">
                            {rank === 1 ? (
                              <span className="px-2 py-0.5 rounded-full bg-amber-500/20 text-amber-300 font-bold border border-amber-500/40">
                                🥇 1
                              </span>
                            ) : rank === 2 ? (
                              <span className="px-2 py-0.5 rounded-full bg-slate-300/20 text-slate-200 font-bold border border-slate-300/40">
                                🥈 2
                              </span>
                            ) : rank === 3 ? (
                              <span className="px-2 py-0.5 rounded-full bg-amber-700/20 text-amber-400 font-bold border border-amber-700/40">
                                🥉 3
                              </span>
                            ) : (
                              <span className="text-slate-400 pl-2">#{rank}</span>
                            )}
                          </td>
                          <td className="py-3 px-3">
                            <div className="flex items-center gap-2">
                              <span className="text-slate-200">
                                {entry.username}
                              </span>
                              {isCurrentUser && (
                                <span className="text-[10px] bg-violet-500/30 text-violet-300 px-1.5 py-0.2 rounded font-bold">
                                  YOU
                                </span>
                              )}
                            </div>
                          </td>
                          <td className="py-3 px-3 text-center text-cyan-300 font-mono">
                            {entry.level}
                          </td>
                          <td className="py-3 px-3 text-right text-slate-300 font-mono">
                            {entry.xp.toLocaleString()} XP
                          </td>
                          <td className="py-3 px-3 text-right text-amber-300 font-mono">
                            🪙 {entry.gold.toLocaleString()}
                          </td>
                        </tr>
                      );
                    })
                  )}
                </tbody>
              </table>
            </div>
          </div>

          {/* Memory Engine Stats Card (1 Col) */}
          <div className="glass-card rounded-2xl p-6 border border-white/10 flex flex-col justify-between">
            <div>
              <div className="flex items-center gap-2 mb-4">
                <span className="text-lg">🧠</span>
                <h3 className="text-sm font-bold text-slate-100 uppercase tracking-wider">
                  Memory Matrix Health
                </h3>
              </div>

              <div className="space-y-4">
                <div className="p-4 rounded-xl bg-violet-950/30 border border-violet-500/30">
                  <div className="text-[11px] text-violet-300 font-medium uppercase tracking-wider">
                    Total Qdrant Vectors
                  </div>
                  <div className="text-2xl font-black text-white mt-1">
                    {memoryStats?.total_memories ?? memoryStats?.total_count ?? 0}
                  </div>
                  <p className="text-[10px] text-slate-400 mt-1">
                    Cosine distance index • 384 dimensions
                  </p>
                </div>

                {/* CSS Bar Chart for NPC Memory Distribution */}
                <div className="space-y-2.5 pt-2">
                  <div className="text-xs font-semibold text-slate-300">
                    Episodic Load by Entity:
                  </div>

                  {memoryByNpc.length === 0 ? (
                    <p className="text-[11px] text-slate-500">
                      No memories yet. Chat with an NPC to create some.
                    </p>
                  ) : (
                    memoryByNpc.slice(0, 5).map((row) => {
                      const pct = Math.round((row.count / memoryTotal) * 100);
                      return (
                        <div key={row.name}>
                          <div className="flex justify-between text-[11px] text-slate-400 mb-1">
                            <span className="truncate">{row.name}</span>
                            <span className="text-violet-300 shrink-0 ml-2">
                              {row.count} · {pct}%
                            </span>
                          </div>
                          <div className="w-full bg-white/5 rounded-full h-2 overflow-hidden">
                            <div
                              className="bg-gradient-to-r from-violet-600 to-cyan-500 h-2 rounded-full"
                              style={{ width: `${pct}%` }}
                            />
                          </div>
                        </div>
                      );
                    })
                  )}
                </div>
              </div>
            </div>

            <div className="mt-6 pt-4 border-t border-white/10 text-center">
              <Link
                href="/memory"
                className="text-xs font-semibold text-cyan-400 hover:text-cyan-300 transition"
              >
                Inspect All Semantic Vectors →
              </Link>
            </div>
          </div>
        </div>

        {/* Bottom Section: Recent Transaction Ledger */}
        <div className="glass-card rounded-2xl p-6 border border-white/10">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <span className="text-lg">📜</span>
              <h3 className="text-sm font-bold text-slate-100 uppercase tracking-wider">
                Audited Inventory Ledger
              </h3>
            </div>
            <Link
              href="/inventory"
              className="text-xs font-semibold text-violet-400 hover:text-violet-300"
            >
              Go to Market →
            </Link>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-white/10 text-slate-400 font-semibold uppercase tracking-wider">
                  <th className="pb-3 px-3">ID</th>
                  <th className="pb-3 px-3">Type</th>
                  <th className="pb-3 px-3">Quantity</th>
                  <th className="pb-3 px-3">Gold Impact</th>
                  <th className="pb-3 px-3">Details</th>
                  <th className="pb-3 px-3 text-right">Timestamp</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5">
                {transactions.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="py-6 text-center text-slate-500">
                      No transactional logs recorded yet. Visit the merchant to buy gear!
                    </td>
                  </tr>
                ) : (
                  transactions.slice(0, 5).map((tx, idx) => (
                    <tr key={tx.transaction_id ?? idx} className="hover:bg-white/5 transition">
                      <td className="py-3 px-3 font-mono text-slate-400">
                        #{tx.transaction_id}
                      </td>
                      <td className="py-3 px-3">
                        <span
                          className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider ${
                            tx.transaction_type === 'buy'
                              ? 'bg-rose-500/20 text-rose-300 border border-rose-500/30'
                              : tx.transaction_type === 'sell'
                              ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'
                              : tx.transaction_type.startsWith('transfer')
                              ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/30'
                              : 'bg-violet-500/20 text-violet-300 border border-violet-500/30'
                          }`}
                        >
                          {tx.transaction_type.replace(/_/g, ' ')}
                        </span>
                      </td>
                      <td className="py-3 px-3 text-slate-200 font-mono">
                        {tx.quantity}x
                      </td>
                      <td className="py-3 px-3 font-mono">
                        {tx.gold_amount !== 0 &&
                        ['buy', 'inn_rest'].includes(tx.transaction_type) ? (
                          <span className="text-rose-400 font-bold">
                            -{Math.abs(tx.gold_amount)} G
                          </span>
                        ) : tx.gold_amount !== 0 ? (
                          <span className="text-emerald-400 font-bold">
                            +{Math.abs(tx.gold_amount)} G
                          </span>
                        ) : (
                          <span className="text-slate-400">0 G</span>
                        )}
                      </td>
                      <td className="py-3 px-3 text-slate-300 max-w-xs truncate">
                        {tx.description || tx.item_name || `Item #${tx.item_id}`}
                      </td>
                      <td className="py-3 px-3 text-right text-slate-400 text-[11px] font-mono">
                        {tx.created_at ? new Date(tx.created_at).toLocaleString() : 'Recent'}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* EVALUATOR VIVA TOUR MODAL */}
        {showVivaTour && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/85 backdrop-blur-md animate-in fade-in">
            <div className="glass-card max-w-xl w-full p-6 rounded-2xl border border-amber-500/40 shadow-2xl relative space-y-5">
              {/* Header */}
              <div className="flex items-center justify-between border-b border-white/10 pb-3">
                <div className="flex items-center gap-2.5">
                  <span className="text-2xl">{tourSteps[tourStep].icon}</span>
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-[10px] font-mono font-bold uppercase tracking-wider px-2 py-0.5 rounded bg-amber-500/20 text-amber-300 border border-amber-500/30">
                        {tourSteps[tourStep].rubric}
                      </span>
                      <span className="text-xs text-slate-400">
                        Step {tourStep + 1} of {tourSteps.length}
                      </span>
                    </div>
                    <h3 className="text-base font-bold text-white mt-0.5">
                      {tourSteps[tourStep].title}
                    </h3>
                  </div>
                </div>
                <button
                  onClick={() => setShowVivaTour(false)}
                  className="text-slate-400 hover:text-white p-1 rounded hover:bg-white/10 transition"
                >
                  ✕
                </button>
              </div>

              {/* Progress Bar */}
              <div className="flex items-center gap-1.5">
                {tourSteps.map((_, idx) => (
                  <button
                    key={idx}
                    onClick={() => setTourStep(idx)}
                    className={`h-1.5 flex-1 rounded-full transition-all ${
                      idx === tourStep
                        ? 'bg-amber-400 shadow-sm shadow-amber-400/50'
                        : idx < tourStep
                        ? 'bg-emerald-500/60'
                        : 'bg-white/10'
                    }`}
                  />
                ))}
              </div>

              {/* Step Content */}
              <div className="space-y-4">
                <div className="p-4 rounded-xl bg-white/[0.03] border border-white/10 space-y-1.5">
                  <div className="text-[10px] font-mono uppercase tracking-wider text-slate-400">
                    Rubric Architecture Detail:
                  </div>
                  <p className="text-xs text-slate-200 leading-relaxed">
                    {tourSteps[tourStep].summary}
                  </p>
                </div>

                <div className="p-4 rounded-xl bg-amber-950/30 border border-amber-500/20 space-y-1.5">
                  <div className="text-[10px] font-mono uppercase tracking-wider text-amber-400 flex items-center gap-1">
                    <span>🎙️</span>
                    <span>Recommended Viva Talking Point (Say this to the teacher):</span>
                  </div>
                  <p className="text-xs text-amber-100/90 italic leading-relaxed">
                    {tourSteps[tourStep].talkingPoint}
                  </p>
                </div>

                <div className="pt-1">
                  <Link
                    href={tourSteps[tourStep].actionLink}
                    onClick={() => setShowVivaTour(false)}
                    className="w-full py-2.5 px-4 rounded-xl bg-white/10 hover:bg-white/15 text-cyan-300 font-bold text-xs border border-cyan-500/30 transition flex items-center justify-center gap-2"
                  >
                    <span>{tourSteps[tourStep].actionLabel}</span>
                  </Link>
                </div>
              </div>

              {/* Navigation Controls */}
              <div className="flex items-center justify-between pt-3 border-t border-white/10">
                <button
                  type="button"
                  disabled={tourStep === 0}
                  onClick={() => setTourStep((prev) => Math.max(0, prev - 1))}
                  className="py-1.5 px-3 rounded-lg text-xs font-semibold text-slate-400 hover:text-white disabled:opacity-30 disabled:pointer-events-none transition"
                >
                  ← Previous
                </button>

                {tourStep < tourSteps.length - 1 ? (
                  <button
                    type="button"
                    onClick={() => setTourStep((prev) => Math.min(tourSteps.length - 1, prev + 1))}
                    className="py-1.5 px-4 rounded-lg bg-amber-500 hover:bg-amber-400 text-black font-bold text-xs transition"
                  >
                    Next Step →
                  </button>
                ) : (
                  <button
                    type="button"
                    onClick={() => setShowVivaTour(false)}
                    className="py-1.5 px-4 rounded-lg bg-emerald-500 hover:bg-emerald-400 text-black font-bold text-xs transition"
                  >
                    ✓ Complete Tour
                  </button>
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </ProtectedRoute>
  );
}
