'use client';

import React, { useState, useEffect, useCallback } from 'react';
import Link from 'next/link';
import ProtectedRoute from '@/components/ProtectedRoute';
import { useAuth } from '@/lib/auth';
import { useToast } from '@/lib/toast';
import {
  api,
  QuestResponse,
  PlayerQuestResponse,
  PrerequisiteChain,
  QuestType,
} from '@/lib/api';

export default function QuestsPage() {
  const { user, refreshUser } = useAuth();
  const { success, error: toastError, info } = useToast();

  const [quests, setQuests] = useState<QuestResponse[]>([]);
  const [myQuests, setMyQuests] = useState<PlayerQuestResponse[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState<number | null>(null);

  // Prerequisites Tree Modal State
  const [selectedQuestPrereqs, setSelectedQuestPrereqs] = useState<{
    quest: QuestResponse;
    chain: PrerequisiteChain[];
  } | null>(null);
  const [loadingPrereqs, setLoadingPrereqs] = useState(false);

  // Objective Challenge Modal State
  const [activeChallengeQuest, setActiveChallengeQuest] = useState<
    QuestResponse | PlayerQuestResponse | null
  >(null);
  const [solutionInput, setSolutionInput] = useState('');
  const [challengeError, setChallengeError] = useState<string | null>(null);
  const [showHint, setShowHint] = useState(false);
  const [submittingSolution, setSubmittingSolution] = useState(false);
  const [resettingProgress, setResettingProgress] = useState(false);

  const loadQuestsData = useCallback(async () => {
    try {
      setLoading(true);
      const [allRes, myRes] = await Promise.allSettled([
        searchQuery ? api.quests.search(searchQuery) : api.quests.getAll(),
        api.quests.getMyQuests(),
      ]);

      if (allRes.status === 'fulfilled') setQuests(allRes.value || []);
      if (myRes.status === 'fulfilled') setMyQuests(myRes.value || []);
    } catch (err: any) {
      toastError(err.message || 'Failed to sync quest registry.');
    } finally {
      setLoading(false);
    }
  }, [searchQuery, toastError]);

  useEffect(() => {
    loadQuestsData();
  }, [loadQuestsData]);

  // Start Quest
  const handleStartQuest = async (questId: number) => {
    setActionLoading(questId);
    try {
      await api.quests.start(questId);
      success('Quest accepted! Complete the mission objective challenge to claim rewards.');
      await loadQuestsData();
    } catch (err: any) {
      toastError(err.message || 'Failed to start quest. Ensure prerequisites are met.');
    } finally {
      setActionLoading(null);
    }
  };

  // Open Challenge Modal for an active quest
  const openChallengeModal = (quest: QuestResponse | PlayerQuestResponse) => {
    // Merge with full quest info to ensure challenge details are present
    const fullQuest = quests.find((q) => q.quest_id === quest.quest_id) || quest;
    setActiveChallengeQuest(fullQuest);
    setSolutionInput('');
    setChallengeError(null);
    setShowHint(false);
  };

  // Verify Solution and Complete Quest
  const handleVerifySolution = async () => {
    if (!activeChallengeQuest) return;
    if (!solutionInput.trim()) {
      setChallengeError('Please enter an answer or codeword to verify.');
      return;
    }

    setSubmittingSolution(true);
    setChallengeError(null);

    try {
      const res = await api.quests.complete(
        activeChallengeQuest.quest_id,
        solutionInput.trim()
      );
      const msg =
        res.message ||
        res.detail ||
        `Quest '${activeChallengeQuest.title}' solved! Rewards and XP awarded.`;
      success(msg);
      setActiveChallengeQuest(null);
      await refreshUser();
      await loadQuestsData();
    } catch (err: any) {
      setChallengeError(
        err.message || 'Incorrect objective solution! Check the question or reveal the hint.'
      );
    } finally {
      setSubmittingSolution(false);
    }
  };

  // Reset Quest Progress for Live Demonstration
  const handleResetProgress = async (resetLevel: boolean = false) => {
    const promptMsg = resetLevel
      ? 'Reset your player to Lv. 1 and clear all completed quests for a complete fresh demonstration?'
      : 'Reset your quest progress back to available so you can replay all challenges?';

    if (!confirm(promptMsg)) return;

    setResettingProgress(true);
    try {
      const res = await api.quests.resetProgress(resetLevel);
      success(res.detail || 'Quest progress reset! Quests are ready for demonstration.');
      await refreshUser();
      await loadQuestsData();
    } catch (err: any) {
      toastError(err.message || 'Failed to reset quest progress.');
    } finally {
      setResettingProgress(false);
    }
  };

  // Inspect Prerequisites Tree
  const handleViewPrereqs = async (quest: QuestResponse) => {
    setLoadingPrereqs(true);
    try {
      const chain = await api.quests.getPrerequisites(quest.quest_id);
      setSelectedQuestPrereqs({ quest, chain: chain || [] });
    } catch {
      setSelectedQuestPrereqs({ quest, chain: [] });
    } finally {
      setLoadingPrereqs(false);
    }
  };

  // Status mapping
  const getQuestStatus = (questId: number) => {
    const entry = myQuests.find((q) => q.quest_id === questId);
    return entry ? entry.status : 'available';
  };

  const getQuestTypeBadge = (type: QuestType = 'main') => {
    switch (type) {
      case 'main':
        return 'bg-amber-500/20 text-amber-300 border-amber-500/40';
      case 'side':
        return 'bg-cyan-500/20 text-cyan-300 border-cyan-500/40';
      case 'daily':
        return 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40';
      case 'hidden':
        return 'bg-purple-500/20 text-purple-300 border-purple-500/40';
      default:
        return 'bg-slate-500/20 text-slate-300 border-slate-500/40';
    }
  };

  const getChallengeTypeIcon = (type?: string | null) => {
    if (!type) return '⚔️';
    const lower = type.toLowerCase();
    if (lower.includes('math') || lower.includes('ratio')) return '🧮';
    if (lower.includes('cipher') || lower.includes('intel') || lower.includes('ctf'))
      return '🕵️';
    if (lower.includes('riddle')) return '🗝️';
    if (lower.includes('crypto') || lower.includes('logic')) return '💻';
    if (lower.includes('forge') || lower.includes('iron')) return '⚒️';
    return '🎯';
  };

  return (
    <ProtectedRoute>
      <div className="space-y-6 pb-12">
        {/* Header */}
        <div className="glass-card rounded-2xl p-6 border border-emerald-500/20 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <span className="text-xs font-mono uppercase tracking-widest text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded border border-emerald-500/30">
                Quest Graph & Progression
              </span>
              <span className="text-xs text-slate-400">Recursive CTE DAG</span>
            </div>
            <h1 className="text-2xl font-extrabold text-white tracking-tight">
              Adventure Quest Log
            </h1>
            <p className="text-xs text-slate-400 mt-1">
              Accept quests, solve interactive math & cipher challenges, talk with NPCs for clues, and unlock recursive DAG story paths.
            </p>
          </div>

          <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-2.5 w-full sm:w-auto">
            {/* Demo Controls */}
            <div className="flex items-center gap-2">
              <button
                onClick={() => handleResetProgress(false)}
                disabled={resettingProgress}
                className="py-1.5 px-3 rounded-xl bg-white/5 hover:bg-white/10 text-slate-300 text-xs font-semibold border border-white/10 transition flex items-center gap-1.5 whitespace-nowrap"
                title="Reset completed quests back to available so you can demonstrate solving them live"
              >
                <span>🔄</span>
                <span>{resettingProgress ? 'Resetting...' : 'Reset Quests'}</span>
              </button>
              <button
                onClick={() => handleResetProgress(true)}
                disabled={resettingProgress}
                className="py-1.5 px-3 rounded-xl bg-purple-600/20 hover:bg-purple-600/30 text-purple-300 text-xs font-semibold border border-purple-500/30 transition flex items-center gap-1.5 whitespace-nowrap"
                title="Reset player to Lv. 1 and clear quest logs for a full fresh playthrough demo"
              >
                <span>🌱</span>
                <span>Reset Lv. 1 Demo</span>
              </button>
            </div>

            {/* Search bar */}
            <div className="relative max-w-xs w-full">
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search quests by title..."
                className="w-full glass-input pl-9 pr-3 py-2 rounded-xl text-xs text-white"
              />
              <span className="absolute left-3 top-2.5 text-xs text-slate-400">🔍</span>
            </div>
          </div>
        </div>

        {/* Active Quests Banner */}
        {myQuests.filter((q) => q.status === 'active').length > 0 && (
          <div className="glass-card p-5 rounded-2xl border border-cyan-500/30 bg-cyan-950/20">
            <div className="flex items-center gap-2 mb-3">
              <span className="text-lg">⚔️</span>
              <h3 className="text-xs font-bold text-cyan-300 uppercase tracking-wider">
                Currently In Progress (Action Required)
              </h3>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
              {myQuests
                .filter((q) => q.status === 'active')
                .map((q) => {
                  const fullQuest = quests.find((quest) => quest.quest_id === q.quest_id) || q;
                  return (
                    <div
                      key={q.player_quest_id}
                      className="p-3.5 rounded-xl bg-black/40 border border-cyan-500/30 flex flex-col justify-between"
                    >
                      <div>
                        <div className="flex items-center justify-between text-xs mb-1">
                          <span className="font-bold text-white">
                            {q.title || `Quest #${q.quest_id}`}
                          </span>
                          <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-cyan-500/20 text-cyan-300">
                            ACTIVE
                          </span>
                        </div>
                        <p className="text-[11px] text-slate-400 line-clamp-2">
                          {q.description || 'Proceed with your objectives.'}
                        </p>

                        {fullQuest.challenge_type && (
                          <div className="mt-2 flex items-center gap-1.5 text-[10px] font-semibold text-cyan-300 bg-cyan-500/10 px-2 py-1 rounded border border-cyan-500/20">
                            <span>{getChallengeTypeIcon(fullQuest.challenge_type)}</span>
                            <span>{fullQuest.challenge_type}</span>
                          </div>
                        )}
                      </div>
                      <div className="mt-3 pt-2 border-t border-white/5 flex flex-col gap-2">
                        <div className="flex items-center justify-between text-[11px] text-amber-300">
                          <span>Reward: 🪙 {q.reward_gold || 0} G</span>
                          <span className="text-cyan-400">✨ {q.reward_xp || 0} XP</span>
                        </div>
                        <button
                          onClick={() => openChallengeModal(fullQuest)}
                          className="w-full py-1.5 px-3 rounded-lg bg-gradient-to-r from-emerald-600 to-cyan-600 hover:from-emerald-500 hover:to-cyan-500 text-white font-semibold text-xs transition shadow-md flex items-center justify-center gap-1.5"
                        >
                          <span>Solve Objective & Claim ✨</span>
                        </button>
                      </div>
                    </div>
                  );
                })}
            </div>
          </div>
        )}

        {/* Quest Catalog Grid */}
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-xs font-bold text-slate-300 uppercase tracking-wider">
              Available Quest Catalog ({quests.length})
            </h3>
            <span className="text-xs text-slate-400">
              Your Current Level:{' '}
              <strong className="text-cyan-400">Lv. {user?.level ?? 1}</strong>
            </span>
          </div>

          {loading ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {[1, 2, 3, 4, 5, 6].map((n) => (
                <div
                  key={n}
                  className="glass-card p-5 rounded-2xl border border-white/5 animate-pulse h-52"
                ></div>
              ))}
            </div>
          ) : quests.length === 0 ? (
            <div className="glass-card rounded-2xl p-12 text-center border border-white/10">
              <div className="text-4xl mb-3">📜</div>
              <h3 className="text-base font-bold text-slate-200">No quests found</h3>
              <p className="text-xs text-slate-400 mt-1">Try modifying your search criteria.</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {quests.map((quest) => {
                const status = getQuestStatus(quest.quest_id);
                const isLevelMet = (user?.level || 1) >= quest.min_level;

                return (
                  <div
                    key={quest.quest_id}
                    className="glass-card p-5 rounded-2xl border border-white/10 flex flex-col justify-between transition-all"
                  >
                    <div>
                      {/* Top tags */}
                      <div className="flex items-center justify-between gap-2 mb-2">
                        <span
                          className={`px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider border ${getQuestTypeBadge(
                            quest.quest_type
                          )}`}
                        >
                          {quest.quest_type}
                        </span>

                        <span
                          className={`text-[10px] font-bold uppercase px-2 py-0.5 rounded ${
                            status === 'completed'
                              ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'
                              : status === 'active'
                              ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/30'
                              : 'bg-white/5 text-slate-400'
                          }`}
                        >
                          {status}
                        </span>
                      </div>

                      {/* Title & Description */}
                      <h4 className="text-sm font-bold text-white mb-1.5">{quest.title}</h4>
                      <p className="text-xs text-slate-400 line-clamp-3 leading-relaxed mb-3">
                        {quest.description || 'An intrepid journey awaiting courage.'}
                      </p>

                      {/* Challenge Objective Badge */}
                      {quest.challenge_type && (
                        <div className="flex items-center gap-1.5 text-[11px] font-semibold text-emerald-300 bg-emerald-500/10 px-2.5 py-1 rounded-lg border border-emerald-500/20 mb-3">
                          <span>{getChallengeTypeIcon(quest.challenge_type)}</span>
                          <span>{quest.challenge_type}</span>
                        </div>
                      )}

                      {/* Requirements & Rewards */}
                      <div className="p-3 rounded-xl bg-white/[0.03] border border-white/5 space-y-1.5 text-xs mb-4">
                        <div className="flex items-center justify-between">
                          <span className="text-slate-400">Min Level:</span>
                          <span
                            className={`font-semibold ${
                              isLevelMet ? 'text-cyan-400' : 'text-rose-400 font-bold'
                            }`}
                          >
                            Lv. {quest.min_level}{' '}
                            {!isLevelMet && <span className="text-[10px]">(Locked)</span>}
                          </span>
                        </div>
                        <div className="flex items-center justify-between">
                          <span className="text-slate-400">Rewards:</span>
                          <span className="font-semibold text-amber-300 flex items-center gap-2">
                            <span>🪙 {quest.reward_gold} G</span>
                            <span className="text-cyan-300">✨ {quest.reward_xp} XP</span>
                          </span>
                        </div>
                        {quest.reward_item_name && (
                          <div className="flex items-center justify-between text-violet-300">
                            <span>Reward Item:</span>
                            <span className="font-semibold">{quest.reward_item_name}</span>
                          </div>
                        )}
                      </div>
                    </div>

                    {/* Actions */}
                    <div className="pt-3 border-t border-white/10 flex items-center gap-2">
                      <button
                        onClick={() => handleViewPrereqs(quest)}
                        className="py-2 px-3 rounded-xl bg-white/5 hover:bg-white/10 text-slate-300 text-xs font-semibold border border-white/10 transition"
                      >
                        Prerequisites 🌲
                      </button>

                      <button
                        onClick={() =>
                          status === 'active'
                            ? openChallengeModal(quest)
                            : handleStartQuest(quest.quest_id)
                        }
                        disabled={
                          actionLoading === quest.quest_id ||
                          status === 'completed' ||
                          (status === 'available' && !isLevelMet)
                        }
                        className={`flex-1 py-2 px-3 rounded-xl font-semibold text-xs transition duration-150 flex items-center justify-center gap-1.5 ${
                          status === 'completed'
                            ? 'bg-emerald-600/30 text-emerald-300 cursor-default'
                            : status === 'active'
                            ? 'bg-gradient-to-r from-emerald-600 to-cyan-600 hover:from-emerald-500 hover:to-cyan-500 text-white shadow-md shadow-emerald-600/20 cursor-pointer animate-pulse'
                            : !isLevelMet
                            ? 'bg-white/5 text-slate-500 cursor-not-allowed'
                            : 'bg-emerald-600 hover:bg-emerald-500 text-white shadow-md shadow-emerald-600/20'
                        }`}
                      >
                        {actionLoading === quest.quest_id ? (
                          'Accepting...'
                        ) : status === 'completed' ? (
                          '✓ Completed'
                        ) : status === 'active' ? (
                          'Solve Objective ⚔️'
                        ) : !isLevelMet ? (
                          `Requires Lv. ${quest.min_level}`
                        ) : (
                          'Accept Quest ⚡'
                        )}
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Interactive Mission Objective Challenge Modal */}
        {activeChallengeQuest && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md animate-in fade-in">
            <div className="glass-card max-w-lg w-full p-6 rounded-2xl border border-cyan-500/40 shadow-2xl relative">
              {/* Modal Header */}
              <div className="flex items-center justify-between mb-4 pb-3 border-b border-white/10">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-xl bg-cyan-500/20 border border-cyan-500/30 flex items-center justify-center text-xl">
                    {getChallengeTypeIcon(activeChallengeQuest.challenge_type)}
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded bg-cyan-500/20 text-cyan-300 border border-cyan-500/30">
                        {activeChallengeQuest.challenge_type || 'Mission Challenge'}
                      </span>
                      <span className="text-[11px] text-slate-400">
                        Min Lv. {activeChallengeQuest.min_level || 1}
                      </span>
                    </div>
                    <h3 className="text-base font-bold text-white mt-0.5">
                      {activeChallengeQuest.title}
                    </h3>
                  </div>
                </div>
                <button
                  onClick={() => setActiveChallengeQuest(null)}
                  className="text-slate-400 hover:text-white text-sm p-1 rounded-lg hover:bg-white/10 transition"
                >
                  ✕
                </button>
              </div>

              {/* Challenge Briefing Box */}
              <div className="space-y-4">
                <div className="p-4 rounded-xl bg-black/50 border border-white/10 space-y-2">
                  <div className="flex items-center justify-between text-[11px] font-mono text-cyan-400 uppercase tracking-wider">
                    <span>📜 Objective Briefing</span>
                    <span className="text-amber-300">
                      🪙 {activeChallengeQuest.reward_gold || 0} G &nbsp;|&nbsp; ✨{' '}
                      {activeChallengeQuest.reward_xp || 0} XP
                    </span>
                  </div>
                  <p className="text-xs text-slate-200 leading-relaxed font-medium">
                    {activeChallengeQuest.challenge_question ||
                      activeChallengeQuest.description ||
                      'Solve the objective puzzle to complete this quest.'}
                  </p>
                </div>

                {/* NPC Dialogue Tip for CTF/Cipher quests */}
                {activeChallengeQuest.challenge_type?.toLowerCase().includes('npc') && (
                  <div className="p-3 rounded-xl bg-indigo-950/40 border border-indigo-500/30 flex items-start gap-2.5 text-xs text-indigo-200">
                    <span className="text-base">💬</span>
                    <div>
                      <strong className="text-indigo-300">NPC Dialogue Intel:</strong> Speak with{' '}
                      <strong>Elara Ravenshade</strong> in the Whispering Crow Inn (ask her about{' '}
                      <em>&quot;smuggler secrets&quot;</em> or <em>&quot;dock cipher&quot;</em>) to extract the secret codeword!
                      <div className="mt-1">
                        <Link
                          href="/chat"
                          target="_blank"
                          className="text-cyan-400 hover:text-cyan-300 underline font-semibold text-[11px]"
                        >
                          Open NPC Chat Chamber ↗
                        </Link>
                      </div>
                    </div>
                  </div>
                )}

                {/* Hint Toggle */}
                {activeChallengeQuest.challenge_hint && (
                  <div>
                    <button
                      type="button"
                      onClick={() => setShowHint(!showHint)}
                      className="text-xs text-amber-400/90 hover:text-amber-300 flex items-center gap-1.5 transition font-medium"
                    >
                      <span>💡</span>
                      <span>{showHint ? 'Hide Hint' : 'Need a Clue? / Reveal Hint'}</span>
                    </button>
                    {showHint && (
                      <div className="mt-2 p-3 rounded-xl bg-amber-950/30 border border-amber-500/20 text-xs text-amber-200 animate-in fade-in">
                        <strong>Clue:</strong> {activeChallengeQuest.challenge_hint}
                      </div>
                    )}
                  </div>
                )}

                {/* Answer Input Field */}
                <div className="space-y-2 pt-1">
                  <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider">
                    Enter Solution / Codeword / Flag:
                  </label>
                  <input
                    type="text"
                    value={solutionInput}
                    onChange={(e) => setSolutionInput(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') handleVerifySolution();
                    }}
                    placeholder="e.g. 33, SHADOW_CARGO_77, echo..."
                    className="w-full glass-input px-3.5 py-2.5 rounded-xl text-sm text-white border border-cyan-500/30 focus:border-cyan-400 focus:outline-none"
                    autoFocus
                  />
                </div>

                {/* Error Banner */}
                {challengeError && (
                  <div className="p-3 rounded-xl bg-rose-950/50 border border-rose-500/40 text-xs text-rose-200 flex items-start gap-2 animate-in fade-in">
                    <span className="text-sm">❌</span>
                    <div>
                      <strong>Verification Failed:</strong> {challengeError}
                    </div>
                  </div>
                )}

                {/* Modal Actions */}
                <div className="pt-3 border-t border-white/10 flex items-center justify-end gap-2.5">
                  <button
                    type="button"
                    onClick={() => setActiveChallengeQuest(null)}
                    className="px-4 py-2 rounded-xl bg-white/5 hover:bg-white/10 text-slate-300 text-xs font-semibold border border-white/10 transition"
                  >
                    Cancel
                  </button>
                  <button
                    type="button"
                    onClick={handleVerifySolution}
                    disabled={submittingSolution}
                    className="px-5 py-2 rounded-xl bg-gradient-to-r from-emerald-600 to-cyan-600 hover:from-emerald-500 hover:to-cyan-500 text-white text-xs font-semibold shadow-lg shadow-cyan-600/20 transition flex items-center gap-1.5"
                  >
                    {submittingSolution ? 'Verifying Objective...' : 'Verify Solution & Claim ✨'}
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Prerequisites DAG Tree Modal */}
        {selectedQuestPrereqs && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-sm animate-in fade-in">
            <div className="glass-card max-w-lg w-full p-6 rounded-2xl border border-emerald-500/30 shadow-2xl relative">
              <div className="flex items-center justify-between mb-4 pb-3 border-b border-white/10">
                <div>
                  <h3 className="text-sm font-bold text-white flex items-center gap-2">
                    <span>🌲</span>
                    <span>Prerequisite Dependency Tree</span>
                  </h3>
                  <p className="text-[11px] text-slate-400 mt-0.5">
                    For:{' '}
                    <strong className="text-emerald-300">
                      {selectedQuestPrereqs.quest.title}
                    </strong>
                  </p>
                </div>
                <button
                  onClick={() => setSelectedQuestPrereqs(null)}
                  className="text-slate-400 hover:text-white text-xs"
                >
                  ✕
                </button>
              </div>

              {loadingPrereqs ? (
                <div className="py-8 text-center text-xs text-slate-400">
                  Resolving recursive CTE DAG graph...
                </div>
              ) : selectedQuestPrereqs.chain.length === 0 ? (
                <div className="p-4 rounded-xl bg-emerald-950/30 border border-emerald-500/20 text-center text-xs text-emerald-300">
                  ✨ No prerequisite quests required! You can undertake this quest directly once
                  level requirements are met.
                </div>
              ) : (
                <div className="space-y-2 max-h-64 overflow-y-auto pr-1">
                  <p className="text-xs text-slate-400 mb-2 font-medium">
                    The following quests must be completed first in sequence:
                  </p>
                  {selectedQuestPrereqs.chain.map((step, idx) => (
                    <div
                      key={idx}
                      className="p-3 rounded-xl bg-white/[0.04] border border-white/10 flex items-center justify-between text-xs"
                    >
                      <div className="flex items-center gap-2.5">
                        <span className="w-5 h-5 rounded-full bg-emerald-500/20 text-emerald-300 flex items-center justify-center font-mono font-bold text-[10px]">
                          {idx + 1}
                        </span>
                        <div>
                          <span className="font-bold text-white">
                            {step.required_quest_title || `Quest ID #${step.required_quest_id}`}
                          </span>
                          {step.depth !== undefined && (
                            <span className="text-[10px] text-slate-400 ml-2 font-mono">
                              (Level {step.depth} DAG node)
                            </span>
                          )}
                        </div>
                      </div>
                      <span className="text-[10px] px-2 py-0.5 rounded bg-cyan-500/10 text-cyan-300">
                        Required
                      </span>
                    </div>
                  ))}
                </div>
              )}

              <div className="mt-5 pt-3 border-t border-white/10 text-right">
                <button
                  onClick={() => setSelectedQuestPrereqs(null)}
                  className="px-4 py-2 rounded-xl bg-white/10 hover:bg-white/20 text-white text-xs font-semibold"
                >
                  Dismiss
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </ProtectedRoute>
  );
}
