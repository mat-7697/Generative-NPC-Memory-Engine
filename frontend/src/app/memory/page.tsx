'use client';

import React, { useState, useEffect, useCallback } from 'react';
import ProtectedRoute from '@/components/ProtectedRoute';
import { useAuth } from '@/lib/auth';
import { useToast } from '@/lib/toast';
import {
  api,
  NPCResponse,
  MemoryResponse,
  MemoryStats,
  CreateMemoryRequest,
  UpdateMemoryRequest,
} from '@/lib/api';

export default function MemoryPage() {
  const { user } = useAuth();
  const { success, error: toastError, info } = useToast();

  const [npcs, setNpcs] = useState<NPCResponse[]>([]);
  const [selectedNpcId, setSelectedNpcId] = useState<number | ''>('');
  const [searchQuery, setSearchQuery] = useState('');
  const [topK, setTopK] = useState(6);
  const [memories, setMemories] = useState<MemoryResponse[]>([]);
  const [stats, setStats] = useState<MemoryStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [searching, setSearching] = useState(false);
  const [viewMode, setViewMode] = useState<'cards' | 'map'>('cards');
  const [hoveredPoint, setHoveredPoint] = useState<MemoryResponse | null>(null);

  // Create Modal State
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [newText, setNewText] = useState('');
  const [newNpcId, setNewNpcId] = useState<number | ''>('');
  const [newRole, setNewRole] = useState('dialogue');
  const [newImportance, setNewImportance] = useState(5.0);
  const [submittingCreate, setSubmittingCreate] = useState(false);

  // Edit Modal State
  const [editingMemory, setEditingMemory] = useState<MemoryResponse | null>(null);
  const [editText, setEditText] = useState('');
  const [editImportance, setEditImportance] = useState(5.0);
  const [submittingEdit, setSubmittingEdit] = useState(false);

  // Delete Player-NPC Modal State
  const [confirmClearNpc, setConfirmClearNpc] = useState<NPCResponse | null>(null);

  const loadInitialData = useCallback(async () => {
    try {
      setLoading(true);
      const [npcList, statsRes] = await Promise.allSettled([
        api.npcs.getAll(),
        api.memory.getStats(),
      ]);

      if (npcList.status === 'fulfilled') {
        const list = npcList.value || [];
        setNpcs(list);
        if (list.length > 0) {
          setSelectedNpcId(list[0].npc_id);
          setNewNpcId(list[0].npc_id);
        }
      }
      if (statsRes.status === 'fulfilled') {
        setStats(statsRes.value);
      }
    } catch (err: any) {
      toastError(err.message || 'Failed to initialize memory matrix.');
    } finally {
      setLoading(false);
    }
  }, [toastError]);

  useEffect(() => {
    loadInitialData();
  }, [loadInitialData]);

  // Execute Vector Search
  const handleSearch = useCallback(async () => {
    setSearching(true);
    try {
      const results = await api.memory.search(
        selectedNpcId !== '' ? Number(selectedNpcId) : undefined,
        searchQuery.trim() || undefined,
        topK
      );
      setMemories(results || []);
    } catch (err: any) {
      toastError(err.message || 'Vector search encountered an issue.');
    } finally {
      setSearching(false);
    }
  }, [selectedNpcId, searchQuery, topK, toastError]);

  useEffect(() => {
    if (!loading) {
      handleSearch();
    }
  }, [loading, selectedNpcId, handleSearch]);

  // Create Memory
  const handleCreateMemory = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newText.trim() || newNpcId === '') return;

    setSubmittingCreate(true);
    try {
      const payload: CreateMemoryRequest = {
        npc_id: Number(newNpcId),
        text: newText.trim(),
        role: newRole,
        importance: newImportance,
      };
      await api.memory.create(payload);
      success('Episodic vector memory synthesized & indexed in Qdrant!');
      setShowCreateModal(false);
      setNewText('');
      await handleSearch();
      const updatedStats = await api.memory.getStats();
      setStats(updatedStats);
    } catch (err: any) {
      toastError(err.message || 'Failed to inject memory.');
    } finally {
      setSubmittingCreate(false);
    }
  };

  // Update Memory
  const handleUpdateMemory = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingMemory) return;

    setSubmittingEdit(true);
    try {
      const payload: UpdateMemoryRequest = {
        text: editText.trim(),
        importance: editImportance,
      };
      await api.memory.update(editingMemory.id, payload);
      success('Vector memory payload updated successfully.');
      setEditingMemory(null);
      await handleSearch();
    } catch (err: any) {
      toastError(err.message || 'Failed to update memory.');
    } finally {
      setSubmittingEdit(false);
    }
  };

  // Delete Single Memory
  const handleDeleteMemory = async (id: string | number) => {
    if (!confirm('Permanently purge this vector point from Qdrant index?')) return;

    try {
      await api.memory.delete(id);
      success('Memory point purged from vector store.');
      setMemories((prev) => prev.filter((m) => m.id !== id));
      const updatedStats = await api.memory.getStats();
      setStats(updatedStats);
    } catch (err: any) {
      toastError(err.message || 'Failed to delete memory point.');
    }
  };

  // Delete all memories for player-NPC pair
  const handleClearPlayerNPCMemories = async () => {
    if (!confirmClearNpc || !user?.player_id) return;

    try {
      await api.memory.deletePlayerNPC(user.player_id, confirmClearNpc.npc_id);
      success(`All episodic records between you and ${confirmClearNpc.name} wiped.`);
      setConfirmClearNpc(null);
      await handleSearch();
      const updatedStats = await api.memory.getStats();
      setStats(updatedStats);
    } catch (err: any) {
      toastError(err.message || 'Failed to wipe shared memories.');
    }
  };

  const getImportanceBadge = (importance: number = 5) => {
    if (importance >= 8) return 'bg-rose-500/20 text-rose-300 border-rose-500/40';
    if (importance >= 5) return 'bg-amber-500/20 text-amber-300 border-amber-500/40';
    return 'bg-blue-500/20 text-blue-300 border-blue-500/40';
  };

  return (
    <ProtectedRoute>
      <div className="space-y-6 pb-12">
        {/* Header */}
        <div className="glass-card rounded-2xl p-6 border border-cyan-500/20 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <span className="text-xs font-mono uppercase tracking-widest text-cyan-400 bg-cyan-500/10 px-2 py-0.5 rounded border border-cyan-500/30">
                Qdrant Vector Database
              </span>
              <span className="text-xs text-slate-400">Cosine Distance 384-Dim</span>
            </div>
            <h1 className="text-2xl font-extrabold text-white tracking-tight">
              Memory Core & Vector Search
            </h1>
            <p className="text-xs text-slate-400 mt-1">
              Manage episodic NPC reflections, inspect semantic relevance scores, and tune generative memory weighting.
            </p>
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={() => setShowCreateModal(true)}
              className="px-4 py-2 rounded-xl bg-gradient-to-r from-cyan-600 to-violet-600 hover:from-cyan-500 hover:to-violet-500 text-white font-semibold text-xs shadow-lg shadow-cyan-600/30 transition flex items-center gap-1.5"
            >
              <span>✨</span>
              <span>Inject Memory Vector</span>
            </button>
          </div>
        </div>

        {/* Stats Row */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div className="glass-card p-5 rounded-2xl border border-white/10">
            <div className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-1">
              Total Indexed Vectors
            </div>
            <div className="text-2xl font-black text-cyan-300">
              {stats?.total_memories ?? stats?.total_count ?? memories.length}
            </div>
            <div className="text-[11px] text-slate-400 mt-0.5">
              HNSW Graph Indexed in Qdrant
            </div>
          </div>

          <div className="glass-card p-5 rounded-2xl border border-white/10">
            <div className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-1">
              Active Entities
            </div>
            <div className="text-2xl font-black text-violet-300">
              {npcs.length} NPCs
            </div>
            <div className="text-[11px] text-slate-400 mt-0.5">
              Autonomous dialogue synthesis agents
            </div>
          </div>

          <div className="glass-card p-5 rounded-2xl border border-white/10">
            <div className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-1">
              Your Shared Memories
            </div>
            <div className="text-2xl font-black text-amber-300">
              {stats?.player_memories ?? memories.length}
            </div>
            <div className="text-[11px] text-slate-400 mt-0.5">
              Filtered by Player ID #{user?.player_id}
            </div>
          </div>
        </div>

        {/* Search & Filter Toolbar */}
        <div className="glass-card p-5 rounded-2xl border border-white/10 space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-12 gap-3 items-end">
            {/* NPC Filter */}
            <div className="md:col-span-4">
              <label className="block text-xs font-semibold text-slate-300 mb-1">
                Filter by NPC:
              </label>
              <select
                value={selectedNpcId}
                onChange={(e) => setSelectedNpcId(e.target.value ? Number(e.target.value) : '')}
                className="w-full glass-input px-3 py-2 rounded-xl text-xs"
              >
                <option value="" className="bg-[#12121a]">All NPCs (Global)</option>
                {npcs.map((npc) => (
                  <option key={npc.npc_id} value={npc.npc_id} className="bg-[#12121a]">
                    {npc.name} ({npc.location || 'Roaming'})
                  </option>
                ))}
              </select>
            </div>

            {/* Semantic Query Text */}
            <div className="md:col-span-5">
              <label className="block text-xs font-semibold text-slate-300 mb-1">
                Semantic Text Search (Dense Embedding):
              </label>
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
                placeholder="e.g. dragon, iron sword, enchanted forest..."
                className="w-full glass-input px-3 py-2 rounded-xl text-xs"
              />
            </div>

            {/* Top-K Selector */}
            <div className="md:col-span-1">
              <label className="block text-xs font-semibold text-slate-300 mb-1">
                Top-K:
              </label>
              <select
                value={topK}
                onChange={(e) => setTopK(Number(e.target.value))}
                className="w-full glass-input px-2 py-2 rounded-xl text-xs text-center"
              >
                <option value={3} className="bg-[#12121a]">3</option>
                <option value={6} className="bg-[#12121a]">6</option>
                <option value={10} className="bg-[#12121a]">10</option>
                <option value={20} className="bg-[#12121a]">20</option>
              </select>
            </div>

            {/* Action Buttons */}
            <div className="md:col-span-2 flex gap-2">
              <button
                onClick={handleSearch}
                disabled={searching}
                className="w-full py-2 px-3 rounded-xl bg-violet-600 hover:bg-violet-500 text-white font-semibold text-xs shadow-md shadow-violet-600/20 transition flex items-center justify-center gap-1.5"
              >
                {searching ? (
                  <div className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
                ) : (
                  <>
                    <span>Search</span>
                    <span>🔍</span>
                  </>
                )}
              </button>
            </div>
          </div>

          {/* Wipe Memories for Selected NPC Helper */}
          {selectedNpcId !== '' && (
            <div className="pt-2 border-t border-white/5 flex items-center justify-between text-xs">
              <span className="text-slate-400">
                Manage relationship lifecycle for entity:
              </span>
              <button
                onClick={() => {
                  const target = npcs.find((n) => n.npc_id === Number(selectedNpcId));
                  if (target) setConfirmClearNpc(target);
                }}
                className="text-rose-400 hover:text-rose-300 text-[11px] font-semibold underline underline-offset-4"
              >
                Purge All Shared Memories With Selected NPC
              </button>
            </div>
          )}
        </div>

        {/* Memories Display Cards & 2D Vector Map */}
        <div>
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4">
            <div className="flex items-center gap-3">
              <h3 className="text-xs font-bold text-slate-300 uppercase tracking-wider">
                Retrieved Vectors ({memories.length})
              </h3>
              {searchQuery && (
                <span className="text-xs text-violet-300 font-mono">
                  Ranking by Cosine Similarity to &ldquo;{searchQuery}&rdquo;
                </span>
              )}
            </div>

            {/* View Mode Toggle */}
            <div className="flex items-center gap-1 p-1 bg-black/40 rounded-xl border border-white/10 w-fit">
              <button
                type="button"
                onClick={() => setViewMode('cards')}
                className={`px-3 py-1.5 rounded-lg text-xs font-bold transition flex items-center gap-1.5 ${
                  viewMode === 'cards'
                    ? 'bg-violet-600/30 text-violet-300 border border-violet-500/40 shadow-sm'
                    : 'text-slate-400 hover:text-white'
                }`}
              >
                <span>🗂️</span>
                <span>Cards View</span>
              </button>
              <button
                type="button"
                onClick={() => setViewMode('map')}
                className={`px-3 py-1.5 rounded-lg text-xs font-bold transition flex items-center gap-1.5 ${
                  viewMode === 'map'
                    ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 shadow-sm'
                    : 'text-slate-400 hover:text-white'
                }`}
              >
                <span>🌌</span>
                <span>2D Vector Map</span>
              </button>
            </div>
          </div>

          {searching ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {[1, 2, 3, 4, 5, 6].map((n) => (
                <div
                  key={n}
                  className="glass-card p-5 rounded-2xl border border-white/5 animate-pulse h-48"
                ></div>
              ))}
            </div>
          ) : memories.length === 0 ? (
            <div className="glass-card rounded-2xl p-12 text-center border border-white/10">
              <div className="text-4xl mb-3">🧠</div>
              <h3 className="text-base font-bold text-slate-200">No vector memories found</h3>
              <p className="text-xs text-slate-400 mt-1 mb-4">
                No episodic records match the current filters. Inject a new memory or chat with NPCs!
              </p>
              <button
                onClick={() => setShowCreateModal(true)}
                className="px-4 py-2 rounded-xl bg-violet-600 hover:bg-violet-500 text-white text-xs font-semibold"
              >
                Inject Memory Point
              </button>
            </div>
          ) : viewMode === 'map' ? (
            /* 2D SEMANTIC VECTOR MAP VIEW */
            <div className="glass-card p-6 rounded-2xl border border-cyan-500/30 bg-black/60 space-y-4 animate-in fade-in">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-white/10 pb-3">
                <div>
                  <h4 className="text-sm font-bold text-white flex items-center gap-2">
                    <span>🌌</span>
                    <span>384-Dimensional Dense Vector Embedding Projection (2D Map)</span>
                  </h4>
                  <p className="text-[11px] text-slate-400 mt-0.5">
                    Visualizing semantic distance and cosine relevance in Qdrant vector space. Hover or click points to inspect payload.
                  </p>
                </div>
                <div className="flex items-center gap-3 text-[11px] font-mono text-slate-300">
                  <span className="flex items-center gap-1.5">
                    <span className="w-2.5 h-2.5 rounded-full bg-cyan-400 inline-block"></span>
                    <span>High Relevance</span>
                  </span>
                  <span className="flex items-center gap-1.5">
                    <span className="w-2.5 h-2.5 rounded-full bg-purple-400 inline-block"></span>
                    <span>Medium</span>
                  </span>
                  <span className="flex items-center gap-1.5">
                    <span className="w-2.5 h-2.5 rounded-full bg-amber-400 inline-block"></span>
                    <span>Background</span>
                  </span>
                </div>
              </div>

              {/* Interactive Vector Space Canvas (SVG) */}
              <div className="relative w-full h-80 sm:h-96 rounded-xl bg-black/80 border border-white/10 overflow-hidden flex items-center justify-center">
                <svg className="w-full h-full" viewBox="0 0 600 400">
                  {/* Grid Lines */}
                  <line x1="50" y1="200" x2="550" y2="200" stroke="rgba(255,255,255,0.08)" strokeDasharray="4 4" />
                  <line x1="300" y1="50" x2="300" y2="350" stroke="rgba(255,255,255,0.08)" strokeDasharray="4 4" />

                  {/* Concentric Similarity Orbit Rings */}
                  <circle cx="300" cy="200" r="160" fill="none" stroke="rgba(6,182,212,0.1)" strokeWidth="1" strokeDasharray="2 4" />
                  <circle cx="300" cy="200" r="110" fill="none" stroke="rgba(6,182,212,0.15)" strokeWidth="1" strokeDasharray="2 4" />
                  <circle cx="300" cy="200" r="60" fill="none" stroke="rgba(6,182,212,0.2)" strokeWidth="1.5" />
                  <text x="305" y="145" fill="rgba(6,182,212,0.5)" fontSize="9" fontFamily="monospace">Sim: 80%</text>
                  <text x="305" y="95" fill="rgba(6,182,212,0.4)" fontSize="9" fontFamily="monospace">Sim: 60%</text>
                  <text x="305" y="45" fill="rgba(6,182,212,0.3)" fontSize="9" fontFamily="monospace">Sim: 40%</text>

                  {/* Center Query Anchor */}
                  <circle cx="300" cy="200" r="6" fill="#06b6d4" />
                  <circle cx="300" cy="200" r="12" fill="none" stroke="#06b6d4" strokeWidth="1" opacity="0.6" className="animate-ping" />
                  <text x="300" y="222" textAnchor="middle" fill="#06b6d4" fontSize="10" fontWeight="bold" fontFamily="monospace">
                    {searchQuery ? `"${searchQuery.slice(0, 14)}..."` : 'Centroid (Query Point)'}
                  </text>

                  {/* Memory Points */}
                  {memories.map((mem, idx) => {
                    const N = memories.length;
                    const angle = (2 * Math.PI * idx) / Math.max(1, N) + 0.3;
                    const score = Number(mem.relevance_score || mem.score || 0.65);
                    // Radius from center: higher score = closer to center!
                    const dist = 50 + (1 - Math.min(1, Math.max(0, score))) * 160;
                    const cx = 300 + Math.cos(angle) * dist;
                    const cy = 200 + Math.sin(angle) * dist;
                    const importance = Number(mem.importance || 5);
                    const r = 5 + (importance / 10) * 7;
                    const isHovered = hoveredPoint?.id === mem.id;

                    const color =
                      score >= 0.75
                        ? '#06b6d4'
                        : score >= 0.5
                        ? '#a855f7'
                        : '#f59e0b';

                    return (
                      <g
                        key={String(mem.id)}
                        className="cursor-pointer transition-all duration-200"
                        onMouseEnter={() => setHoveredPoint(mem)}
                        onClick={() => setHoveredPoint(mem)}
                      >
                        {/* Connecting Line to centroid */}
                        <line
                          x1="300"
                          y1="200"
                          x2={cx}
                          y2={cy}
                          stroke={color}
                          strokeWidth={isHovered ? 1.5 : 0.6}
                          opacity={isHovered ? 0.8 : 0.25}
                        />

                        {/* Outer Glow Halo */}
                        {isHovered && (
                          <circle cx={cx} cy={cy} r={r + 8} fill="none" stroke={color} strokeWidth="2" opacity="0.8" />
                        )}

                        {/* Memory Node */}
                        <circle
                          cx={cx}
                          cy={cy}
                          r={isHovered ? r + 3 : r}
                          fill={color}
                          opacity={0.9}
                          stroke="#ffffff"
                          strokeWidth={1}
                        />

                        {/* Node Label */}
                        <text
                          x={cx}
                          y={cy - r - 4}
                          textAnchor="middle"
                          fill="#ffffff"
                          fontSize="9"
                          fontFamily="monospace"
                          fontWeight={isHovered ? 'bold' : 'normal'}
                          opacity={isHovered ? 1 : 0.7}
                        >
                          #{String(mem.id).slice(-4)}
                        </text>
                      </g>
                    );
                  })}
                </svg>
              </div>

              {/* Hovered / Selected Memory Detail Inspector */}
              <div className="p-4 rounded-xl bg-white/[0.03] border border-white/10 min-h-[90px] flex flex-col justify-center">
                {hoveredPoint ? (
                  <div className="space-y-1.5 animate-in fade-in">
                    <div className="flex items-center justify-between text-xs">
                      <div className="flex items-center gap-2">
                        <span className="font-bold text-white font-mono">
                          Vector Point #{String(hoveredPoint.id)}
                        </span>
                        <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-white/10 text-slate-300 uppercase">
                          {hoveredPoint.role || 'dialogue'}
                        </span>
                      </div>
                      <div className="flex items-center gap-3 text-xs font-mono">
                        <span className="text-cyan-300">
                          Cosine Relevance:{' '}
                          {(Number(hoveredPoint.relevance_score || hoveredPoint.score || 0) * 100).toFixed(1)}%
                        </span>
                        <span className="text-amber-300">
                          Importance: {Number(hoveredPoint.importance || 5).toFixed(1)}
                        </span>
                      </div>
                    </div>
                    <p className="text-xs text-slate-200 leading-relaxed font-medium">
                      &ldquo;{hoveredPoint.text || hoveredPoint.content}&rdquo;
                    </p>
                  </div>
                ) : (
                  <div className="text-center text-xs text-slate-400 font-mono">
                    Hover over or click any vector point in the 2D embedding space above to inspect its payload, cosine score, and semantic content.
                  </div>
                )}
              </div>
            </div>
          ) : (
            /* CARDS VIEW */
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {memories.map((mem) => {
                const text = mem.text || mem.content || 'Blank memory content';
                const score = mem.relevance_score || mem.score;
                const importance = mem.importance ?? 5;
                const role = mem.role || mem.memory_type || 'dialogue';

                return (
                  <div
                    key={String(mem.id)}
                    className="glass-card p-5 rounded-2xl border border-white/10 flex flex-col justify-between"
                  >
                    <div>
                      {/* Top metadata tags */}
                      <div className="flex items-center justify-between gap-2 mb-3">
                        <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-white/5 border border-white/10 text-slate-300 uppercase">
                          {role}
                        </span>

                        <div className="flex items-center gap-1.5">
                          <span
                            className={`px-2 py-0.5 rounded-full text-[10px] font-bold border ${getImportanceBadge(
                              importance
                            )}`}
                          >
                            Imp: {importance.toFixed(1)}
                          </span>

                          {score != null && (
                            <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-cyan-500/20 text-cyan-300 border border-cyan-500/40 font-mono">
                              Sim: {(Number(score) * 100).toFixed(0)}%
                            </span>
                          )}
                        </div>
                      </div>

                      {/* Memory Content Text */}
                      <p className="text-xs text-slate-200 leading-relaxed font-sans mb-4">
                        &ldquo;{text}&rdquo;
                      </p>
                    </div>

                    {/* Bottom Info and Actions */}
                    <div className="pt-3 border-t border-white/10 flex items-center justify-between text-[11px] text-slate-400">
                      <span className="font-mono">ID: #{String(mem.id).slice(0, 8)}</span>

                      <div className="flex items-center gap-2">
                        <button
                          onClick={() => {
                            setEditingMemory(mem);
                            setEditText(text);
                            setEditImportance(importance);
                          }}
                          className="px-2 py-1 rounded bg-white/5 hover:bg-white/10 text-slate-300 hover:text-white transition"
                        >
                          Edit ✏️
                        </button>
                        <button
                          onClick={() => handleDeleteMemory(mem.id)}
                          className="px-2 py-1 rounded bg-rose-500/10 hover:bg-rose-500/20 text-rose-300 transition"
                        >
                          Delete 🗑️
                        </button>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* CREATE MEMORY MODAL */}
        {showCreateModal && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-sm animate-in fade-in">
            <div className="glass-card max-w-lg w-full p-6 rounded-2xl border border-cyan-500/30 shadow-2xl relative">
              <div className="flex items-center justify-between mb-4 pb-3 border-b border-white/10">
                <h3 className="text-sm font-bold text-white flex items-center gap-2">
                  <span>✨</span>
                  <span>Synthesize Memory Vector into Qdrant</span>
                </h3>
                <button
                  onClick={() => setShowCreateModal(false)}
                  className="text-slate-400 hover:text-white text-xs"
                >
                  ✕
                </button>
              </div>

              <form onSubmit={handleCreateMemory} className="space-y-4">
                <div>
                  <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                    Target NPC Entity:
                  </label>
                  <select
                    required
                    value={newNpcId}
                    onChange={(e) => setNewNpcId(Number(e.target.value))}
                    className="w-full glass-input px-3.5 py-2.5 rounded-xl text-xs"
                  >
                    {npcs.map((npc) => (
                      <option key={npc.npc_id} value={npc.npc_id} className="bg-[#12121a]">
                        {npc.name} ({npc.location || 'Global'})
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                    Memory Dialogue / Observation Text:
                  </label>
                  <textarea
                    required
                    rows={3}
                    value={newText}
                    onChange={(e) => setNewText(e.target.value)}
                    placeholder="e.g. The adventurer helped find the lost silver locket in the crypt..."
                    className="w-full glass-input px-3.5 py-2.5 rounded-xl text-xs"
                  />
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                      Memory Role / Classification:
                    </label>
                    <select
                      value={newRole}
                      onChange={(e) => setNewRole(e.target.value)}
                      className="w-full glass-input px-3 py-2 rounded-xl text-xs"
                    >
                      <option value="dialogue" className="bg-[#12121a]">Dialogue</option>
                      <option value="observation" className="bg-[#12121a]">Observation</option>
                      <option value="reflection" className="bg-[#12121a]">Reflection</option>
                      <option value="plan" className="bg-[#12121a]">Plan</option>
                    </select>
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                      Importance Weight (0.0 - 10.0):
                    </label>
                    <input
                      type="number"
                      step="0.1"
                      min="0.0"
                      max="10.0"
                      value={newImportance}
                      onChange={(e) => setNewImportance(parseFloat(e.target.value) || 5.0)}
                      className="w-full glass-input px-3 py-2 rounded-xl text-xs"
                    />
                  </div>
                </div>

                <div className="flex items-center justify-end gap-2 pt-4 border-t border-white/10">
                  <button
                    type="button"
                    onClick={() => setShowCreateModal(false)}
                    className="px-4 py-2 rounded-xl bg-white/5 hover:bg-white/10 text-slate-300 text-xs font-semibold"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={submittingCreate}
                    className="px-4 py-2 rounded-xl bg-cyan-600 hover:bg-cyan-500 text-white text-xs font-semibold shadow-lg shadow-cyan-600/30"
                  >
                    {submittingCreate ? 'Embedding Vector...' : 'Inject Vector'}
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}

        {/* EDIT MEMORY MODAL */}
        {editingMemory && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-sm animate-in fade-in">
            <div className="glass-card max-w-lg w-full p-6 rounded-2xl border border-violet-500/30 shadow-2xl relative">
              <div className="flex items-center justify-between mb-4 pb-3 border-b border-white/10">
                <h3 className="text-sm font-bold text-white flex items-center gap-2">
                  <span>✏️</span>
                  <span>Update Memory Vector #{String(editingMemory.id).slice(0, 8)}</span>
                </h3>
                <button
                  onClick={() => setEditingMemory(null)}
                  className="text-slate-400 hover:text-white text-xs"
                >
                  ✕
                </button>
              </div>

              <form onSubmit={handleUpdateMemory} className="space-y-4">
                <div>
                  <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                    Memory Text:
                  </label>
                  <textarea
                    required
                    rows={3}
                    value={editText}
                    onChange={(e) => setEditText(e.target.value)}
                    className="w-full glass-input px-3.5 py-2.5 rounded-xl text-xs"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                    Importance Score (0.0 - 10.0):
                  </label>
                  <input
                    type="number"
                    step="0.1"
                    min="0.0"
                    max="10.0"
                    value={editImportance}
                    onChange={(e) => setEditImportance(parseFloat(e.target.value) || 5.0)}
                    className="w-full glass-input px-3 py-2 rounded-xl text-xs"
                  />
                </div>

                <div className="flex items-center justify-end gap-2 pt-4 border-t border-white/10">
                  <button
                    type="button"
                    onClick={() => setEditingMemory(null)}
                    className="px-4 py-2 rounded-xl bg-white/5 hover:bg-white/10 text-slate-300 text-xs font-semibold"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={submittingEdit}
                    className="px-4 py-2 rounded-xl bg-violet-600 hover:bg-violet-500 text-white text-xs font-semibold shadow-lg shadow-violet-600/30"
                  >
                    {submittingEdit ? 'Saving...' : 'Update Memory'}
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}

        {/* CONFIRM CLEAR PLAYER-NPC MODAL */}
        {confirmClearNpc && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-in fade-in">
            <div className="glass-card max-w-md w-full p-6 rounded-2xl border border-rose-500/40 shadow-2xl text-center">
              <div className="text-3xl mb-2">⚠️</div>
              <h3 className="text-base font-bold text-white mb-2">
                Purge All Shared Memories?
              </h3>
              <p className="text-xs text-slate-300 mb-4 leading-relaxed">
                This will delete all episodic vector memories in Qdrant connecting Player #{user?.player_id} with{' '}
                <strong className="text-white">{confirmClearNpc.name}</strong>. This action is irreversible.
              </p>

              <div className="flex items-center justify-center gap-3">
                <button
                  onClick={() => setConfirmClearNpc(null)}
                  className="px-4 py-2 rounded-xl bg-white/10 hover:bg-white/20 text-white text-xs font-semibold"
                >
                  Cancel
                </button>
                <button
                  onClick={handleClearPlayerNPCMemories}
                  className="px-4 py-2 rounded-xl bg-rose-600 hover:bg-rose-500 text-white text-xs font-semibold shadow-lg shadow-rose-600/30"
                >
                  Confirm Purge
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </ProtectedRoute>
  );
}
