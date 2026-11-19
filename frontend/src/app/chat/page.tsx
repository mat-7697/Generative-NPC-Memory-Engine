'use client';

import React, { useState, useEffect, useRef } from 'react';
import ProtectedRoute from '@/components/ProtectedRoute';
import { useAuth } from '@/lib/auth';
import { useToast } from '@/lib/toast';
import {
  api,
  NPCResponse,
  NPCRelationship,
  ChatResponse,
  MemoryResponse,
} from '@/lib/api';

interface ChatMessage {
  id: string;
  sender: 'user' | 'npc';
  senderName: string;
  text: string;
  timestamp: string;
  memoriesUsed?: any[];
  affinityChange?: number;
  source?: string;
}

export default function ChatPage() {
  const { user, refreshUser } = useAuth();
  const { success, error: toastError, info } = useToast();

  const [npcs, setNpcs] = useState<NPCResponse[]>([]);
  const [selectedNpc, setSelectedNpc] = useState<NPCResponse | null>(null);
  const [relationship, setRelationship] = useState<NPCRelationship | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputText, setInputText] = useState('');
  const [sending, setSending] = useState(false);
  // True once the first streamed token arrives (hides the typing indicator).
  const [streamStarted, setStreamStarted] = useState(false);
  const [loadingNpcs, setLoadingNpcs] = useState(true);
  const [latestMemoriesUsed, setLatestMemoriesUsed] = useState<any[]>([]);
  const [showMemoriesSidebar, setShowMemoriesSidebar] = useState(true);

  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, sending]);

  // Load NPCs on mount
  useEffect(() => {
    let mounted = true;
    async function fetchNPCs() {
      try {
        setLoadingNpcs(true);
        const list = await api.npcs.getAll();
        if (!mounted) return;
        setNpcs(list);
        if (list.length > 0) {
          setSelectedNpc(list[0]);
        }
      } catch (err: any) {
        console.error('Failed to load NPCs:', err);
      } finally {
        if (mounted) setLoadingNpcs(false);
      }
    }
    fetchNPCs();
    return () => {
      mounted = false;
    };
  }, []);

  const selectedNpcId = selectedNpc?.npc_id;

  // When selected NPC changes, fetch relationship & initialize dialogue
  useEffect(() => {
    if (!selectedNpc) return;
    const targetNpc = selectedNpc;
    const targetId = targetNpc.npc_id;

    let mounted = true;
    async function fetchNpcData() {
      try {
        const rel = await api.npcs.getRelationship(targetId);
        if (!mounted) return;
        setRelationship(rel);
      } catch {
        if (!mounted) return;
        // Fallback default relationship if none exists yet
        setRelationship({
          player_id: user?.player_id || 1,
          npc_id: targetId,
          affinity_score: 0.0,
          interaction_count: 0,
        });
      }

      if (!mounted) return;
      // Initial greeting from NPC
      setMessages([
        {
          id: 'greeting',
          sender: 'npc',
          senderName: targetNpc.name,
          text:
            targetNpc.greeting ||
            `Greetings, ${user?.username || 'traveler'}. What brings you to speak with me?`,
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        },
      ]);
      setLatestMemoriesUsed([]);
    }

    fetchNpcData();
    return () => {
      mounted = false;
    };
  }, [selectedNpcId, user?.player_id, user?.username]);

  const handleSendMessage = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputText.trim() || !selectedNpc || sending) return;

    const userText = inputText.trim();
    setInputText('');

    const userMsg: ChatMessage = {
      id: Math.random().toString(),
      sender: 'user',
      senderName: user?.username || 'Hero',
      text: userText,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    };

    // Recent on-screen dialogue (minus system/error bubbles) gives the NPC short-term
    // context even if long-term memory is offline.
    const history = messages
      .filter((m) => m.senderName !== 'System' && m.text.trim())
      .slice(-10)
      .map((m) => ({ role: m.sender === 'user' ? ('player' as const) : ('npc' as const), text: m.text.slice(0, 2000) }));

    setMessages((prev) => [...prev, userMsg]);
    setSending(true);
    setStreamStarted(false);

    const npcMsgId = Math.random().toString();
    let started = false;
    const patchNpcMsg = (patch: (m: ChatMessage) => ChatMessage) =>
      setMessages((prev) => prev.map((m) => (m.id === npcMsgId ? patch(m) : m)));

    try {
      const response: ChatResponse = await api.chat.stream(
        { npc_id: selectedNpc.npc_id, message: userText, history },
        {
          onMeta: (meta) => {
            if (meta.memory_online === false) {
              toastError('Long-term memory (Qdrant) is offline — this chat will not be remembered later.');
            }
          },
          onDelta: (chunk) => {
            if (!started) {
              started = true;
              setStreamStarted(true);
              // First token: add the NPC bubble that the rest of the reply streams into.
              setMessages((prev) => [
                ...prev,
                {
                  id: npcMsgId,
                  sender: 'npc',
                  senderName: selectedNpc.name,
                  text: chunk,
                  timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
                },
              ]);
            } else {
              patchNpcMsg((m) => ({ ...m, text: m.text + chunk }));
            }
          },
        }
      );

      patchNpcMsg((m) => ({
        ...m,
        senderName: response.npc_name || selectedNpc.name,
        text: response.reply || m.text,
        memoriesUsed: response.memories_used,
        affinityChange: response.affinity_change,
        source: response.source,
      }));
      if (response.memories_used && response.memories_used.length > 0) {
        setLatestMemoriesUsed(response.memories_used);
      }

      // Update relationship affinity in local state
      if (response.affinity_change !== undefined) {
        const affChange = response.affinity_change;
        setRelationship((prev) => {
          if (!prev) return prev;
          const newScore = Math.max(
            -100,
            Math.min(100, (prev.affinity_score || 0) + affChange)
          );
          return {
            ...prev,
            affinity_score: newScore,
            interaction_count: (prev.interaction_count || 0) + 1,
          };
        });

        if (affChange > 0) {
          success(`+${affChange} Affinity with ${selectedNpc.name}!`);
        } else if (affChange < 0) {
          info(`${affChange} Affinity with ${selectedNpc.name}`);
        }
      }

      // Refresh player's gold/xp in case NPC gave rewards
      await refreshUser();
    } catch (err: any) {
      toastError(err.message || 'Failed to exchange dialogue with NPC.');
      // Add an error message bubble so user knows something went wrong
      const errorMsg: ChatMessage = {
        id: Math.random().toString(),
        sender: 'npc',
        senderName: 'System',
        text: `⚠️ Connection error: ${err.message || 'Could not reach the server. Please try again.'}`,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      };
      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setSending(false);
      setStreamStarted(false);
    }
  };

  // Helper for NPC emoji avatar based on name/location
  const getNPCAvatar = (name: string) => {
    if (name.includes('Elder') || name.includes('Thorne') || name.includes('Sage')) return '🧙‍♂️';
    if (name.includes('Blacksmith') || name.includes('Kaelen')) return '⚒️';
    if (name.includes('Lyra') || name.includes('Alchemist') || name.includes('Herbalist')) return '🧪';
    if (name.includes('Guard') || name.includes('Captain')) return '🛡️';
    if (name.includes('Merchant') || name.includes('Trader')) return '💰';
    return '👤';
  };

  const affinityScore = relationship?.affinity_score || 0;
  // Calculate percentage from -100..+100 to 0..100%
  const affinityPercent = Math.max(0, Math.min(100, ((affinityScore + 100) / 200) * 100));

  return (
    <ProtectedRoute>
      <div className="space-y-4">
        {/* Header / NPC Picker */}
        <div className="glass-card rounded-2xl p-4 sm:p-5 border border-violet-500/20 flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="w-12 h-12 rounded-xl bg-violet-600/20 border border-violet-500/40 flex items-center justify-center text-2xl shadow-inner">
              {selectedNpc ? getNPCAvatar(selectedNpc.name) : '💬'}
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-lg font-bold text-white">
                  {selectedNpc?.name || 'Select an NPC'}
                </h1>
                {selectedNpc?.location && (
                  <span className="text-[10px] bg-cyan-500/20 text-cyan-300 border border-cyan-500/30 px-2 py-0.5 rounded-full">
                    📍 {selectedNpc.location}
                  </span>
                )}
              </div>
              <p className="text-xs text-slate-400 max-w-xl truncate">
                {selectedNpc?.persona || 'Conversational Generative NPC Memory Agent'}
              </p>
            </div>
          </div>

          {/* NPC Selector Dropdown / Pills */}
          <div className="flex items-center gap-2 w-full md:w-auto">
            <label className="text-xs text-slate-400 font-semibold whitespace-nowrap">
              Active Entity:
            </label>
            <select
              value={selectedNpc?.npc_id || ''}
              onChange={(e) => {
                const found = npcs.find((n) => n.npc_id === Number(e.target.value));
                if (found) setSelectedNpc(found);
              }}
              disabled={loadingNpcs}
              className="glass-input text-xs font-semibold px-3 py-2 rounded-xl text-slate-200 border border-white/10 w-full md:w-48"
            >
              {npcs.map((npc) => (
                <option key={npc.npc_id} value={npc.npc_id} className="bg-[#12121a]">
                  {npc.name} ({npc.location || 'Roaming'})
                </option>
              ))}
            </select>
            <button
              onClick={() => setShowMemoriesSidebar(!showMemoriesSidebar)}
              title="Toggle Semantic Memories Inspector"
              className={`p-2 rounded-xl border text-xs transition ${
                showMemoriesSidebar
                  ? 'bg-violet-600 text-white border-violet-500'
                  : 'bg-white/5 text-slate-400 border-white/10 hover:text-white'
              }`}
            >
              🧠
            </button>
          </div>
        </div>

        {/* Main Dialogue Layout */}
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-4 min-h-[580px]">
          {/* Chat Stream (3 Cols) */}
          <div
            className={`${
              showMemoriesSidebar ? 'lg:col-span-3' : 'lg:col-span-4'
            } glass-card rounded-2xl flex flex-col border border-white/10 overflow-hidden h-[620px] transition-all`}
          >
            {/* Top Affinity Bar */}
            <div className="px-5 py-3 border-b border-white/10 bg-white/[0.02] flex items-center justify-between text-xs">
              <div className="flex items-center gap-2">
                <span className="font-semibold text-slate-300">Affinity Matrix:</span>
                <span
                  className={`font-mono font-bold ${
                    affinityScore > 20
                      ? 'text-emerald-400'
                      : affinityScore < -20
                      ? 'text-rose-400'
                      : 'text-amber-400'
                  }`}
                >
                  {affinityScore > 0 ? `+${affinityScore.toFixed(1)}` : affinityScore.toFixed(1)}
                  /100
                </span>
                <span className="text-[10px] text-slate-400">
                  ({relationship?.interaction_count || 0} interactions)
                </span>
              </div>

              {/* Mini Affinity Gauge */}
              <div className="w-36 bg-black/40 h-2 rounded-full overflow-hidden border border-white/10">
                <div
                  className={`h-full transition-all duration-500 ${
                    affinityScore > 20
                      ? 'bg-gradient-to-r from-emerald-500 to-cyan-400'
                      : affinityScore < -20
                      ? 'bg-gradient-to-r from-rose-600 to-amber-500'
                      : 'bg-gradient-to-r from-amber-500 to-cyan-400'
                  }`}
                  style={{ width: `${affinityPercent}%` }}
                ></div>
              </div>
            </div>

            {/* Scrollable Message History */}
            <div className="flex-1 p-5 overflow-y-auto space-y-4">
              {messages.map((msg) => {
                const isUser = msg.sender === 'user';
                return (
                  <div
                    key={msg.id}
                    className={`flex items-start gap-3 ${
                      isUser ? 'flex-row-reverse' : 'flex-row'
                    }`}
                  >
                    {/* Avatar */}
                    <div
                      className={`w-9 h-9 rounded-xl flex items-center justify-center text-sm shadow-md shrink-0 ${
                        isUser
                          ? 'bg-violet-600/30 border border-violet-500/50 text-white'
                          : 'bg-indigo-950/60 border border-indigo-500/40 text-cyan-300'
                      }`}
                    >
                      {isUser ? '⚔️' : getNPCAvatar(msg.senderName)}
                    </div>

                    {/* Bubble */}
                    <div
                      className={`max-w-[78%] rounded-2xl p-4 text-xs leading-relaxed ${
                        isUser
                          ? 'bg-gradient-to-br from-violet-600 to-indigo-700 text-white shadow-lg shadow-violet-600/20'
                          : 'bg-[#151522]/90 border border-white/10 text-slate-200'
                      }`}
                    >
                      <div className="flex items-center justify-between gap-4 mb-1 text-[10px] opacity-75">
                        <span className="font-semibold uppercase tracking-wider">
                          {msg.senderName}
                        </span>
                        <span className="flex items-center gap-1.5">
                          {msg.source && (
                            <span
                              title={msg.source === 'mock' ? 'Gemini unavailable — offline fallback reply' : `Live reply from ${msg.source}`}
                              className={`px-1.5 py-0.5 rounded font-mono normal-case ${
                                msg.source === 'mock'
                                  ? 'bg-amber-500/20 text-amber-300'
                                  : 'bg-emerald-500/20 text-emerald-300'
                              }`}
                            >
                              {msg.source === 'mock' ? 'offline' : '✦ gemini'}
                            </span>
                          )}
                          {msg.timestamp}
                        </span>
                      </div>
                      <p className="whitespace-pre-wrap">{msg.text}</p>

                      {/* If NPC used memories in this message */}
                      {msg.memoriesUsed && msg.memoriesUsed.length > 0 && (
                        <div className="mt-2 pt-2 border-t border-white/10 flex items-center gap-1.5 text-[10px] text-violet-300">
                          <span>🧠</span>
                          <span>Informed by {msg.memoriesUsed.length} retrieved memories</span>
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}

              {/* Typing indicator */}
              {sending && !streamStarted && (
                <div className="flex items-center gap-3">
                  <div className="w-9 h-9 rounded-xl bg-indigo-950/60 border border-indigo-500/40 flex items-center justify-center text-sm text-cyan-300 shrink-0">
                    {selectedNpc ? getNPCAvatar(selectedNpc.name) : '🤖'}
                  </div>
                  <div className="glass-card px-4 py-3 rounded-2xl border border-white/10 flex items-center gap-1.5">
                    <div className="w-1.5 h-1.5 rounded-full bg-violet-400 animate-bounce"></div>
                    <div className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-bounce [animation-delay:0.2s]"></div>
                    <div className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-bounce [animation-delay:0.4s]"></div>
                    <span className="text-[11px] text-slate-400 ml-2 font-mono">
                      Querying Qdrant & synthesizing persona...
                    </span>
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>

            {/* Input Bar */}
            <form
              onSubmit={handleSendMessage}
              className="p-3.5 border-t border-white/10 bg-black/20 flex items-center gap-2"
            >
              <input
                type="text"
                value={inputText}
                onChange={(e) => setInputText(e.target.value)}
                placeholder={`Speak to ${selectedNpc?.name || 'NPC'}... (e.g. Ask for rumors, items, or quests)`}
                disabled={sending || !selectedNpc}
                className="flex-1 glass-input px-4 py-2.5 rounded-xl text-xs sm:text-sm text-white placeholder-slate-500"
              />
              <button
                type="submit"
                disabled={sending || !inputText.trim()}
                className="px-4 py-2.5 rounded-xl bg-gradient-to-r from-violet-600 to-cyan-500 hover:from-violet-500 hover:to-cyan-400 text-white font-semibold text-xs tracking-wider shadow-lg shadow-violet-600/30 transition disabled:opacity-40 flex items-center gap-1.5"
              >
                <span>Send</span>
                <span>⚡</span>
              </button>
            </form>
          </div>

          {/* Right Sidebar: Semantic Memory Inspector & State (1 Col) */}
          {showMemoriesSidebar && (
            <div className="glass-card rounded-2xl p-4 border border-white/10 flex flex-col justify-between h-[620px] overflow-hidden">
              <div className="overflow-y-auto pr-1 space-y-4">
                <div className="flex items-center justify-between pb-2 border-b border-white/10">
                  <div className="flex items-center gap-1.5">
                    <span className="text-base">🧠</span>
                    <h3 className="text-xs font-bold text-slate-200 uppercase tracking-wider">
                      Neural Context
                    </h3>
                  </div>
                  <span className="text-[10px] bg-violet-500/20 text-violet-300 px-2 py-0.5 rounded font-mono">
                    Top-K RAG
                  </span>
                </div>

                {/* NPC Personality Traits */}
                <div>
                  <h4 className="text-[11px] font-semibold text-slate-400 mb-1.5">
                    Core Personality Traits:
                  </h4>
                  <div className="p-2.5 rounded-xl bg-white/[0.03] border border-white/5 text-[11px] text-slate-300">
                    {selectedNpc?.personality_traits ? (
                      typeof selectedNpc.personality_traits === 'string' ? (
                        selectedNpc.personality_traits
                      ) : (
                        <div className="space-y-1">
                          {Object.entries(selectedNpc.personality_traits).map(([k, v]) => (
                            <div key={k} className="flex justify-between gap-3">
                              <span className="capitalize text-slate-400 shrink-0">{k}:</span>
                              <span className="font-mono text-cyan-300 text-right break-words min-w-0">{String(v)}</span>
                            </div>
                          ))}
                        </div>
                      )
                    ) : (
                      <span className="text-slate-500 italic">Balanced persona archetype</span>
                    )}
                  </div>
                </div>

                {/* Retrieved Memories List */}
                <div>
                  <h4 className="text-[11px] font-semibold text-slate-400 mb-1.5 flex items-center justify-between">
                    <span>Retrieved Episodic Memories:</span>
                    <span className="text-[10px] text-violet-400 font-mono">
                      {latestMemoriesUsed.length} Active
                    </span>
                  </h4>

                  {latestMemoriesUsed.length === 0 ? (
                    <div className="p-3 rounded-xl bg-white/[0.02] border border-dashed border-white/10 text-center text-[11px] text-slate-500">
                      Send a message to prompt Qdrant vector retrieval.
                    </div>
                  ) : (
                    <div className="space-y-2">
                      {latestMemoriesUsed.map((mem: any, i: number) => {
                        const content =
                          typeof mem === 'string'
                            ? mem
                            : mem.content || mem.text || JSON.stringify(mem);
                        const score = mem.relevance_score || mem.score;
                        return (
                          <div
                            key={i}
                            className="p-2.5 rounded-xl bg-violet-950/30 border border-violet-500/20 text-[11px] space-y-1"
                          >
                            <div className="flex items-center justify-between text-[10px] text-violet-300">
                              <span>Memory #{i + 1}</span>
                              {score !== undefined && (
                                <span className="font-mono text-cyan-300">
                                  Sim: {(Number(score) * 100).toFixed(0)}%
                                </span>
                              )}
                            </div>
                            <p className="text-slate-300 italic">{content}</p>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              </div>

              {/* Game State Quick Footer */}
              <div className="mt-3 pt-3 border-t border-white/10">
                <div className="text-[10px] text-slate-400 font-semibold uppercase tracking-wider mb-1.5">
                  Your Current State:
                </div>
                <div className="grid grid-cols-2 gap-2 text-center text-xs">
                  <div className="p-1.5 rounded-lg bg-amber-500/10 border border-amber-500/20 text-amber-300 font-bold">
                    🪙 {user?.gold ?? 0}
                  </div>
                  <div className="p-1.5 rounded-lg bg-cyan-500/10 border border-cyan-500/20 text-cyan-300 font-bold">
                    ⚔️ Lv. {user?.level ?? 1}
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </ProtectedRoute>
  );
}
