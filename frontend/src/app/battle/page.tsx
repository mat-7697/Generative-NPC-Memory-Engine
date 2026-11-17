'use client';

import React, { useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import ProtectedRoute from '@/components/ProtectedRoute';
import { useAuth } from '@/lib/auth';
import { useToast } from '@/lib/toast';
import { api, BattleActionResult, BattleState, Monster } from '@/lib/api';

function Bar({ value, max, color }: { value: number; max: number; color: string }) {
  const pct = max > 0 ? Math.max(0, Math.min(100, (value / max) * 100)) : 0;
  return (
    <div className="h-2.5 w-full rounded-full bg-white/5 overflow-hidden">
      <div className={`h-full rounded-full transition-all duration-300 ${color}`} style={{ width: `${pct}%` }} />
    </div>
  );
}

function Stat({ label, value, tone }: { label: string; value: React.ReactNode; tone: string }) {
  return (
    <div className="rounded-xl bg-white/[0.03] border border-white/10 px-3 py-2.5">
      <div className="text-[11px] uppercase tracking-wider text-slate-400">{label}</div>
      <div className={`text-lg font-bold ${tone}`}>{value}</div>
    </div>
  );
}

export default function BattlePage() {
  const { refreshUser } = useAuth();
  const { success, error: toastError } = useToast();

  const [state, setState] = useState<BattleState | null>(null);
  const [log, setLog] = useState<string[]>([]);
  const [lastOutcome, setLastOutcome] = useState<BattleActionResult['outcome'] | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      setState(await api.battle.getState());
    } catch (err: any) {
      toastError(err.message || 'Failed to load the campaign.');
    }
  }, [toastError]);

  useEffect(() => {
    load();
  }, [load]);

  const run = async (action: () => Promise<BattleActionResult>, fresh = false) => {
    setBusy(true);
    try {
      const res = await action();
      setState(res.state);
      setLog((prev) => (fresh ? res.log : [...prev, ...res.log]));
      setLastOutcome(res.outcome);
      if (res.outcome === 'won') success('Victory!');
      if (res.outcome === 'rested') success(res.log[0]);
      if (res.outcome !== 'ongoing') await refreshUser();
    } catch (err: any) {
      toastError(err.message || 'Action failed.');
    } finally {
      setBusy(false);
    }
  };

  if (!state) {
    return (
      <ProtectedRoute>
        <div className="glass-card rounded-2xl p-10 text-center text-sm text-slate-400">Loading campaign...</div>
      </ProtectedRoute>
    );
  }

  const { player, monsters, active_battle: battle } = state;
  const totalRegions = monsters.length;

  return (
    <ProtectedRoute>
      <div className="space-y-6 pb-12">
        {/* Story header */}
        <section className="glass-card rounded-2xl p-6 flex flex-col lg:flex-row lg:items-center gap-6">
          <div className="flex-1 min-w-0">
            <span className="text-xs font-mono uppercase tracking-widest text-rose-300 bg-rose-500/10 px-2 py-0.5 rounded border border-rose-500/30">
              Main Campaign
            </span>
            <h1 className="mt-2 text-2xl font-extrabold text-white tracking-tight">Seal the Void Rift</h1>
            <p className="mt-1 text-sm text-slate-400 max-w-2xl">
              A rift has torn open above the Mount of Ash and monsters are pouring into the realm. Hunt them region by
              region, buy better gear with the gold you earn, and slay the Ashen Wyrm to close the rift for good.
            </p>
          </div>
          <div className="w-full lg:w-72 shrink-0 space-y-2">
            <div className="flex justify-between text-xs text-slate-300">
              <span>Regions conquered</span>
              <span className="font-semibold text-white">
                {state.regions_cleared} / {totalRegions}
              </span>
            </div>
            <Bar value={state.regions_cleared} max={totalRegions} color="bg-gradient-to-r from-violet-500 to-rose-500" />
            {state.rift_sealed && (
              <div className="text-xs font-semibold text-emerald-300">The rift is sealed. You saved the realm!</div>
            )}
          </div>
        </section>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 items-start">
          {/* Hero panel */}
          <aside className="glass-card rounded-2xl p-5 space-y-5 lg:sticky lg:top-24">
            <div>
              <div className="flex items-baseline justify-between">
                <h2 className="text-sm font-bold uppercase tracking-wider text-slate-200">Your Hero</h2>
                <span className="text-xs text-cyan-300 font-semibold">Level {player.level}</span>
              </div>
              <div className="mt-3 flex justify-between text-xs text-slate-300">
                <span>Health</span>
                <span className="font-semibold text-white">
                  {player.hp} / {player.max_hp}
                </span>
              </div>
              <div className="mt-1.5">
                <Bar
                  value={player.hp}
                  max={player.max_hp}
                  color={player.hp / player.max_hp > 0.35 ? 'bg-emerald-500' : 'bg-rose-500'}
                />
              </div>
            </div>

            <div className="grid grid-cols-3 gap-2">
              <Stat label="Attack" value={player.attack} tone="text-rose-300" />
              <Stat label="Defense" value={player.defense} tone="text-sky-300" />
              <Stat label="Gold" value={player.gold} tone="text-amber-300" />
            </div>

            <div className="space-y-2">
              <h3 className="text-[11px] uppercase tracking-wider text-slate-400">Equipped Gear</h3>
              {[
                { slot: 'Weapon', item: player.weapon, bonus: player.weapon && `+${player.weapon.attack_power} ATK` },
                { slot: 'Armor', item: player.armor, bonus: player.armor && `+${player.armor.defense_power} DEF` },
              ].map(({ slot, item, bonus }) => (
                <div
                  key={slot}
                  className="flex items-center justify-between rounded-xl bg-white/[0.03] border border-white/10 px-3 py-2.5 text-sm"
                >
                  <div className="min-w-0">
                    <div className="text-[11px] text-slate-500">{slot}</div>
                    <div className={`truncate ${item ? 'text-slate-100' : 'text-slate-500 italic'}`}>
                      {item ? item.name : 'Nothing equipped'}
                    </div>
                  </div>
                  {bonus && <span className="text-xs font-semibold text-emerald-300 shrink-0 ml-2">{bonus}</span>}
                </div>
              ))}
              <Link href="/inventory" className="block text-center text-xs text-violet-300 hover:text-violet-200 pt-1">
                Change gear or buy potions in the Market →
              </Link>
            </div>

            <button
              onClick={() => run(api.battle.rest, true)}
              disabled={busy || !!battle || player.hp >= player.max_hp || player.gold < state.rest_cost}
              className="w-full py-2.5 rounded-xl text-sm font-semibold bg-emerald-600/80 hover:bg-emerald-500 text-white transition disabled:opacity-40 disabled:cursor-not-allowed"
            >
              Rest at the Inn · {state.rest_cost} gold
            </button>
          </aside>

          {/* Main area */}
          <section className="lg:col-span-2 space-y-6">
            {battle ? (
              <div className="glass-card rounded-2xl p-6 space-y-5">
                <div className="flex items-start gap-4">
                  <div className="w-16 h-16 shrink-0 rounded-2xl bg-white/5 border border-white/10 flex items-center justify-center text-4xl">
                    {battle.monster.icon}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="text-xs text-slate-400">{battle.monster.region}</div>
                    <h2 className="text-xl font-bold text-white">{battle.monster.name}</h2>
                    <div className="mt-2 flex justify-between text-xs text-slate-300">
                      <span>
                        ATK {battle.monster.attack} · DEF {battle.monster.defense}
                      </span>
                      <span className="font-semibold text-white">
                        {battle.monster_hp} / {battle.monster.max_hp} HP
                      </span>
                    </div>
                    <div className="mt-1.5">
                      <Bar value={battle.monster_hp} max={battle.monster.max_hp} color="bg-rose-500" />
                    </div>
                  </div>
                </div>

                {battle.empowered && (
                  <div className="text-xs rounded-lg bg-violet-500/10 border border-violet-500/30 text-violet-200 px-3 py-2">
                    Empowered: your next attack deals double damage.
                  </div>
                )}

                <div className="flex flex-wrap gap-2">
                  <button
                    onClick={() => run(api.battle.attack)}
                    disabled={busy}
                    className="px-5 py-2.5 rounded-xl text-sm font-semibold bg-rose-600 hover:bg-rose-500 text-white transition disabled:opacity-50"
                  >
                    ⚔️ Attack
                  </button>
                  {state.potions.map((p) => (
                    <button
                      key={p.item_id}
                      onClick={() => run(() => api.battle.useItem(p.item_id))}
                      disabled={busy}
                      className="px-4 py-2.5 rounded-xl text-sm font-medium bg-white/5 hover:bg-white/10 border border-white/10 text-slate-100 transition disabled:opacity-50"
                    >
                      🧪 {p.name} ×{p.quantity}
                    </button>
                  ))}
                  <button
                    onClick={() => run(api.battle.flee)}
                    disabled={busy}
                    className="ml-auto px-4 py-2.5 rounded-xl text-sm font-medium text-slate-300 hover:text-white hover:bg-white/5 border border-white/10 transition disabled:opacity-50"
                  >
                    Flee
                  </button>
                </div>
                {state.potions.length === 0 && (
                  <p className="text-xs text-slate-500">No potions in your vault. Buy some in the Market before tough fights.</p>
                )}

                <BattleLog log={log} />
              </div>
            ) : (
              <>
                {log.length > 0 && (
                  <div
                    className={`glass-card rounded-2xl p-5 border ${
                      lastOutcome === 'won'
                        ? 'border-emerald-500/40'
                        : lastOutcome === 'lost'
                          ? 'border-rose-500/40'
                          : 'border-white/10'
                    }`}
                  >
                    <div className="flex items-center justify-between mb-3">
                      <h2 className="text-sm font-bold text-white">
                        {lastOutcome === 'won'
                          ? 'Victory'
                          : lastOutcome === 'lost'
                            ? 'Defeated'
                            : lastOutcome === 'fled'
                              ? 'Escaped'
                              : 'Rested'}
                      </h2>
                      <button onClick={() => setLog([])} className="text-xs text-slate-400 hover:text-white">
                        Dismiss
                      </button>
                    </div>
                    <BattleLog log={log} />
                  </div>
                )}

                <div>
                  <h2 className="text-sm font-bold uppercase tracking-wider text-slate-200 mb-3">Hunting Grounds</h2>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {monsters.map((m) => (
                      <MonsterCard
                        key={m.monster_id}
                        monster={m}
                        disabled={busy}
                        onFight={() => run(() => api.battle.start(m.monster_id), true)}
                      />
                    ))}
                  </div>
                </div>
              </>
            )}

            <div className="glass-card rounded-2xl p-5 text-sm text-slate-400 space-y-1.5">
              <h3 className="text-xs font-bold uppercase tracking-wider text-slate-200 mb-2">How it works</h3>
              <p>• Equip a weapon for more attack and armor for more defense (Market → My Vault).</p>
              <p>• Potions heal you in and out of battle. A Mana Draught also doubles your next hit.</p>
              <p>• Monsters give gold, XP and loot. Sell loot like Wolf Pelts in the Market.</p>
              <p>• The Crypt Key (quest reward) and Heart of the Void (Champion drop) unlock the last regions.</p>
              <p>• Losing a fight costs 10% of your gold. Rest at the inn to heal fully.</p>
            </div>
          </section>
        </div>
      </div>
    </ProtectedRoute>
  );
}

function BattleLog({ log }: { log: string[] }) {
  return (
    <div className="rounded-xl bg-black/30 border border-white/5 p-4 max-h-56 overflow-y-auto space-y-1.5 text-sm">
      {log.map((line, i) => (
        <p key={i} className={i === log.length - 1 ? 'text-slate-100' : 'text-slate-400'}>
          {line}
        </p>
      ))}
    </div>
  );
}

function MonsterCard({ monster: m, onFight, disabled }: { monster: Monster; onFight: () => void; disabled: boolean }) {
  return (
    <div
      className={`glass-card rounded-2xl p-5 flex flex-col gap-4 ${m.is_boss ? 'border-rose-500/30' : ''} ${
        m.unlocked ? '' : 'opacity-60'
      }`}
    >
      <div className="flex items-start gap-3">
        <div className="w-12 h-12 shrink-0 rounded-xl bg-white/5 border border-white/10 flex items-center justify-center text-2xl">
          {m.unlocked ? m.icon : '🔒'}
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <h3 className="font-bold text-white truncate">{m.name}</h3>
            {m.is_boss && (
              <span className="text-[10px] font-bold uppercase px-1.5 py-0.5 rounded bg-rose-500/20 text-rose-300 border border-rose-500/30">
                Boss
              </span>
            )}
          </div>
          <div className="text-xs text-slate-400">
            {m.region} · Lv. {m.min_level}+
          </div>
        </div>
        {m.kills > 0 && <span className="text-xs text-emerald-300 shrink-0">✓ {m.kills}</span>}
      </div>

      <p className="text-sm text-slate-400 flex-1">{m.description}</p>

      <div className="grid grid-cols-3 gap-2 text-center text-xs">
        <div className="rounded-lg bg-white/[0.03] py-1.5">
          <div className="text-slate-500">HP</div>
          <div className="font-semibold text-slate-100">{m.max_hp}</div>
        </div>
        <div className="rounded-lg bg-white/[0.03] py-1.5">
          <div className="text-slate-500">ATK</div>
          <div className="font-semibold text-rose-300">{m.attack}</div>
        </div>
        <div className="rounded-lg bg-white/[0.03] py-1.5">
          <div className="text-slate-500">DEF</div>
          <div className="font-semibold text-sky-300">{m.defense}</div>
        </div>
      </div>

      <div className="flex items-center justify-between text-xs text-slate-300">
        <span>
          🪙 {m.gold_reward} · ✨ {m.xp_reward} XP
        </span>
        {m.loot_item_name && (
          <span className="text-slate-400 truncate ml-2">
            Loot: {m.loot_item_name} ({Math.round(m.loot_chance * 100)}%)
          </span>
        )}
      </div>

      {m.unlocked ? (
        <button
          onClick={onFight}
          disabled={disabled}
          className="w-full py-2.5 rounded-xl text-sm font-semibold bg-violet-600 hover:bg-violet-500 text-white transition disabled:opacity-50"
        >
          Fight
        </button>
      ) : (
        <div className="w-full py-2.5 rounded-xl text-sm text-center text-slate-400 bg-white/[0.03] border border-white/10">
          🔒 {m.lock_reason}
        </div>
      )}
    </div>
  );
}
