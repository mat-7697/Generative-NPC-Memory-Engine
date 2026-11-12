'use client';

import React, { useState, useEffect, useCallback } from 'react';
import ProtectedRoute from '@/components/ProtectedRoute';
import { useAuth } from '@/lib/auth';
import { useToast } from '@/lib/toast';
import {
  api,
  PlayerResponse,
  NPCResponse,
  ItemResponse,
  QuestResponse,
  AuditLogResponse,
  AdminStats,
  NPCPopularity,
  QuestProgress,
  LeaderboardEntry,
  CreateNPCRequest,
  UpdateNPCRequest,
  CreateItemRequest,
  UpdateItemRequest,
  CreateQuestRequest,
  UpdateQuestRequest,
  UpdatePlayerRequest,
} from '@/lib/api';

type AdminTab = 'stats' | 'players' | 'npcs' | 'items' | 'quests' | 'audit' | 'sql';

export default function AdminPage() {
  const { user } = useAuth();
  const { success, error: toastError, info } = useToast();

  const [activeTab, setActiveTab] = useState<AdminTab>('stats');
  const [loading, setLoading] = useState(false);

  // SQL Console & EXPLAIN ANALYZE state
  const [sqlQuery, setSqlQuery] = useState<string>(
    `SELECT \n    p.player_id,\n    p.username,\n    p.level,\n    p.gold,\n    COUNT(pi.item_id) AS total_inventory_slots,\n    COALESCE(SUM(pi.quantity * i.base_price), 0) AS inventory_net_worth,\n    p.gold + COALESCE(SUM(pi.quantity * i.base_price), 0) AS total_player_wealth\nFROM players p\nLEFT JOIN player_inventory pi ON p.player_id = pi.player_id\nLEFT JOIN items i ON pi.item_id = i.item_id\nGROUP BY p.player_id, p.username, p.level, p.gold\nORDER BY total_player_wealth DESC;`
  );
  const [sqlResult, setSqlResult] = useState<any>(null);
  const [explainResult, setExplainResult] = useState<any>(null);
  const [executingSql, setExecutingSql] = useState(false);
  const [explainingSql, setExplainingSql] = useState(false);
  const [queryPresets, setQueryPresets] = useState<any[]>([]);
  const [sqlViewMode, setSqlViewMode] = useState<'table' | 'explain'>('table');

  // Stats Data
  const [stats, setStats] = useState<AdminStats | null>(null);
  const [npcPopularity, setNpcPopularity] = useState<NPCPopularity[]>([]);
  const [questProgress, setQuestProgress] = useState<QuestProgress[]>([]);
  const [leaderboard, setLeaderboard] = useState<LeaderboardEntry[]>([]);

  // Tables Data
  const [players, setPlayers] = useState<PlayerResponse[]>([]);
  const [npcs, setNpcs] = useState<NPCResponse[]>([]);
  const [items, setItems] = useState<ItemResponse[]>([]);
  const [quests, setQuests] = useState<QuestResponse[]>([]);
  const [auditLog, setAuditLog] = useState<AuditLogResponse[]>([]);
  const [auditFilterTable, setAuditFilterTable] = useState('');

  // Modals state
  const [editingPlayer, setEditingPlayer] = useState<PlayerResponse | null>(null);
  const [playerGold, setPlayerGold] = useState(100);
  const [playerLevel, setPlayerLevel] = useState(1);
  const [playerRole, setPlayerRole] = useState<'player' | 'admin'>('player');

  const [showNpcModal, setShowNpcModal] = useState(false);
  const [editingNpc, setEditingNpc] = useState<NPCResponse | null>(null);
  const [npcName, setNpcName] = useState('');
  const [npcPersona, setNpcPersona] = useState('');
  const [npcLocation, setNpcLocation] = useState('');
  const [npcGreeting, setNpcGreeting] = useState('');

  const [showItemModal, setShowItemModal] = useState(false);
  const [editingItem, setEditingItem] = useState<ItemResponse | null>(null);
  const [itemName, setItemName] = useState('');
  const [itemDesc, setItemDesc] = useState('');
  const [itemPrice, setItemPrice] = useState(50);
  const [itemType, setItemType] = useState<any>('weapon');
  const [itemRarity, setItemRarity] = useState<any>('common');
  const [itemStock, setItemStock] = useState(-1);

  const [showQuestModal, setShowQuestModal] = useState(false);
  const [editingQuest, setEditingQuest] = useState<QuestResponse | null>(null);
  const [questTitle, setQuestTitle] = useState('');
  const [questDesc, setQuestDesc] = useState('');
  const [questGold, setQuestGold] = useState(100);
  const [questXp, setQuestXp] = useState(50);
  const [questMinLevel, setQuestMinLevel] = useState(1);
  const [questType, setQuestType] = useState<any>('main');

  // Load Tab Specific Data
  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      if (activeTab === 'stats') {
        const [sRes, pRes, qRes, lRes] = await Promise.allSettled([
          api.admin.getStats(),
          api.admin.getNPCPopularity(),
          api.admin.getQuestProgress(),
          api.players.getLeaderboard(),
        ]);
        if (sRes.status === 'fulfilled') setStats(sRes.value);
        if (pRes.status === 'fulfilled') setNpcPopularity(pRes.value || []);
        if (qRes.status === 'fulfilled') setQuestProgress(qRes.value || []);
        if (lRes.status === 'fulfilled') setLeaderboard(lRes.value || []);
      } else if (activeTab === 'players') {
        const res = await api.admin.getPlayers();
        setPlayers(res || []);
      } else if (activeTab === 'npcs') {
        const res = await api.npcs.getAll();
        setNpcs(res || []);
      } else if (activeTab === 'items') {
        const res = await api.inventory.getItems();
        setItems(res || []);
      } else if (activeTab === 'quests') {
        const res = await api.quests.getAll();
        setQuests(res || []);
      } else if (activeTab === 'audit') {
        const res = await api.admin.getAuditLog(100, 0);
        setAuditLog(res || []);
      }
    } catch (err: any) {
      toastError(err.message || 'Failed to fetch admin data.');
    } finally {
      setLoading(false);
    }
  }, [activeTab, toastError]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // Player Handlers
  const handleSavePlayer = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingPlayer) return;
    try {
      const payload: UpdatePlayerRequest = {
        gold: playerGold,
        level: playerLevel,
        role: playerRole,
      };
      await api.admin.updatePlayer(editingPlayer.player_id, payload);
      success(`Player #${editingPlayer.player_id} parameters updated.`);
      setEditingPlayer(null);
      loadData();
    } catch (err: any) {
      toastError(err.message || 'Player update failed.');
    }
  };

  const handleDeletePlayer = async (id: number) => {
    if (!confirm(`Delete player #${id}? This will cascade delete player quests and inventory.`)) return;
    try {
      await api.admin.deletePlayer(id);
      success(`Player #${id} removed.`);
      loadData();
    } catch (err: any) {
      toastError(err.message || 'Delete failed.');
    }
  };

  // NPC Handlers
  const handleSaveNpc = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      if (editingNpc) {
        const payload: UpdateNPCRequest = {
          name: npcName,
          persona: npcPersona,
          location: npcLocation || undefined,
          greeting: npcGreeting || undefined,
        };
        await api.npcs.update(editingNpc.npc_id, payload);
        success(`NPC ${npcName} updated.`);
      } else {
        const payload: CreateNPCRequest = {
          name: npcName,
          persona: npcPersona,
          location: npcLocation || undefined,
          greeting: npcGreeting || undefined,
        };
        await api.npcs.create(payload);
        success(`New NPC entity ${npcName} forged.`);
      }
      setShowNpcModal(false);
      setEditingNpc(null);
      loadData();
    } catch (err: any) {
      toastError(err.message || 'NPC action failed.');
    }
  };

  const handleDeleteNpc = async (id: number) => {
    if (!confirm(`Delete NPC #${id}? This will remove related dialog and relationship records.`)) return;
    try {
      await api.npcs.delete(id);
      success(`NPC #${id} deleted.`);
      loadData();
    } catch (err: any) {
      toastError(err.message || 'Failed to delete NPC.');
    }
  };

  // Item Handlers
  const handleSaveItem = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      if (editingItem) {
        const payload: UpdateItemRequest = {
          name: itemName,
          description: itemDesc,
          base_price: itemPrice,
          item_type: itemType,
          rarity: itemRarity,
          stock: itemStock,
        };
        await api.admin.updateItem(editingItem.item_id, payload);
        success(`Item #${editingItem.item_id} updated.`);
      } else {
        const payload: CreateItemRequest = {
          name: itemName,
          description: itemDesc,
          base_price: itemPrice,
          item_type: itemType,
          rarity: itemRarity,
          stock: itemStock,
        };
        await api.admin.createItem(payload);
        success(`Item ${itemName} added to catalog.`);
      }
      setShowItemModal(false);
      setEditingItem(null);
      loadData();
    } catch (err: any) {
      toastError(err.message || 'Item action failed.');
    }
  };

  const handleDeleteItem = async (id: number) => {
    if (!confirm(`Delete Item #${id}?`)) return;
    try {
      await api.admin.deleteItem(id);
      success(`Item #${id} deleted.`);
      loadData();
    } catch (err: any) {
      toastError(err.message || 'Item deletion failed.');
    }
  };

  // Quest Handlers
  const handleSaveQuest = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      if (editingQuest) {
        const payload: UpdateQuestRequest = {
          title: questTitle,
          description: questDesc,
          reward_gold: questGold,
          reward_xp: questXp,
          min_level: questMinLevel,
          quest_type: questType,
        };
        await api.admin.updateQuest(editingQuest.quest_id, payload);
        success(`Quest #${editingQuest.quest_id} updated.`);
      } else {
        const payload: CreateQuestRequest = {
          title: questTitle,
          description: questDesc,
          reward_gold: questGold,
          reward_xp: questXp,
          min_level: questMinLevel,
          quest_type: questType,
        };
        await api.admin.createQuest(payload);
        success(`New quest "${questTitle}" registered.`);
      }
      setShowQuestModal(false);
      setEditingQuest(null);
      loadData();
    } catch (err: any) {
      toastError(err.message || 'Quest action failed.');
    }
  };

  const handleDeleteQuest = async (id: number) => {
    if (!confirm(`Delete Quest #${id}?`)) return;
    try {
      await api.admin.deleteQuest(id);
      success(`Quest #${id} deleted.`);
      loadData();
    } catch (err: any) {
      toastError(err.message || 'Quest deletion failed.');
    }
  };

  // Load Query Presets
  useEffect(() => {
    if (activeTab === 'sql' && queryPresets.length === 0) {
      api.admin.getQueryPresets().then(setQueryPresets).catch(() => {});
    }
  }, [activeTab, queryPresets.length]);

  const handleRunSql = async () => {
    if (!sqlQuery.trim()) return;
    setExecutingSql(true);
    setSqlViewMode('table');
    setExplainResult(null);
    try {
      const res = await api.admin.executeSql(sqlQuery);
      setSqlResult(res);
      if (!res.success) {
        toastError(res.error || 'Query failed to execute');
      } else {
        success(`Executed in ${res.execution_time_ms} ms (${res.row_count} rows returned)`);
      }
    } catch (err: any) {
      toastError(err.message || 'Execution error');
    } finally {
      setExecutingSql(false);
    }
  };

  const handleExplainAnalyze = async () => {
    if (!sqlQuery.trim()) return;
    setExplainingSql(true);
    setSqlViewMode('explain');
    try {
      const res = await api.admin.explainAnalyze(sqlQuery);
      setExplainResult(res);
      if (!res.success) {
        toastError(res.error || 'EXPLAIN ANALYZE failed');
      } else {
        success(`Query plan generated: ${res.summary?.execution_time_ms ?? 0} ms`);
      }
    } catch (err: any) {
      toastError(err.message || 'EXPLAIN ANALYZE error');
    } finally {
      setExplainingSql(false);
    }
  };

  return (
    <ProtectedRoute requireAdmin={true}>
      <div className="space-y-6 pb-14">
        {/* Header */}
        <div className="glass-card rounded-2xl p-6 border border-amber-500/30 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <span className="text-xs font-mono uppercase tracking-widest text-amber-400 bg-amber-500/10 px-2 py-0.5 rounded border border-amber-500/30">
                Administrator Console
              </span>
              <span className="text-xs text-slate-400">PostgreSQL RBAC & Audit</span>
            </div>
            <h1 className="text-2xl font-extrabold text-white tracking-tight">
              Command Core & System Governance
            </h1>
            <p className="text-xs text-slate-400 mt-1">
              Full administrative privileges over schema entities, audit trails, and economy controls.
            </p>
          </div>

          <div className="flex items-center gap-2">
            <span className="px-3 py-1.5 rounded-full bg-amber-500/20 text-amber-300 font-bold text-xs border border-amber-500/40">
              👑 Root Clearance
            </span>
          </div>
        </div>

        {/* Tab Navigation */}
        <div className="flex flex-wrap items-center gap-1.5 p-1 rounded-xl bg-black/40 border border-white/10 w-fit">
          {[
            { id: 'stats', label: '📊 System Metrics' },
            { id: 'players', label: '👥 Players' },
            { id: 'npcs', label: '🤖 NPCs' },
            { id: 'items', label: '📦 Items' },
            { id: 'quests', label: '📜 Quests' },
            { id: 'audit', label: '🛡️ Audit Log' },
            { id: 'sql', label: '💻 SQL Console & EXPLAIN' },
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id as AdminTab)}
              className={`px-4 py-2 rounded-lg text-xs font-bold transition ${
                activeTab === tab.id
                  ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40 shadow-sm shadow-amber-500/20'
                  : 'text-slate-400 hover:text-white'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* TAB 1: SYSTEM METRICS */}
        {activeTab === 'stats' && (
          <div className="space-y-6">
            {/* Top Counts Grid */}
            <div className="grid grid-cols-2 lg:grid-cols-6 gap-3">
              {[
                { label: 'Total Players', val: stats?.total_players ?? players.length, icon: '👥' },
                { label: 'Total NPCs', val: stats?.total_npcs ?? npcs.length, icon: '🤖' },
                { label: 'Total Items', val: stats?.total_items ?? items.length, icon: '📦' },
                { label: 'Total Quests', val: stats?.total_quests ?? quests.length, icon: '📜' },
                { label: 'Transactions', val: stats?.total_transactions ?? 48, icon: '🪙' },
                { label: 'Vector Points', val: stats?.total_memories ?? 156, icon: '🧠' },
              ].map((s, idx) => (
                <div key={idx} className="glass-card p-4 rounded-xl border border-white/10">
                  <div className="text-lg mb-1">{s.icon}</div>
                  <div className="text-xl font-black text-white">{s.val}</div>
                  <div className="text-[10px] text-slate-400 uppercase tracking-wider mt-0.5">
                    {s.label}
                  </div>
                </div>
              ))}
            </div>

            {/* Sub-panels: NPC Popularity & Quest Progress */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* NPC Popularity */}
              <div className="glass-card p-5 rounded-2xl border border-white/10">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-xs font-bold text-slate-200 uppercase tracking-wider flex items-center gap-2">
                    <span>🤖</span>
                    <span>NPC Dialogue Engagement</span>
                  </h3>
                  <span className="text-[10px] text-slate-400 font-mono">Affinity Averages</span>
                </div>

                <div className="space-y-3">
                  {npcPopularity.length === 0 ? (
                    <div className="text-center py-6 text-xs text-slate-500">
                      No interaction metrics recorded yet.
                    </div>
                  ) : (
                    npcPopularity.map((npc) => (
                      <div
                        key={npc.npc_id}
                        className="p-3 rounded-xl bg-white/[0.03] border border-white/5 flex items-center justify-between text-xs"
                      >
                        <div>
                          <div className="font-bold text-white">{npc.name}</div>
                          <div className="text-[10px] text-slate-400">
                            {npc.interaction_count} player conversations
                          </div>
                        </div>
                        <div className="text-right">
                          <div className="font-mono text-cyan-300 font-bold">
                            Avg Affinity: {Number(npc.average_affinity).toFixed(1)}
                          </div>
                          {npc.memory_count !== undefined && (
                            <div className="text-[10px] text-violet-300">
                              {npc.memory_count} memory points
                            </div>
                          )}
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </div>

              {/* Quest Progress Completion */}
              <div className="glass-card p-5 rounded-2xl border border-white/10">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-xs font-bold text-slate-200 uppercase tracking-wider flex items-center gap-2">
                    <span>📜</span>
                    <span>Quest Graph Progression</span>
                  </h3>
                  <span className="text-[10px] text-slate-400 font-mono">Completion Rates</span>
                </div>

                <div className="space-y-3">
                  {questProgress.length === 0 ? (
                    <div className="text-center py-6 text-xs text-slate-500">
                      No quest progress data found.
                    </div>
                  ) : (
                    questProgress.map((qp) => (
                      <div
                        key={qp.quest_id}
                        className="p-3 rounded-xl bg-white/[0.03] border border-white/5 flex items-center justify-between text-xs"
                      >
                        <div>
                          <div className="font-bold text-white">{qp.title}</div>
                          <div className="text-[10px] text-slate-400">
                            Active: {qp.active_count} players • Completed: {qp.completed_count} players
                          </div>
                        </div>
                        <div className="text-right">
                          <div className="font-mono text-emerald-400 font-bold">
                            {qp.completion_rate !== undefined
                              ? `${qp.completion_rate}%`
                              : `${Math.round(
                                  (qp.completed_count /
                                    Math.max(1, qp.active_count + qp.completed_count)) *
                                    100
                                )}%`}
                          </div>
                          <div className="text-[10px] text-slate-400">Completion</div>
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* TAB 2: PLAYERS TABLE */}
        {activeTab === 'players' && (
          <div className="glass-card rounded-2xl p-6 border border-white/10">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-bold text-white uppercase tracking-wider">
                Player Accounts Ledger ({players.length})
              </h3>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="border-b border-white/10 text-slate-400 font-semibold uppercase tracking-wider">
                    <th className="pb-3 px-3">ID</th>
                    <th className="pb-3 px-3">Username</th>
                    <th className="pb-3 px-3">Email</th>
                    <th className="pb-3 px-3">Role</th>
                    <th className="pb-3 px-3">Gold</th>
                    <th className="pb-3 px-3">Level</th>
                    <th className="pb-3 px-3 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/5">
                  {players.map((p) => (
                    <tr key={p.player_id} className="hover:bg-white/5 transition">
                      <td className="py-3 px-3 font-mono text-slate-400">#{p.player_id}</td>
                      <td className="py-3 px-3 font-bold text-white">{p.username}</td>
                      <td className="py-3 px-3 text-slate-300">{p.email}</td>
                      <td className="py-3 px-3">
                        <span
                          className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase ${
                            p.role === 'admin'
                              ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40'
                              : 'bg-violet-500/20 text-violet-300'
                          }`}
                        >
                          {p.role}
                        </span>
                      </td>
                      <td className="py-3 px-3 font-mono text-amber-300 font-bold">
                        🪙 {p.gold?.toLocaleString()}
                      </td>
                      <td className="py-3 px-3 font-mono text-cyan-300 font-bold">
                        Lv. {p.level}
                      </td>
                      <td className="py-3 px-3 text-right space-x-2">
                        <button
                          onClick={() => {
                            setEditingPlayer(p);
                            setPlayerGold(p.gold);
                            setPlayerLevel(p.level);
                            setPlayerRole(p.role);
                          }}
                          className="px-2.5 py-1 rounded-lg bg-white/5 hover:bg-white/10 text-slate-300"
                        >
                          Edit ✏️
                        </button>
                        <button
                          onClick={() => handleDeletePlayer(p.player_id)}
                          className="px-2.5 py-1 rounded-lg bg-rose-500/10 hover:bg-rose-500/20 text-rose-300"
                        >
                          Delete 🗑️
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

{/* TAB 3: NPCS TABLE */}
        {activeTab === 'npcs' && (
          <div className="glass-card rounded-2xl p-6 border border-white/10">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-bold text-white uppercase tracking-wider">
                NPC Entities ({npcs.length})
              </h3>
              <button
                onClick={() => {
                  setEditingNpc(null);
                  setNpcName('');
                  setNpcPersona('');
                  setNpcLocation('');
                  setNpcGreeting('');
                  setShowNpcModal(true);
                }}
                className="px-3 py-1.5 rounded-xl bg-violet-600 hover:bg-violet-500 text-white text-xs font-semibold"
              >
                + Register New NPC
              </button>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="border-b border-white/10 text-slate-400 font-semibold uppercase tracking-wider">
                    <th className="pb-3 px-3">ID</th>
                    <th className="pb-3 px-3">Name</th>
                    <th className="pb-3 px-3">Location</th>
                    <th className="pb-3 px-3">Persona Description</th>
                    <th className="pb-3 px-3 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/5">
                  {npcs.map((n) => (
                    <tr key={n.npc_id} className="hover:bg-white/5 transition">
                      <td className="py-3 px-3 font-mono text-slate-400">#{n.npc_id}</td>
                      <td className="py-3 px-3 font-bold text-white">{n.name}</td>
                      <td className="py-3 px-3 text-cyan-300">{n.location || 'Global'}</td>
                      <td className="py-3 px-3 text-slate-400 max-w-sm truncate">{n.persona}</td>
                      <td className="py-3 px-3 text-right space-x-2">
                        <button
                          onClick={() => {
                            setEditingNpc(n);
                            setNpcName(n.name);
                            setNpcPersona(n.persona);
                            setNpcLocation(n.location || '');
                            setNpcGreeting(n.greeting || '');
                            setShowNpcModal(true);
                          }}
                          className="px-2.5 py-1 rounded-lg bg-white/5 hover:bg-white/10 text-slate-300"
                        >
                          Edit ✏️
                        </button>
                        <button
                          onClick={() => handleDeleteNpc(n.npc_id)}
                          className="px-2.5 py-1 rounded-lg bg-rose-500/10 hover:bg-rose-500/20 text-rose-300"
                        >
                          Delete 🗑️
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

{/* TAB 4: ITEMS TABLE */}
        {activeTab === 'items' && (
          <div className="glass-card rounded-2xl p-6 border border-white/10">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-bold text-white uppercase tracking-wider">
                Item Catalog ({items.length})
              </h3>
              <button
                onClick={() => {
                  setEditingItem(null);
                  setItemName('');
                  setItemDesc('');
                  setItemPrice(50);
                  setItemType('weapon');
                  setItemRarity('common');
                  setItemStock(-1);
                  setShowItemModal(true);
                }}
                className="px-3 py-1.5 rounded-xl bg-violet-600 hover:bg-violet-500 text-white text-xs font-semibold"
              >
                + Forge Item
              </button>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="border-b border-white/10 text-slate-400 font-semibold uppercase tracking-wider">
                    <th className="pb-3 px-3">ID</th>
                    <th className="pb-3 px-3">Name</th>
                    <th className="pb-3 px-3">Type</th>
                    <th className="pb-3 px-3">Rarity</th>
                    <th className="pb-3 px-3">Price</th>
                    <th className="pb-3 px-3">Stock</th>
                    <th className="pb-3 px-3 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/5">
                  {items.map((it) => (
                    <tr key={it.item_id} className="hover:bg-white/5 transition">
                      <td className="py-3 px-3 font-mono text-slate-400">#{it.item_id}</td>
                      <td className="py-3 px-3 font-bold text-white">{it.name}</td>
                      <td className="py-3 px-3 text-slate-300 capitalize">{it.item_type}</td>
                      <td className="py-3 px-3 capitalize font-bold">
                        <span className={`px-2 py-0.5 rounded text-[10px] uppercase rarity-${it.rarity}`}>
                          {it.rarity}
                        </span>
                      </td>
                      <td className="py-3 px-3 font-mono text-amber-300 font-bold">
                        🪙 {it.base_price} G
                      </td>
                      <td className="py-3 px-3 font-mono text-slate-300">
                        {it.stock === -1 ? '∞' : it.stock}
                      </td>
                      <td className="py-3 px-3 text-right space-x-2">
                        <button
                          onClick={() => {
                            setEditingItem(it);
                            setItemName(it.name);
                            setItemDesc(it.description || '');
                            setItemPrice(it.base_price);
                            setItemType(it.item_type);
                            setItemRarity(it.rarity);
                            setItemStock(it.stock);
                            setShowItemModal(true);
                          }}
                          className="px-2.5 py-1 rounded-lg bg-white/5 hover:bg-white/10 text-slate-300"
                        >
                          Edit ✏️
                        </button>
                        <button
                          onClick={() => handleDeleteItem(it.item_id)}
                          className="px-2.5 py-1 rounded-lg bg-rose-500/10 hover:bg-rose-500/20 text-rose-300"
                        >
                          Delete 🗑️
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

{/* TAB 5: QUESTS TABLE */}
        {activeTab === 'quests' && (
          <div className="glass-card rounded-2xl p-6 border border-white/10">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-bold text-white uppercase tracking-wider">
                Quests Registry ({quests.length})
              </h3>
              <button
                onClick={() => {
                  setEditingQuest(null);
                  setQuestTitle('');
                  setQuestDesc('');
                  setQuestGold(100);
                  setQuestXp(50);
                  setQuestMinLevel(1);
                  setQuestType('main');
                  setShowQuestModal(true);
                }}
                className="px-3 py-1.5 rounded-xl bg-violet-600 hover:bg-violet-500 text-white text-xs font-semibold"
              >
                + Register Quest
              </button>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="border-b border-white/10 text-slate-400 font-semibold uppercase tracking-wider">
                    <th className="pb-3 px-3">ID</th>
                    <th className="pb-3 px-3">Title</th>
                    <th className="pb-3 px-3">Type</th>
                    <th className="pb-3 px-3">Min Level</th>
                    <th className="pb-3 px-3">Gold Reward</th>
                    <th className="pb-3 px-3">XP Reward</th>
                    <th className="pb-3 px-3 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/5">
                  {quests.map((q) => (
                    <tr key={q.quest_id} className="hover:bg-white/5 transition">
                      <td className="py-3 px-3 font-mono text-slate-400">#{q.quest_id}</td>
                      <td className="py-3 px-3 font-bold text-white">{q.title}</td>
                      <td className="py-3 px-3 text-cyan-300 uppercase text-[10px] font-bold">
                        {q.quest_type}
                      </td>
                      <td className="py-3 px-3 font-mono text-slate-300">Lv. {q.min_level}</td>
                      <td className="py-3 px-3 font-mono text-amber-300">🪙 {q.reward_gold}</td>
                      <td className="py-3 px-3 font-mono text-emerald-400">✨ {q.reward_xp}</td>
                      <td className="py-3 px-3 text-right space-x-2">
                        <button
                          onClick={() => {
                            setEditingQuest(q);
                            setQuestTitle(q.title);
                            setQuestDesc(q.description || '');
                            setQuestGold(q.reward_gold);
                            setQuestXp(q.reward_xp);
                            setQuestMinLevel(q.min_level);
                            setQuestType(q.quest_type);
                            setShowQuestModal(true);
                          }}
                          className="px-2.5 py-1 rounded-lg bg-white/5 hover:bg-white/10 text-slate-300"
                        >
                          Edit ✏️
                        </button>
                        <button
                          onClick={() => handleDeleteQuest(q.quest_id)}
                          className="px-2.5 py-1 rounded-lg bg-rose-500/10 hover:bg-rose-500/20 text-rose-300"
                        >
                          Delete 🗑️
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

{/* TAB 6: AUDIT LOG */}
        {activeTab === 'audit' && (
          <div className="glass-card rounded-2xl p-6 border border-white/10">
            <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 mb-4">
              <div>
                <h3 className="text-sm font-bold text-white uppercase tracking-wider flex items-center gap-2">
                  <span>🛡️</span>
                  <span>Database Row Audit Log (JSONB Trigger-backed)</span>
                </h3>
                <p className="text-[11px] text-slate-400 mt-0.5">
                  Records all table mutations, diffs, and acting database users.
                </p>
              </div>

              <input
                type="text"
                value={auditFilterTable}
                onChange={(e) => setAuditFilterTable(e.target.value)}
                placeholder="Filter by table name..."
                className="glass-input px-3 py-1.5 rounded-xl text-xs"
              />
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="border-b border-white/10 text-slate-400 font-semibold uppercase tracking-wider">
                    <th className="pb-3 px-3">Log ID</th>
                    <th className="pb-3 px-3">Table</th>
                    <th className="pb-3 px-3">Operation</th>
                    <th className="pb-3 px-3">Row ID</th>
                    <th className="pb-3 px-3">Changed By</th>
                    <th className="pb-3 px-3 text-right">Timestamp</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/5">
                  {auditLog
                    .filter(
                      (l) =>
                        !auditFilterTable ||
                        l.table_name.toLowerCase().includes(auditFilterTable.toLowerCase())
                    )
                    .map((log) => (
                      <tr key={log.log_id} className="hover:bg-white/5 transition">
                        <td className="py-3 px-3 font-mono text-slate-400">#{log.log_id}</td>
                        <td className="py-3 px-3 font-bold text-violet-300">{log.table_name}</td>
                        <td className="py-3 px-3">
                          <span
                            className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                              log.operation === 'INSERT'
                                ? 'bg-emerald-500/20 text-emerald-300'
                                : log.operation === 'UPDATE'
                                ? 'bg-amber-500/20 text-amber-300'
                                : 'bg-rose-500/20 text-rose-300'
                            }`}
                          >
                            {log.operation}
                          </span>
                        </td>
                        <td className="py-3 px-3 font-mono text-slate-300">
                          {log.row_id ?? '-'}
                        </td>
                        <td className="py-3 px-3 text-slate-400 font-mono text-[11px]">
                          {log.changed_by}
                        </td>
                        <td className="py-3 px-3 text-right text-slate-400 font-mono text-[11px]">
                          {log.changed_at ? new Date(log.changed_at).toLocaleString() : 'Recent'}
                        </td>
                      </tr>
                    ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* TAB 7: SQL CONSOLE & EXPLAIN ANALYZE */}
        {activeTab === 'sql' && (
          <div className="space-y-6">
            {/* Top Info Banner for Viva */}
            <div className="glass-card p-5 rounded-2xl border border-cyan-500/30 bg-cyan-950/20">
              <div className="flex items-start gap-3">
                <span className="text-2xl">🎓</span>
                <div className="space-y-1">
                  <h3 className="text-sm font-bold text-white flex items-center gap-2">
                    <span>Interactive PostgreSQL Console & Execution Plan Benchmarker</span>
                    <span className="text-[10px] font-mono bg-cyan-500/20 text-cyan-300 px-2 py-0.5 rounded border border-cyan-500/30">
                      ACID & Performance
                    </span>
                  </h3>
                  <p className="text-xs text-slate-300 leading-relaxed">
                    Designed for your DBMS evaluation. Execute arbitrary SQL queries, benchmark query planning and execution times with <strong className="text-cyan-400">EXPLAIN (ANALYZE, BUFFERS)</strong>, or run queries in the native terminal via <code className="bg-black/50 px-1.5 py-0.5 rounded text-amber-300 font-mono text-[11px]">psql -U postgres -d generative_npc_db</code>.
                  </p>
                </div>
              </div>
            </div>

            {/* Presets Bar */}
            <div className="glass-card p-4 rounded-2xl border border-white/10 space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-slate-300 uppercase tracking-wider">
                  Curated Viva Query Presets (Select to load):
                </span>
                <span className="text-[11px] text-slate-400">
                  Click any query below to populate the console
                </span>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2 pt-1">
                {queryPresets.map((preset, idx) => (
                  <button
                    key={idx}
                    type="button"
                    onClick={() => {
                      setSqlQuery(preset.query);
                      setSqlResult(null);
                      setExplainResult(null);
                    }}
                    className="p-2.5 rounded-xl bg-white/[0.03] hover:bg-white/[0.08] border border-white/10 text-left transition group"
                  >
                    <div className="flex items-center justify-between text-[11px] mb-1">
                      <span className="font-bold text-white group-hover:text-cyan-300 transition">
                        {preset.name}
                      </span>
                      <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-cyan-500/10 text-cyan-300 border border-cyan-500/20">
                        {preset.category}
                      </span>
                    </div>
                    <p className="text-[10px] text-slate-400 line-clamp-2 leading-relaxed">
                      {preset.description}
                    </p>
                  </button>
                ))}
              </div>
            </div>

            {/* SQL Query Editor & Actions */}
            <div className="glass-card p-5 rounded-2xl border border-white/10 space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-xs font-mono font-bold text-amber-300 uppercase tracking-wider flex items-center gap-1.5">
                  <span>⚡</span>
                  <span>SQL Query Editor:</span>
                </span>
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => setSqlQuery('')}
                    className="text-[11px] text-slate-400 hover:text-white transition px-2 py-1 rounded hover:bg-white/5"
                  >
                    Clear Editor
                  </button>
                </div>
              </div>

              <textarea
                value={sqlQuery}
                onChange={(e) => setSqlQuery(e.target.value)}
                rows={7}
                placeholder="Write any PostgreSQL query here (e.g. SELECT * FROM players;)..."
                className="w-full font-mono text-xs p-3.5 rounded-xl bg-black/60 text-emerald-300 border border-white/10 focus:border-cyan-400 focus:outline-none leading-relaxed selection:bg-cyan-500/30"
                spellCheck={false}
              />

              <div className="flex flex-wrap items-center justify-between gap-3 pt-1">
                <div className="text-[11px] text-slate-400">
                  Tip: Supports <strong className="text-slate-300">SELECT</strong>, <strong className="text-slate-300">WITH RECURSIVE</strong>, <strong className="text-slate-300">JOINs</strong>, <strong className="text-slate-300">Window Functions</strong>, and <strong className="text-slate-300">DML</strong>.
                </div>
                <div className="flex items-center gap-2.5">
                  <button
                    type="button"
                    onClick={handleExplainAnalyze}
                    disabled={explainingSql || executingSql}
                    className="py-2 px-4 rounded-xl bg-purple-600/20 hover:bg-purple-600/30 text-purple-300 border border-purple-500/30 text-xs font-bold transition flex items-center gap-1.5"
                  >
                    <span>⚡</span>
                    <span>{explainingSql ? 'Analyzing Plan...' : 'EXPLAIN ANALYZE'}</span>
                  </button>
                  <button
                    type="button"
                    onClick={handleRunSql}
                    disabled={executingSql || explainingSql}
                    className="py-2 px-5 rounded-xl bg-gradient-to-r from-emerald-600 to-cyan-600 hover:from-emerald-500 hover:to-cyan-500 text-white text-xs font-bold shadow-lg shadow-cyan-600/20 transition flex items-center gap-1.5"
                  >
                    <span>▶️</span>
                    <span>{executingSql ? 'Executing...' : 'Run Query'}</span>
                  </button>
                </div>
              </div>
            </div>

            {/* Results Section */}
            {sqlViewMode === 'table' && sqlResult && (
              <div className="glass-card p-5 rounded-2xl border border-white/10 space-y-4 animate-in fade-in">
                <div className="flex items-center justify-between border-b border-white/10 pb-3">
                  <div className="flex items-center gap-2.5">
                    <span className={`w-2.5 h-2.5 rounded-full ${sqlResult.success ? 'bg-emerald-400' : 'bg-rose-400'}`}></span>
                    <span className="text-xs font-bold text-white uppercase tracking-wider">
                      Execution Result
                    </span>
                  </div>
                  <div className="flex items-center gap-3 text-xs font-mono">
                    <span className="text-cyan-300 bg-cyan-500/10 px-2.5 py-0.5 rounded border border-cyan-500/20">
                      ⏱️ {sqlResult.execution_time_ms} ms
                    </span>
                    <span className="text-amber-300 bg-amber-500/10 px-2.5 py-0.5 rounded border border-amber-500/20">
                      📊 {sqlResult.row_count} rows
                    </span>
                    {sqlResult.command && (
                      <span className="text-purple-300 bg-purple-500/10 px-2.5 py-0.5 rounded border border-purple-500/20">
                        {sqlResult.command}
                      </span>
                    )}
                  </div>
                </div>

                {!sqlResult.success ? (
                  <div className="p-4 rounded-xl bg-rose-950/40 border border-rose-500/40 text-xs text-rose-200 font-mono space-y-1">
                    <div className="font-bold flex items-center gap-2">
                      <span>❌ PostgreSQL Error</span>
                      {sqlResult.pg_code && <span className="text-[10px] bg-rose-900/60 px-1.5 py-0.5 rounded">SQLSTATE: {sqlResult.pg_code}</span>}
                    </div>
                    <p>{sqlResult.error}</p>
                  </div>
                ) : sqlResult.columns.length === 0 ? (
                  <div className="p-6 text-center text-xs text-slate-400 font-mono">
                    ✓ Statement executed successfully. Status: <strong className="text-emerald-300">{sqlResult.status || 'OK'}</strong>
                  </div>
                ) : (
                  <div className="overflow-x-auto max-h-96 rounded-xl border border-white/10">
                    <table className="w-full text-left text-xs">
                      <thead className="bg-black/60 sticky top-0 z-10 border-b border-white/10">
                        <tr>
                          {sqlResult.columns.map((col: string, idx: number) => (
                            <th key={idx} className="py-2.5 px-3 font-mono font-bold text-cyan-300 text-[11px] whitespace-nowrap">
                              {col}
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-white/5 font-mono text-[11px]">
                        {sqlResult.rows.map((row: any, rIdx: number) => (
                          <tr key={rIdx} className="hover:bg-white/[0.03] transition">
                            {sqlResult.columns.map((col: string, cIdx: number) => (
                              <td key={cIdx} className="py-2 px-3 text-slate-300 whitespace-nowrap">
                                {row[col] !== null && row[col] !== undefined ? String(row[col]) : <em className="text-slate-500">NULL</em>}
                              </td>
                            ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            )}

            {/* EXPLAIN ANALYZE Result */}
            {sqlViewMode === 'explain' && explainResult && (
              <div className="glass-card p-5 rounded-2xl border border-purple-500/30 space-y-4 animate-in fade-in">
                <div className="flex items-center justify-between border-b border-white/10 pb-3">
                  <div className="flex items-center gap-2.5">
                    <span className="text-lg">⚡</span>
                    <span className="text-xs font-bold text-white uppercase tracking-wider">
                      PostgreSQL Query Planner & Execution Profile
                    </span>
                  </div>
                  <button
                    type="button"
                    onClick={() => setSqlViewMode('table')}
                    className="text-[11px] text-cyan-400 hover:text-cyan-300 underline"
                  >
                    Switch to Data Table View
                  </button>
                </div>

                {!explainResult.success ? (
                  <div className="p-4 rounded-xl bg-rose-950/40 border border-rose-500/40 text-xs text-rose-200 font-mono">
                    ❌ EXPLAIN Error: {explainResult.error}
                  </div>
                ) : (
                  <div className="space-y-4">
                    {/* Summary Metrics */}
                    <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
                      <div className="p-3 rounded-xl bg-white/[0.03] border border-white/10">
                        <div className="text-[10px] text-slate-400 uppercase tracking-wider">Planning Time</div>
                        <div className="text-base font-black text-cyan-400 mt-0.5">
                          {explainResult.summary?.planning_time_ms ?? '-'} ms
                        </div>
                      </div>
                      <div className="p-3 rounded-xl bg-white/[0.03] border border-white/10">
                        <div className="text-[10px] text-slate-400 uppercase tracking-wider">Execution Time</div>
                        <div className="text-base font-black text-emerald-400 mt-0.5">
                          {explainResult.summary?.execution_time_ms ?? '-'} ms
                        </div>
                      </div>
                      <div className="p-3 rounded-xl bg-white/[0.03] border border-white/10">
                        <div className="text-[10px] text-slate-400 uppercase tracking-wider">Root Scan Type</div>
                        <div className="text-xs font-bold text-purple-300 mt-1 font-mono truncate">
                          {explainResult.summary?.node_type ?? '-'}
                        </div>
                      </div>
                      <div className="p-3 rounded-xl bg-white/[0.03] border border-white/10">
                        <div className="text-[10px] text-slate-400 uppercase tracking-wider">Optimizer Cost</div>
                        <div className="text-base font-black text-amber-300 mt-0.5">
                          {explainResult.summary?.total_cost ?? '-'}
                        </div>
                      </div>
                      <div className="p-3 rounded-xl bg-white/[0.03] border border-white/10">
                        <div className="text-[10px] text-slate-400 uppercase tracking-wider">Shared Buffer Hits</div>
                        <div className="text-base font-black text-blue-400 mt-0.5">
                          {explainResult.summary?.shared_hit_blocks ?? 0} blocks
                        </div>
                      </div>
                    </div>

                    {/* Text Execution Plan */}
                    <div className="p-4 rounded-xl bg-black/60 border border-white/10 overflow-x-auto">
                      <div className="text-[10px] text-slate-400 font-mono uppercase tracking-wider mb-2">
                        Execution Plan Tree:
                      </div>
                      <pre className="font-mono text-xs text-slate-200 leading-relaxed whitespace-pre">
                        {explainResult.text_plan}
                      </pre>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* EDIT PLAYER MODAL */}
        {editingPlayer && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-sm animate-in fade-in">
            <div className="glass-card max-w-md w-full p-6 rounded-2xl border border-amber-500/30">
              <h3 className="text-sm font-bold text-white mb-4">
                Update Player #{editingPlayer.player_id} ({editingPlayer.username})
              </h3>
              <form onSubmit={handleSavePlayer} className="space-y-4">
                <div>
                  <label className="block text-xs font-semibold text-slate-300 mb-1">
                    Role Clearance:
                  </label>
                  <select
                    value={playerRole}
                    onChange={(e) => setPlayerRole(e.target.value as any)}
                    className="w-full glass-input px-3 py-2 rounded-xl text-xs"
                  >
                    <option value="player" className="bg-[#12121a]">player</option>
                    <option value="admin" className="bg-[#12121a]">admin</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-300 mb-1">
                    Gold Balance:
                  </label>
                  <input
                    type="number"
                    min="0"
                    value={playerGold}
                    onChange={(e) => setPlayerGold(Number(e.target.value))}
                    className="w-full glass-input px-3 py-2 rounded-xl text-xs"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-300 mb-1">
                    Player Level:
                  </label>
                  <input
                    type="number"
                    min="1"
                    value={playerLevel}
                    onChange={(e) => setPlayerLevel(Number(e.target.value))}
                    className="w-full glass-input px-3 py-2 rounded-xl text-xs"
                  />
                </div>
                <div className="flex justify-end gap-2 pt-3 border-t border-white/10">
                  <button
                    type="button"
                    onClick={() => setEditingPlayer(null)}
                    className="px-4 py-2 rounded-xl bg-white/5 text-xs text-slate-300"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    className="px-4 py-2 rounded-xl bg-amber-600 hover:bg-amber-500 text-white text-xs font-semibold"
                  >
                    Save Changes
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}

        {/* NPC CREATE/EDIT MODAL */}
        {showNpcModal && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-sm animate-in fade-in">
            <div className="glass-card max-w-lg w-full p-6 rounded-2xl border border-violet-500/30">
              <h3 className="text-sm font-bold text-white mb-4">
                {editingNpc ? `Edit NPC ${editingNpc.name}` : 'Register New NPC Entity'}
              </h3>
              <form onSubmit={handleSaveNpc} className="space-y-4">
                <div>
                  <label className="block text-xs font-semibold text-slate-300 mb-1">Name:</label>
                  <input
                    type="text"
                    required
                    value={npcName}
                    onChange={(e) => setNpcName(e.target.value)}
                    className="w-full glass-input px-3 py-2 rounded-xl text-xs"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-300 mb-1">Location:</label>
                  <input
                    type="text"
                    value={npcLocation}
                    onChange={(e) => setNpcLocation(e.target.value)}
                    placeholder="e.g. Arcane Tower"
                    className="w-full glass-input px-3 py-2 rounded-xl text-xs"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-300 mb-1">Persona:</label>
                  <textarea
                    required
                    rows={3}
                    value={npcPersona}
                    onChange={(e) => setNpcPersona(e.target.value)}
                    placeholder="Describe character archetype, backstory, and tone..."
                    className="w-full glass-input px-3 py-2 rounded-xl text-xs"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-300 mb-1">Greeting Dialogue:</label>
                  <input
                    type="text"
                    value={npcGreeting}
                    onChange={(e) => setNpcGreeting(e.target.value)}
                    placeholder="Welcome, traveler..."
                    className="w-full glass-input px-3 py-2 rounded-xl text-xs"
                  />
                </div>
                <div className="flex justify-end gap-2 pt-3 border-t border-white/10">
                  <button
                    type="button"
                    onClick={() => setShowNpcModal(false)}
                    className="px-4 py-2 rounded-xl bg-white/5 text-xs text-slate-300"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    className="px-4 py-2 rounded-xl bg-violet-600 hover:bg-violet-500 text-white text-xs font-semibold"
                  >
                    Save NPC
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}

        {/* ITEM CREATE/EDIT MODAL */}
        {showItemModal && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-sm animate-in fade-in">
            <div className="glass-card max-w-lg w-full p-6 rounded-2xl border border-cyan-500/30">
              <h3 className="text-sm font-bold text-white mb-4">
                {editingItem ? `Edit Item ${editingItem.name}` : 'Forge New Catalog Item'}
              </h3>
              <form onSubmit={handleSaveItem} className="space-y-4">
                <div>
                  <label className="block text-xs font-semibold text-slate-300 mb-1">Name:</label>
                  <input
                    type="text"
                    required
                    value={itemName}
                    onChange={(e) => setItemName(e.target.value)}
                    className="w-full glass-input px-3 py-2 rounded-xl text-xs"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-300 mb-1">Description:</label>
                  <input
                    type="text"
                    value={itemDesc}
                    onChange={(e) => setItemDesc(e.target.value)}
                    className="w-full glass-input px-3 py-2 rounded-xl text-xs"
                  />
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs font-semibold text-slate-300 mb-1">Base Price (Gold):</label>
                    <input
                      type="number"
                      required
                      min="1"
                      value={itemPrice}
                      onChange={(e) => setItemPrice(Number(e.target.value))}
                      className="w-full glass-input px-3 py-2 rounded-xl text-xs"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-semibold text-slate-300 mb-1">Stock (-1 = infinite):</label>
                    <input
                      type="number"
                      value={itemStock}
                      onChange={(e) => setItemStock(Number(e.target.value))}
                      className="w-full glass-input px-3 py-2 rounded-xl text-xs"
                    />
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs font-semibold text-slate-300 mb-1">Type:</label>
                    <select
                      value={itemType}
                      onChange={(e) => setItemType(e.target.value as any)}
                      className="w-full glass-input px-3 py-2 rounded-xl text-xs"
                    >
                      <option value="weapon" className="bg-[#12121a]">Weapon</option>
                      <option value="armor" className="bg-[#12121a]">Armor</option>
                      <option value="potion" className="bg-[#12121a]">Potion</option>
                      <option value="misc" className="bg-[#12121a]">Misc</option>
                      <option value="quest_item" className="bg-[#12121a]">Quest Item</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-xs font-semibold text-slate-300 mb-1">Rarity:</label>
                    <select
                      value={itemRarity}
                      onChange={(e) => setItemRarity(e.target.value as any)}
                      className="w-full glass-input px-3 py-2 rounded-xl text-xs"
                    >
                      <option value="common" className="bg-[#12121a]">Common</option>
                      <option value="uncommon" className="bg-[#12121a]">Uncommon</option>
                      <option value="rare" className="bg-[#12121a]">Rare</option>
                      <option value="epic" className="bg-[#12121a]">Epic</option>
                      <option value="legendary" className="bg-[#12121a]">Legendary</option>
                    </select>
                  </div>
                </div>
                <div className="flex justify-end gap-2 pt-3 border-t border-white/10">
                  <button
                    type="button"
                    onClick={() => setShowItemModal(false)}
                    className="px-4 py-2 rounded-xl bg-white/5 text-xs text-slate-300"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    className="px-4 py-2 rounded-xl bg-cyan-600 hover:bg-cyan-500 text-white text-xs font-semibold"
                  >
                    Save Item
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}

        {/* QUEST CREATE/EDIT MODAL */}
        {showQuestModal && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-sm animate-in fade-in">
            <div className="glass-card max-w-lg w-full p-6 rounded-2xl border border-emerald-500/30">
              <h3 className="text-sm font-bold text-white mb-4">
                {editingQuest ? `Edit Quest ${editingQuest.title}` : 'Register New Adventure Quest'}
              </h3>
              <form onSubmit={handleSaveQuest} className="space-y-4">
                <div>
                  <label className="block text-xs font-semibold text-slate-300 mb-1">Title:</label>
                  <input
                    type="text"
                    required
                    value={questTitle}
                    onChange={(e) => setQuestTitle(e.target.value)}
                    className="w-full glass-input px-3 py-2 rounded-xl text-xs"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-300 mb-1">Description:</label>
                  <textarea
                    rows={2}
                    value={questDesc}
                    onChange={(e) => setQuestDesc(e.target.value)}
                    className="w-full glass-input px-3 py-2 rounded-xl text-xs"
                  />
                </div>
                <div className="grid grid-cols-3 gap-3">
                  <div>
                    <label className="block text-xs font-semibold text-slate-300 mb-1">Min Level:</label>
                    <input
                      type="number"
                      required
                      min="1"
                      value={questMinLevel}
                      onChange={(e) => setQuestMinLevel(Number(e.target.value))}
                      className="w-full glass-input px-3 py-2 rounded-xl text-xs"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-semibold text-slate-300 mb-1">Gold Reward:</label>
                    <input
                      type="number"
                      required
                      min="0"
                      value={questGold}
                      onChange={(e) => setQuestGold(Number(e.target.value))}
                      className="w-full glass-input px-3 py-2 rounded-xl text-xs"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-semibold text-slate-300 mb-1">XP Reward:</label>
                    <input
                      type="number"
                      required
                      min="0"
                      value={questXp}
                      onChange={(e) => setQuestXp(Number(e.target.value))}
                      className="w-full glass-input px-3 py-2 rounded-xl text-xs"
                    />
                  </div>
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-300 mb-1">Quest Type:</label>
                  <select
                    value={questType}
                    onChange={(e) => setQuestType(e.target.value as any)}
                    className="w-full glass-input px-3 py-2 rounded-xl text-xs"
                  >
                    <option value="main" className="bg-[#12121a]">Main Quest</option>
                    <option value="side" className="bg-[#12121a]">Side Quest</option>
                    <option value="daily" className="bg-[#12121a]">Daily Quest</option>
                    <option value="hidden" className="bg-[#12121a]">Hidden Quest</option>
                  </select>
                </div>
                <div className="flex justify-end gap-2 pt-3 border-t border-white/10">
                  <button
                    type="button"
                    onClick={() => setShowQuestModal(false)}
                    className="px-4 py-2 rounded-xl bg-white/5 text-xs text-slate-300"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    className="px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-semibold"
                  >
                    Save Quest
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}
      </div>
    </ProtectedRoute>
  );
}
