'use client';

import React, { useEffect, useRef, useState } from 'react';
import { api, NPCResponse } from '@/lib/api';

interface WidgetMessage {
  id: string;
  sender: 'user' | 'npc' | 'system';
  text: string;
  source?: string;
}

/**
 * Small floating chat bubble (bottom-right) for talking to any NPC from the admin
 * panel. Replies stream in live from Gemini through POST /api/chat/stream, using
 * the same memory + game-state pipeline as the main chat page.
 */
export default function NpcChatWidget() {
  const [open, setOpen] = useState(false);
  const [npcs, setNpcs] = useState<NPCResponse[]>([]);
  const [npcId, setNpcId] = useState<number | null>(null);
  // Conversation history kept per NPC while the page is open.
  const [threads, setThreads] = useState<Record<number, WidgetMessage[]>>({});
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const [waitingFirstToken, setWaitingFirstToken] = useState(false);
  const [memoryOnline, setMemoryOnline] = useState(true);
  const endRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const messages = npcId != null ? threads[npcId] || [] : [];
  const npc = npcs.find((n) => n.npc_id === npcId);

  useEffect(() => {
    if (!open || npcs.length > 0) return;
    api.npcs
      .getAll()
      .then((list) => {
        setNpcs(list);
        if (list.length > 0) setNpcId(list[0].npc_id);
      })
      .catch(() => setNpcs([]));
  }, [open, npcs.length]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, waitingFirstToken]);

  useEffect(() => {
    if (open) inputRef.current?.focus();
  }, [open, npcId]);

  const updateThread = (id: number, fn: (msgs: WidgetMessage[]) => WidgetMessage[]) =>
    setThreads((prev) => ({ ...prev, [id]: fn(prev[id] || []) }));

  const send = async (e: React.FormEvent) => {
    e.preventDefault();
    const text = input.trim();
    if (!text || npcId == null || sending) return;
    const targetId = npcId;
    const replyId = `npc-${Date.now()}`;
    let started = false;
    const history = (threads[targetId] || [])
      .filter((m) => m.sender !== 'system')
      .slice(-10)
      .map((m) => ({ role: m.sender === 'user' ? ('player' as const) : ('npc' as const), text: m.text.slice(0, 2000) }));

    setInput('');
    setSending(true);
    setWaitingFirstToken(true);
    updateThread(targetId, (m) => [...m, { id: `me-${Date.now()}`, sender: 'user', text }]);

    try {
      const res = await api.chat.stream(
        { npc_id: targetId, message: text, history },
        {
          onMeta: (meta) => setMemoryOnline(meta.memory_online !== false),
          onDelta: (chunk) => {
            if (!started) {
              started = true;
              setWaitingFirstToken(false);
              updateThread(targetId, (m) => [...m, { id: replyId, sender: 'npc', text: chunk }]);
            } else {
              updateThread(targetId, (m) =>
                m.map((x) => (x.id === replyId ? { ...x, text: x.text + chunk } : x))
              );
            }
          },
        }
      );
      updateThread(targetId, (m) =>
        m.map((x) => (x.id === replyId ? { ...x, text: res.reply || x.text, source: res.source } : x))
      );
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Could not reach the server.';
      updateThread(targetId, (m) => [...m, { id: `err-${Date.now()}`, sender: 'system', text: `⚠️ ${msg}` }]);
    } finally {
      setSending(false);
      setWaitingFirstToken(false);
    }
  };

  return (
    <div className="fixed bottom-5 right-5 z-50 flex flex-col items-end gap-3">
      {open && (
        <div className="w-[min(340px,calc(100vw-2rem))] h-[460px] max-h-[calc(100vh-7rem)] flex flex-col rounded-2xl border border-violet-500/30 bg-[#0f0f1a]/95 backdrop-blur shadow-2xl shadow-violet-900/40 overflow-hidden">
          {/* Header */}
          <div className="flex items-center gap-2 px-3 py-2.5 border-b border-white/10 bg-violet-950/40">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" title="Live" />
            <select
              value={npcId ?? ''}
              onChange={(e) => setNpcId(Number(e.target.value))}
              disabled={sending}
              aria-label="Choose NPC"
              className="flex-1 min-w-0 bg-transparent text-xs font-semibold text-white focus:outline-none cursor-pointer"
            >
              {npcs.length === 0 && <option value="">Loading NPCs…</option>}
              {npcs.map((n) => (
                <option key={n.npc_id} value={n.npc_id} className="bg-[#151522]">
                  {n.name}
                </option>
              ))}
            </select>
            <button
              onClick={() => setOpen(false)}
              aria-label="Close chat"
              className="text-slate-400 hover:text-white text-sm px-1"
            >
              ✕
            </button>
          </div>

          {!memoryOnline && (
            <div className="px-3 py-1.5 text-[10px] text-amber-300 bg-amber-500/10 border-b border-amber-500/20">
              ⚠️ Long-term memory is offline — NPCs won&apos;t remember this chat later.
            </div>
          )}

          {/* Messages */}
          <div className="flex-1 overflow-y-auto p-3 space-y-2 text-xs">
            {messages.length === 0 && (
              <p className="text-slate-500 text-center mt-8 px-4">
                {npc ? `Say something to ${npc.name}. Replies stream live from Gemini.` : 'Pick an NPC to start.'}
              </p>
            )}
            {messages.map((m) => (
              <div key={m.id} className={`flex ${m.sender === 'user' ? 'justify-end' : 'justify-start'}`}>
                <div
                  className={`max-w-[85%] rounded-xl px-3 py-2 leading-relaxed whitespace-pre-wrap ${
                    m.sender === 'user'
                      ? 'bg-violet-600 text-white'
                      : m.sender === 'system'
                        ? 'bg-red-500/15 text-red-300 border border-red-500/30'
                        : 'bg-white/5 text-slate-200 border border-white/10'
                  }`}
                >
                  {m.text}
                  {m.source && (
                    <div
                      className={`mt-1 text-[9px] font-mono ${m.source === 'mock' ? 'text-amber-400' : 'text-emerald-400'}`}
                    >
                      {m.source === 'mock' ? 'offline fallback (Gemini unavailable)' : `✦ ${m.source}`}
                    </div>
                  )}
                </div>
              </div>
            ))}
            {waitingFirstToken && (
              <div className="flex gap-1 px-3 py-2 w-fit rounded-xl bg-white/5 border border-white/10">
                {[0, 150, 300].map((d) => (
                  <span
                    key={d}
                    className="w-1.5 h-1.5 rounded-full bg-violet-400 animate-bounce"
                    style={{ animationDelay: `${d}ms` }}
                  />
                ))}
              </div>
            )}
            <div ref={endRef} />
          </div>

          {/* Input */}
          <form onSubmit={send} className="flex gap-2 p-2 border-t border-white/10">
            <input
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder={npc ? `Message ${npc.name}…` : 'Message…'}
              disabled={sending || npcId == null}
              className="flex-1 min-w-0 rounded-lg bg-white/5 border border-white/10 px-3 py-2 text-xs text-white placeholder:text-slate-500 focus:outline-none focus:border-violet-500/60"
            />
            <button
              type="submit"
              disabled={sending || !input.trim() || npcId == null}
              className="rounded-lg bg-violet-600 hover:bg-violet-500 disabled:opacity-40 px-3 text-xs font-semibold text-white"
            >
              Send
            </button>
          </form>
        </div>
      )}

      <button
        onClick={() => setOpen((o) => !o)}
        aria-label={open ? 'Close NPC chat' : 'Open NPC chat'}
        title="Chat with NPCs"
        className="w-11 h-11 rounded-full bg-violet-600 hover:bg-violet-500 text-white text-lg shadow-lg shadow-violet-900/50 flex items-center justify-center transition-transform hover:scale-105"
      >
        {open ? '✕' : '💬'}
      </button>
    </div>
  );
}
