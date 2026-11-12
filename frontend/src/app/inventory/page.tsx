'use client';

import React, { useState, useEffect, useCallback } from 'react';
import ProtectedRoute from '@/components/ProtectedRoute';
import { useAuth } from '@/lib/auth';
import { useToast } from '@/lib/toast';
import {
  api,
  ItemResponse,
  InventoryItem,
  TransactionResponse,
  ItemRarity,
} from '@/lib/api';

export default function InventoryPage() {
  const { user, refreshUser } = useAuth();
  const { success, error: toastError } = useToast();

  const [activeTab, setActiveTab] = useState<'inventory' | 'shop'>('shop');
  const [shopItems, setShopItems] = useState<ItemResponse[]>([]);
  const [myInventory, setMyInventory] = useState<InventoryItem[]>([]);
  const [transactions, setTransactions] = useState<TransactionResponse[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  // Transfer Modal State
  const [transferModalItem, setTransferModalItem] = useState<InventoryItem | null>(null);
  const [transferTargetId, setTransferTargetId] = useState('');
  const [transferQty, setTransferQty] = useState(1);

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      const [itemsRes, invRes, txRes] = await Promise.allSettled([
        api.inventory.getItems(searchQuery),
        api.inventory.getMyInventory(),
        api.inventory.getTransactions(),
      ]);

      if (itemsRes.status === 'fulfilled') setShopItems(itemsRes.value || []);
      if (invRes.status === 'fulfilled') setMyInventory(invRes.value || []);
      if (txRes.status === 'fulfilled') setTransactions(txRes.value || []);
    } catch (err: any) {
      toastError(err.message || 'Failed to sync inventory and shop catalog.');
    } finally {
      setLoading(false);
    }
  }, [searchQuery, toastError]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // Handle Buy Item
  const handleBuy = async (item: ItemResponse, quantity: number = 1) => {
    if ((user?.gold || 0) < item.base_price * quantity) {
      toastError(`Insufficient gold! You need ${item.base_price * quantity} G.`);
      return;
    }

    setActionLoading(`buy-${item.item_id}`);
    try {
      await api.inventory.buy({ item_id: item.item_id, quantity });
      success(`Acquired ${quantity}x ${item.name}!`);
      await refreshUser();
      await loadData();
    } catch (err: any) {
      toastError(err.message || 'Purchase failed.');
    } finally {
      setActionLoading(null);
    }
  };

  // Handle Sell Item
  const handleSell = async (invItem: InventoryItem, quantity: number = 1) => {
    setActionLoading(`sell-${invItem.item_id}`);
    try {
      await api.inventory.sell({ item_id: invItem.item_id, quantity });
      success(`Sold ${quantity}x ${invItem.name || 'item'} for gold!`);
      await refreshUser();
      await loadData();
    } catch (err: any) {
      toastError(err.message || 'Sale failed.');
    } finally {
      setActionLoading(null);
    }
  };

  // Handle Use / Equip Item
  const handleUse = async (invItem: InventoryItem) => {
    setActionLoading(`use-${invItem.item_id}`);
    try {
      const res = await api.inventory.use(invItem.item_id);
      success(res.message);
      await refreshUser();
      await loadData();
    } catch (err: any) {
      toastError(err.message || 'Failed to use item.');
    } finally {
      setActionLoading(null);
    }
  };

  // Handle Transfer Item
  const handleTransferSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!transferModalItem || !transferTargetId) return;

    const targetIdNum = parseInt(transferTargetId, 10);
    if (isNaN(targetIdNum) || targetIdNum === user?.player_id) {
      toastError('Please enter a valid destination Player ID.');
      return;
    }

    setActionLoading(`transfer-${transferModalItem.item_id}`);
    try {
      await api.inventory.transfer({
        to_player_id: targetIdNum,
        item_id: transferModalItem.item_id,
        quantity: transferQty,
      });
      success(`Successfully transferred ${transferQty}x to Player #${targetIdNum}!`);
      setTransferModalItem(null);
      await loadData();
    } catch (err: any) {
      toastError(err.message || 'Transfer failed.');
    } finally {
      setActionLoading(null);
    }
  };

  // Rarity color helpers
  const getRarityBadge = (rarity: ItemRarity = 'common') => {
    switch (rarity) {
      case 'uncommon':
        return 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40';
      case 'rare':
        return 'bg-blue-500/20 text-blue-300 border-blue-500/40';
      case 'epic':
        return 'bg-purple-500/20 text-purple-300 border-purple-500/40';
      case 'legendary':
        return 'bg-amber-500/20 text-amber-300 border-amber-500/40';
      default:
        return 'bg-slate-500/20 text-slate-300 border-slate-500/40';
    }
  };

  const getRarityBorder = (rarity: ItemRarity = 'common') => {
    switch (rarity) {
      case 'uncommon':
        return 'border-emerald-500/40 hover:border-emerald-500/80 shadow-emerald-950/30';
      case 'rare':
        return 'border-blue-500/40 hover:border-blue-500/80 shadow-blue-950/30';
      case 'epic':
        return 'border-purple-500/40 hover:border-purple-500/80 shadow-purple-950/30';
      case 'legendary':
        return 'border-amber-500/40 hover:border-amber-500/80 shadow-amber-950/30';
      default:
        return 'border-white/10 hover:border-white/30';
    }
  };

  const getItemIcon = (type: string = 'misc') => {
    switch (type) {
      case 'weapon':
        return '⚔️';
      case 'armor':
        return '🛡️';
      case 'potion':
        return '🧪';
      case 'quest_item':
        return '📜';
      default:
        return '💎';
    }
  };

  return (
    <ProtectedRoute>
      <div className="space-y-6 pb-12">
        {/* Header with Economy Banner */}
        <div className="glass-card rounded-2xl p-6 border border-amber-500/20 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <span className="text-xs font-mono uppercase tracking-widest text-amber-400 bg-amber-500/10 px-2 py-0.5 rounded border border-amber-500/30">
                Transactional RPG Vault
              </span>
              <span className="text-xs text-slate-400">ACID Atomic Ledger</span>
            </div>
            <h1 className="text-2xl font-extrabold text-white tracking-tight">
              Marketplace & Personal Vault
            </h1>
            <p className="text-xs text-slate-400 mt-1">
              Trade gear, enforce non-negative check constraints, and transfer items to peer players.
            </p>
          </div>

          <div className="flex items-center gap-3">
            <div className="px-5 py-3 rounded-2xl bg-amber-500/10 border border-amber-500/30 text-amber-300 flex items-center gap-3 shadow-lg shadow-amber-500/10">
              <span className="text-2xl">🪙</span>
              <div>
                <div className="text-[10px] text-amber-400/80 font-bold uppercase tracking-wider">
                  Available Gold
                </div>
                <div className="text-xl font-black">
                  {user?.gold?.toLocaleString() ?? 0}{' '}
                  <span className="text-xs font-normal">G</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Tab Navigation and Search Bar */}
        <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-4">
          {/* Tabs */}
          <div className="flex items-center p-1 rounded-xl bg-black/40 border border-white/10 w-fit">
            <button
              onClick={() => setActiveTab('shop')}
              className={`px-5 py-2 rounded-lg text-xs font-bold transition flex items-center gap-2 ${
                activeTab === 'shop'
                  ? 'bg-violet-600 text-white shadow-md shadow-violet-600/30'
                  : 'text-slate-400 hover:text-white'
              }`}
            >
              <span>🏪</span>
              <span>Merchant Shop ({shopItems.length})</span>
            </button>
            <button
              onClick={() => setActiveTab('inventory')}
              className={`px-5 py-2 rounded-lg text-xs font-bold transition flex items-center gap-2 ${
                activeTab === 'inventory'
                  ? 'bg-cyan-600 text-white shadow-md shadow-cyan-600/30'
                  : 'text-slate-400 hover:text-white'
              }`}
            >
              <span>🎒</span>
              <span>My Vault ({myInventory.length})</span>
            </button>
          </div>

          {/* Full-Text Search Input */}
          <div className="relative max-w-sm w-full">
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search catalog by name or description..."
              className="w-full glass-input pl-9 pr-4 py-2 rounded-xl text-xs text-white"
            />
            <span className="absolute left-3 top-2.5 text-xs text-slate-400">🔍</span>
            {searchQuery && (
              <button
                onClick={() => setSearchQuery('')}
                className="absolute right-3 top-2.5 text-xs text-slate-400 hover:text-white"
              >
                ✕
              </button>
            )}
          </div>
        </div>

        {/* SHOP TAB VIEW */}
        {activeTab === 'shop' && (
          <div>
            {loading ? (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
                {[1, 2, 3, 4, 5, 6].map((n) => (
                  <div
                    key={n}
                    className="glass-card p-5 rounded-2xl border border-white/5 animate-pulse h-48"
                  ></div>
                ))}
              </div>
            ) : shopItems.length === 0 ? (
              <div className="glass-card rounded-2xl p-12 text-center border border-white/10">
                <div className="text-4xl mb-3">📦</div>
                <h3 className="text-base font-bold text-slate-200">No items available</h3>
                <p className="text-xs text-slate-400 mt-1">
                  Try clearing your search query or check back later.
                </p>
              </div>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
                {shopItems.map((item) => {
                  const canAfford = (user?.gold || 0) >= item.base_price;
                  const isInfinite = item.stock === -1;
                  const inStock = isInfinite || item.stock > 0;

                  return (
                    <div
                      key={item.item_id}
                      className={`glass-card p-5 rounded-2xl border transition-all flex flex-col justify-between ${getRarityBorder(
                        item.rarity
                      )}`}
                    >
                      <div>
                        {/* Header: Icon, Type, Rarity */}
                        <div className="flex items-start justify-between gap-2 mb-3">
                          <div className="w-10 h-10 rounded-xl bg-white/5 border border-white/10 flex items-center justify-center text-xl">
                            {getItemIcon(item.item_type)}
                          </div>
                          <span
                            className={`px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider border ${getRarityBadge(
                              item.rarity
                            )}`}
                          >
                            {item.rarity}
                          </span>
                        </div>

                        {/* Title & Description */}
                        <h3 className="text-sm font-bold text-white mb-1">{item.name}</h3>
                        <p className="text-xs text-slate-400 line-clamp-2 leading-relaxed mb-4">
                          {item.description || 'Standard fantasy adventure artifact.'}
                        </p>
                      </div>

                      {/* Footer: Price, Stock & Buy Action */}
                      <div className="pt-3 border-t border-white/10">
                        <div className="flex items-center justify-between text-xs mb-3">
                          <div className="flex items-center gap-1 font-bold text-amber-300">
                            <span>🪙</span>
                            <span>{item.base_price} G</span>
                          </div>
                          <div className="text-[11px] text-slate-400">
                            {isInfinite ? (
                              <span className="text-cyan-400">∞ Infinite</span>
                            ) : (
                              <span>Stock: {item.stock}</span>
                            )}
                          </div>
                        </div>

                        <button
                          onClick={() => handleBuy(item, 1)}
                          disabled={
                            !inStock || !canAfford || actionLoading === `buy-${item.item_id}`
                          }
                          className="w-full py-2 px-3 rounded-xl bg-violet-600 hover:bg-violet-500 text-white font-semibold text-xs transition duration-150 disabled:opacity-40 flex items-center justify-center gap-1.5 shadow-md shadow-violet-600/20"
                        >
                          {actionLoading === `buy-${item.item_id}` ? (
                            <div className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
                          ) : !canAfford ? (
                            'Insufficient Gold'
                          ) : !inStock ? (
                            'Out of Stock'
                          ) : (
                            <>
                              <span>Purchase (1x)</span>
                              <span>🛒</span>
                            </>
                          )}
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}

        {/* MY INVENTORY TAB VIEW */}
        {activeTab === 'inventory' && (
          <div>
            {myInventory.length === 0 ? (
              <div className="glass-card rounded-2xl p-12 text-center border border-white/10">
                <div className="text-4xl mb-3">🎒</div>
                <h3 className="text-base font-bold text-slate-200">Your vault is empty</h3>
                <p className="text-xs text-slate-400 mt-1 mb-4">
                  Visit the Merchant Shop tab to acquire weapons, armor, and potions!
                </p>
                <button
                  onClick={() => setActiveTab('shop')}
                  className="px-4 py-2 bg-violet-600 hover:bg-violet-500 text-white text-xs font-semibold rounded-xl"
                >
                  Browse Shop Catalog
                </button>
              </div>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
                {myInventory.map((item) => (
                  <div
                    key={item.inventory_id}
                    className={`glass-card p-5 rounded-2xl border transition-all flex flex-col justify-between ${getRarityBorder(
                      item.rarity || 'common'
                    )}`}
                  >
                    <div>
                      {/* Top Bar */}
                      <div className="flex items-start justify-between gap-2 mb-3">
                        <div className="w-10 h-10 rounded-xl bg-white/5 border border-white/10 flex items-center justify-center text-xl">
                          {getItemIcon(item.item_type || 'misc')}
                        </div>
                        <div className="flex items-center gap-1.5">
                          {item.is_equipped && (
                            <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-amber-500/20 text-amber-300 border border-amber-500/40 animate-pulse">
                              ✨ EQUIPPED
                            </span>
                          )}
                          <span className="px-2 py-0.5 rounded-full text-[11px] font-bold bg-cyan-500/20 text-cyan-300 border border-cyan-500/40">
                            {item.quantity}x Owned
                          </span>
                        </div>
                      </div>

                      {/* Item Info */}
                      <h3 className="text-sm font-bold text-white mb-1">
                        {item.name || `Item #${item.item_id}`}
                      </h3>
                      <p className="text-xs text-slate-400 line-clamp-2 leading-relaxed mb-4">
                        {item.description || 'Equipped in player inventory.'}
                      </p>
                    </div>

                    {/* Actions: Use/Equip, Sell & Transfer */}
                    <div className="pt-3 border-t border-white/10 space-y-2">
                      {/* Primary Use / Equip Action */}
                      <button
                        onClick={() => handleUse(item)}
                        disabled={actionLoading === `use-${item.item_id}`}
                        className={`w-full py-1.5 px-3 rounded-xl text-xs font-bold transition flex items-center justify-center gap-1.5 ${
                          item.item_type === 'potion'
                            ? 'bg-purple-600/30 hover:bg-purple-600/40 text-purple-200 border border-purple-500/40 shadow-sm'
                            : item.is_equipped
                            ? 'bg-amber-500/20 hover:bg-amber-500/30 text-amber-300 border border-amber-500/40'
                            : 'bg-indigo-600/20 hover:bg-indigo-600/30 text-indigo-300 border border-indigo-500/40'
                        }`}
                      >
                        {actionLoading === `use-${item.item_id}` ? (
                          'Processing...'
                        ) : item.item_type === 'potion' ? (
                          '🧪 Drink / Consume Potion'
                        ) : item.is_equipped ? (
                          '🛡️ Unequip Gear'
                        ) : (
                          '⚔️ Equip to Active Slot'
                        )}
                      </button>

                      <div className="flex items-center justify-between text-xs text-slate-400 pt-0.5">
                        <span>Sell Value:</span>
                        <span className="text-amber-300 font-bold">
                          🪙 {Math.floor((item.base_price || 10) * 0.75)} G each
                        </span>
                      </div>

                      <div className="grid grid-cols-2 gap-2">
                        <button
                          onClick={() => handleSell(item, 1)}
                          disabled={actionLoading === `sell-${item.item_id}`}
                          className="py-1.5 px-2 rounded-xl bg-emerald-600/20 hover:bg-emerald-600/30 text-emerald-300 border border-emerald-500/30 text-xs font-semibold transition"
                        >
                          {actionLoading === `sell-${item.item_id}` ? 'Selling...' : 'Sell (1x)'}
                        </button>
                        <button
                          onClick={() => {
                            setTransferModalItem(item);
                            setTransferQty(1);
                            setTransferTargetId('');
                          }}
                          className="py-1.5 px-2 rounded-xl bg-cyan-600/20 hover:bg-cyan-600/30 text-cyan-300 border border-cyan-500/30 text-xs font-semibold transition"
                        >
                          Transfer 🔄
                        </button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Audit Log / Recent Transactions Accordion */}
        <div className="glass-card rounded-2xl p-6 border border-white/10 mt-8">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-bold text-white uppercase tracking-wider flex items-center gap-2">
              <span>📜</span>
              <span>Personal Transaction Ledger</span>
            </h3>
            <span className="text-xs text-slate-400 font-mono">
              {transactions.length} records logged
            </span>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-white/10 text-slate-400 font-semibold uppercase tracking-wider">
                  <th className="pb-3 px-3">Tx ID</th>
                  <th className="pb-3 px-3">Operation</th>
                  <th className="pb-3 px-3">Quantity</th>
                  <th className="pb-3 px-3">Net Gold</th>
                  <th className="pb-3 px-3">Details</th>
                  <th className="pb-3 px-3 text-right">Time</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5">
                {transactions.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="py-6 text-center text-slate-500">
                      No transactions recorded.
                    </td>
                  </tr>
                ) : (
                  transactions.slice(0, 8).map((tx) => (
                    <tr key={tx.transaction_id} className="hover:bg-white/5 transition">
                      <td className="py-3 px-3 text-slate-400 font-mono">
                        #{tx.transaction_id}
                      </td>
                      <td className="py-3 px-3">
                        <span
                          className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider ${
                            tx.transaction_type === 'buy'
                              ? 'bg-rose-500/20 text-rose-300'
                              : tx.transaction_type === 'sell'
                              ? 'bg-emerald-500/20 text-emerald-300'
                              : 'bg-cyan-500/20 text-cyan-300'
                          }`}
                        >
                          {tx.transaction_type}
                        </span>
                      </td>
                      <td className="py-3 px-3 text-slate-200 font-mono">
                        {tx.quantity}x
                      </td>
                      <td className="py-3 px-3 font-mono">
                        {tx.gold_amount > 0 ? (
                          <span className="text-emerald-400 font-bold">
                            +{tx.gold_amount} G
                          </span>
                        ) : tx.gold_amount < 0 ? (
                          <span className="text-rose-400 font-bold">
                            {tx.gold_amount} G
                          </span>
                        ) : (
                          <span className="text-slate-400">0 G</span>
                        )}
                      </td>
                      <td className="py-3 px-3 text-slate-300 max-w-sm truncate">
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

        {/* Transfer Item Modal */}
        {transferModalItem && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm animate-in fade-in">
            <div className="glass-card max-w-md w-full p-6 rounded-2xl border border-cyan-500/30 shadow-2xl relative">
              <div className="flex items-center justify-between mb-4 pb-3 border-b border-white/10">
                <div className="flex items-center gap-2">
                  <span className="text-lg">🔄</span>
                  <h3 className="text-sm font-bold text-white">Transfer Item to Player</h3>
                </div>
                <button
                  onClick={() => setTransferModalItem(null)}
                  className="text-slate-400 hover:text-white text-xs"
                >
                  ✕
                </button>
              </div>

              <form onSubmit={handleTransferSubmit} className="space-y-4">
                <div className="p-3 rounded-xl bg-white/5 border border-white/10 flex items-center justify-between text-xs">
                  <div>
                    <div className="font-bold text-white">{transferModalItem.name}</div>
                    <div className="text-[11px] text-slate-400">
                      In Vault: {transferModalItem.quantity}x
                    </div>
                  </div>
                  <span
                    className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase ${getRarityBadge(
                      transferModalItem.rarity || 'common'
                    )}`}
                  >
                    {transferModalItem.rarity || 'common'}
                  </span>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                    Target Player ID
                  </label>
                  <input
                    type="number"
                    required
                    min="1"
                    value={transferTargetId}
                    onChange={(e) => setTransferTargetId(e.target.value)}
                    placeholder="e.g. 2"
                    className="w-full glass-input px-3.5 py-2 rounded-xl text-xs"
                  />
                  <p className="text-[10px] text-slate-400 mt-1">
                    Enter the recipient player&apos;s numeric ID (from Leaderboard or Admin).
                  </p>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                    Quantity to Transfer
                  </label>
                  <input
                    type="number"
                    required
                    min="1"
                    max={transferModalItem.quantity}
                    value={transferQty}
                    onChange={(e) => setTransferQty(Math.max(1, parseInt(e.target.value, 10) || 1))}
                    className="w-full glass-input px-3.5 py-2 rounded-xl text-xs"
                  />
                </div>

                <div className="flex items-center justify-end gap-2 pt-3 border-t border-white/10">
                  <button
                    type="button"
                    onClick={() => setTransferModalItem(null)}
                    className="px-4 py-2 rounded-xl bg-white/5 hover:bg-white/10 text-slate-300 text-xs font-semibold"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={actionLoading !== null}
                    className="px-4 py-2 rounded-xl bg-cyan-600 hover:bg-cyan-500 text-white text-xs font-semibold shadow-lg shadow-cyan-600/30"
                  >
                    {actionLoading ? 'Transferring...' : 'Confirm Transfer'}
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
