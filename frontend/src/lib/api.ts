/**
 * Generative NPC Memory Engine - API Client Library
 * Comprehensive strongly-typed client for PostgreSQL transactional endpoints,
 * Qdrant vector memory, authentication, and the interactive SQL Workbench.
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

function getAuthHeader(): Record<string, string> {
  if (typeof window === 'undefined') return {};
  const token = localStorage.getItem('token') || localStorage.getItem('access_token');
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function request<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const url = `${API_BASE}${endpoint}`;
  const headers = {
    'Content-Type': 'application/json',
    ...getAuthHeader(),
    ...((options.headers as Record<string, string>) || {}),
  };

  const response = await fetch(url, { ...options, headers });
  if (response.status === 204) {
    return {} as T;
  }

  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const errorMsg =
      data.detail || data.error || data.message || `Request failed with status ${response.status}`;
    throw new Error(errorMsg);
  }

  return data as T;
}

// ==============================================================================
// TYPES & DATA MODELS
// ==============================================================================

export type Role = 'player' | 'admin';
export type ItemType = 'weapon' | 'armor' | 'potion' | 'misc' | 'quest_item';
export type ItemRarity = 'common' | 'uncommon' | 'rare' | 'epic' | 'legendary';
export type QuestType = 'main' | 'side' | 'daily' | 'hidden';
export type QuestStatus = 'available' | 'active' | 'completed' | 'failed';

export interface User {
  player_id: number;
  username: string;
  email: string;
  role: Role;
  gold: number;
  level: number;
  xp: number;
  created_at?: string;
}

export interface PlayerResponse {
  player_id: number;
  username: string;
  email: string;
  role: string;
  gold: number;
  level: number;
  xp: number;
  created_at: string;
}

export interface UpdatePlayerRequest {
  email?: string;
  role?: 'player' | 'admin';
  gold?: number;
  level?: number;
  xp?: number;
}

export interface NPCResponse {
  npc_id: number;
  name: string;
  persona: string;
  location?: string;
  personality_traits?: Record<string, unknown>;
  greeting?: string;
  created_at?: string;
}

export interface CreateNPCRequest {
  name: string;
  persona: string;
  location?: string;
  personality_traits?: Record<string, unknown>;
  greeting?: string;
}

export interface UpdateNPCRequest {
  name?: string;
  persona?: string;
  location?: string;
  personality_traits?: Record<string, unknown>;
  greeting?: string;
}

export interface ItemResponse {
  item_id: number;
  name: string;
  description?: string;
  base_price: number;
  item_type: ItemType;
  rarity: ItemRarity;
  stock: number;
  created_at?: string;
}

export interface CreateItemRequest {
  name: string;
  description?: string;
  base_price: number;
  item_type: ItemType;
  rarity: ItemRarity;
  stock?: number;
}

export interface UpdateItemRequest {
  name?: string;
  description?: string;
  base_price?: number;
  item_type?: ItemType;
  rarity?: ItemRarity;
  stock?: number;
}

export interface QuestResponse {
  quest_id: number;
  title: string;
  description?: string;
  reward_gold: number;
  reward_xp: number;
  reward_item_id?: number | null;
  reward_item_name?: string | null;
  min_level: number;
  quest_type: QuestType;
  challenge_type?: string;
  challenge_question?: string;
  challenge_hint?: string;
  created_at?: string;
}

export interface CreateQuestRequest {
  title: string;
  description?: string;
  reward_gold?: number;
  reward_xp?: number;
  reward_item_id?: number | null;
  min_level?: number;
  quest_type?: QuestType;
}

export interface UpdateQuestRequest {
  title?: string;
  description?: string;
  reward_gold?: number;
  reward_xp?: number;
  reward_item_id?: number | null;
  min_level?: number;
  quest_type?: QuestType;
}

export interface InventoryItem {
  inventory_id: number;
  player_id: number;
  item_id: number;
  quantity: number;
  acquired_at: string;
  name?: string;
  description?: string;
  base_price?: number;
  item_type?: ItemType;
  rarity?: ItemRarity;
  is_equipped?: boolean;
}

export interface TransactionResponse {
  transaction_id: number;
  player_id: number;
  item_id?: number | null;
  transaction_type: string;
  quantity: number;
  gold_amount: number;
  description?: string;
  created_at: string;
  item_name?: string;
}

export interface PlayerQuestResponse {
  player_quest_id: number;
  player_id: number;
  quest_id: number;
  status: QuestStatus;
  started_at?: string | null;
  completed_at?: string | null;
  title?: string;
  description?: string;
  reward_gold?: number;
  reward_xp?: number;
  reward_item_id?: number | null;
  min_level?: number;
  quest_type?: QuestType;
  challenge_type?: string;
  challenge_question?: string;
  challenge_hint?: string;
}

export interface PrerequisiteChain {
  depth: number;
  quest_id: number;
  title: string;
  min_level: number;
  traversal_path: string;
  completed?: boolean;
  required_quest_id?: number;
  required_quest_title?: string;
}

export interface NPCRelationship {
  player_id: number;
  npc_id: number;
  affinity_score: number;
  interaction_count: number;
  last_interaction?: string | null;
}

export interface MemoryResponse {
  id: string;
  player_id: number;
  npc_id: number;
  text: string;
  content?: string;
  role: string;
  memory_type?: string;
  importance: number;
  timestamp: number;
  score?: number;
  relevance_score?: number;
}

export interface MemoryStats {
  total_memories: number;
  total_count?: number;
  player_memories?: number;
  by_npc: Array<{ npc_id: number; count: number }>;
  by_player: Array<{ player_id: number; count: number }>;
  recent: MemoryResponse[];
}

export interface CreateMemoryRequest {
  npc_id: number;
  text: string;
  role?: string;
  importance?: number;
}

export interface UpdateMemoryRequest {
  text?: string;
  importance?: number;
}

export interface ChatRequest {
  npc_id: number;
  message: string;
}

export interface ChatResponse {
  reply: string;
  npc_name: string;
  memories_used: MemoryResponse[];
  game_state?: Record<string, unknown>;
  affinity_change?: number;
}

export interface LeaderboardEntry {
  rank: number;
  player_id?: number;
  username: string;
  level: number;
  xp: number;
  gold: number;
  quests_completed: number;
  total_items: number;
}

export interface AdminStats {
  total_players: number;
  total_npcs: number;
  total_items: number;
  total_quests: number;
  total_transactions: number;
  total_memories?: number;
}

export interface NPCPopularity {
  npc_id: number;
  npc_name: string;
  name?: string;
  location?: string;
  total_unique_players: number;
  total_interaction_count: number;
  interaction_count?: number;
  avg_affinity_score: number;
  average_affinity?: number;
  popularity_rank: number;
  memory_count?: number;
}

export interface QuestProgress {
  player_id: number;
  username: string;
  player_level: number;
  quest_id: number;
  quest_title: string;
  title?: string;
  quest_type: string;
  min_level: number;
  status: string;
  reward_gold: number;
  reward_xp: number;
  reward_item_id?: number | null;
  reward_item_name?: string | null;
  prerequisites_met: boolean;
  started_at?: string | null;
  completed_at?: string | null;
  active_count?: number;
  completed_count?: number;
  completion_rate?: number;
}

export interface AuditLogResponse {
  log_id: number;
  table_name: string;
  operation: string;
  row_id?: number | null;
  old_data?: Record<string, unknown> | null;
  new_data?: Record<string, unknown> | null;
  changed_by: string;
  changed_at: string;
}

export interface QueryPreset {
  name: string;
  category: string;
  description: string;
  query: string;
}

export interface SQLWorkbenchResult {
  success: boolean;
  mode?: 'read_only' | 'dml';
  command?: string;
  execution_time_ms?: number;
  row_count?: number;
  affected_rows?: number;
  columns?: string[];
  rows?: Array<Record<string, unknown>>;
  error?: string;
  pg_code?: string;
  status?: string;
  message?: string;
  rolled_back?: boolean;
  committed?: boolean;
  transaction_status?: string;
}

export interface ExplainAnalyzeResult {
  success: boolean;
  summary?: {
    planning_time_ms?: number;
    execution_time_ms?: number;
    node_type?: string;
    total_cost?: number;
    actual_rows?: number;
    plan_rows?: number;
    shared_hit_blocks?: number;
    shared_read_blocks?: number;
    relation_name?: string;
    index_name?: string;
  };
  text_plan?: string;
  json_plan?: Array<Record<string, unknown>>;
  error?: string;
  pg_code?: string;
}

export interface ColumnSchema {
  name: string;
  type: string;
  nullable: boolean;
  default?: string | null;
  is_primary_key: boolean;
  is_pk?: boolean;
  is_fk?: boolean;
  foreign_table?: string;
  foreign_key?: {
    table: string;
    column: string;
  } | null;
}

export interface TableSchema {
  name: string;
  columns: ColumnSchema[];
}

export interface ViewSchema {
  name: string;
  definition?: string;
}

export interface RoutineSchema {
  name: string;
  type: string;
  return_type?: string;
}

export interface DatabaseExplorerResponse {
  tables: TableSchema[];
  views: ViewSchema[];
  routines: RoutineSchema[];
}

// ==============================================================================
// API CONTROLLERS
// ==============================================================================

export const api = {
  // Authentication
  auth: {
    login: (credentials: { username: string; password: string }) =>
      request<{ access_token: string; token_type: string }>('/api/auth/login', {
        method: 'POST',
        body: JSON.stringify(credentials),
      }),
    register: (data: { username: string; email: string; password: string }) =>
      request<{ access_token: string; token_type: string }>('/api/auth/register', {
        method: 'POST',
        body: JSON.stringify(data),
      }),
  },

  // Players
  players: {
    getMe: () => request<User>('/api/players/me'),
    updateMe: (data: { email?: string }) =>
      request<User>('/api/players/me', {
        method: 'PUT',
        body: JSON.stringify(data),
      }),
    getLeaderboard: () => request<LeaderboardEntry[]>('/api/players/leaderboard'),
    getById: (id: number) => request<PlayerResponse>(`/api/players/${id}`),
  },

  // NPCs
  npcs: {
    getAll: () => request<NPCResponse[]>('/api/npcs/'),
    getById: (id: number) => request<NPCResponse>(`/api/npcs/${id}`),
    getRelationship: (npcId: number) =>
      request<NPCRelationship>(`/api/npcs/${npcId}/relationship`),
    create: (data: CreateNPCRequest) =>
      request<NPCResponse>('/api/npcs/', { method: 'POST', body: JSON.stringify(data) }),
    update: (id: number, data: UpdateNPCRequest) =>
      request<NPCResponse>(`/api/npcs/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
    delete: (id: number) =>
      request<{ detail: string }>(`/api/npcs/${id}`, { method: 'DELETE' }),
  },

  // Inventory & Shop
  inventory: {
    getItems: (search?: string) => {
      const q = search ? `?search=${encodeURIComponent(search)}` : '';
      return request<ItemResponse[]>(`/api/inventory/items${q}`);
    },
    getMyInventory: () => request<InventoryItem[]>('/api/inventory/my-inventory'),
    getTransactions: (limit = 50, offset = 0) =>
      request<TransactionResponse[]>(`/api/inventory/transactions?limit=${limit}&offset=${offset}`),
    buy: (payload: { item_id: number; quantity: number }) =>
      request<{ message: string; new_gold: number; item_id: number; quantity: number }>(
        '/api/inventory/buy',
        {
          method: 'POST',
          body: JSON.stringify(payload),
        }
      ),
    sell: (payload: { item_id: number; quantity: number }) =>
      request<{ message: string; new_gold: number; item_id: number; quantity: number }>(
        '/api/inventory/sell',
        {
          method: 'POST',
          body: JSON.stringify(payload),
        }
      ),
    use: (itemId: number) =>
      request<{ message: string; remaining_quantity: number }>(`/api/inventory/use/${itemId}`, {
        method: 'POST',
      }),
    transfer: (payload: { to_player_id: number; item_id: number; quantity: number }) =>
      request<{ message: string; item_id: number; quantity: number; to_player_id: number }>(
        '/api/inventory/transfer',
        {
          method: 'POST',
          body: JSON.stringify(payload),
        }
      ),
  },

  // Quests
  quests: {
    getAll: () => request<QuestResponse[]>('/api/quests/'),
    search: (query: string) =>
      request<QuestResponse[]>(`/api/quests/search?query=${encodeURIComponent(query)}`),
    getMyQuests: () => request<PlayerQuestResponse[]>('/api/quests/my-quests'),
    start: (questId: number) =>
      request<PlayerQuestResponse>(`/api/quests/${questId}/start`, { method: 'POST' }),
    complete: (questId: number, answer?: string) =>
      request<{ message?: string; detail?: string; quest_id: number; status: string }>(
        `/api/quests/${questId}/complete`,
        {
          method: 'POST',
          body: JSON.stringify({ answer: answer || '' }),
        }
      ),
    getPrerequisites: (questId: number) =>
      request<PrerequisiteChain[]>(`/api/quests/${questId}/prerequisites`),
    resetProgress: (resetLevel = false) =>
      request<{ detail: string }>(`/api/quests/reset-progress?reset_level=${resetLevel}`, {
        method: 'POST',
      }),
  },

  // Memory Core (Qdrant)
  memory: {
    getStats: () => request<MemoryStats>('/api/memory/stats'),
    search: (npcId?: number, query?: string, topK = 5) => {
      const params = new URLSearchParams();
      if (npcId !== undefined) params.append('npc_id', String(npcId));
      if (query) params.append('query', query);
      params.append('top_k', String(topK));
      return request<MemoryResponse[]>(`/api/memory/search?${params.toString()}`);
    },
    create: (data: CreateMemoryRequest) =>
      request<MemoryResponse>('/api/memory/', {
        method: 'POST',
        body: JSON.stringify(data),
      }),
    update: (memoryId: string, data: UpdateMemoryRequest) =>
      request<MemoryResponse>(`/api/memory/${memoryId}`, {
        method: 'PUT',
        body: JSON.stringify(data),
      }),
    delete: (memoryId: string | number) =>
      request<{ detail: string }>(`/api/memory/${memoryId}`, { method: 'DELETE' }),
    deletePlayerNPC: (playerId: number, npcId: number) =>
      request<{ detail: string }>(`/api/memory/player/${playerId}/npc/${npcId}`, {
        method: 'DELETE',
      }),
  },

  // Dialogue & Chat
  chat: {
    send: (data: ChatRequest) =>
      request<ChatResponse>('/api/chat/', {
        method: 'POST',
        body: JSON.stringify(data),
      }),
  },

  // Administrative Hub & Interactive SQL Workbench
  admin: {
    getStats: () => request<AdminStats>('/api/admin/stats'),
    getPlayers: () => request<PlayerResponse[]>('/api/admin/players'),
    updatePlayer: (id: number, data: UpdatePlayerRequest) =>
      request<PlayerResponse>(`/api/admin/players/${id}`, {
        method: 'PUT',
        body: JSON.stringify(data),
      }),
    deletePlayer: (id: number) =>
      request<{ detail: string }>(`/api/admin/players/${id}`, { method: 'DELETE' }),
    createNPC: (data: CreateNPCRequest) =>
      request<NPCResponse>('/api/npcs/', { method: 'POST', body: JSON.stringify(data) }),
    updateNPC: (id: number, data: UpdateNPCRequest) =>
      request<NPCResponse>(`/api/npcs/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
    deleteNPC: (id: number) =>
      request<{ detail: string }>(`/api/npcs/${id}`, { method: 'DELETE' }),
    createItem: (data: CreateItemRequest) =>
      request<ItemResponse>('/api/admin/items', { method: 'POST', body: JSON.stringify(data) }),
    updateItem: (id: number, data: UpdateItemRequest) =>
      request<ItemResponse>(`/api/admin/items/${id}`, {
        method: 'PUT',
        body: JSON.stringify(data),
      }),
    deleteItem: (id: number) =>
      request<{ detail: string }>(`/api/admin/items/${id}`, { method: 'DELETE' }),
    createQuest: (data: CreateQuestRequest) =>
      request<QuestResponse>('/api/admin/quests', { method: 'POST', body: JSON.stringify(data) }),
    updateQuest: (id: number, data: UpdateQuestRequest) =>
      request<QuestResponse>(`/api/admin/quests/${id}`, {
        method: 'PUT',
        body: JSON.stringify(data),
      }),
    deleteQuest: (id: number) =>
      request<{ detail: string }>(`/api/admin/quests/${id}`, { method: 'DELETE' }),
    getAuditLog: (limit = 100, offset = 0) =>
      request<AuditLogResponse[]>(`/api/admin/audit-log?limit=${limit}&offset=${offset}`),
    getNPCPopularity: () => request<NPCPopularity[]>('/api/admin/npc-popularity'),
    getQuestProgress: (playerId?: number) => {
      const q = playerId !== undefined ? `?player_id=${playerId}` : '';
      return request<QuestProgress[]>(`/api/admin/quest-progress${q}`);
    },
    getQueryPresets: () => request<QueryPreset[]>('/api/admin/query-presets'),
    executeSql: (query: string, mode: 'read_only' | 'dml' = 'read_only', confirmCommit = false) =>
      request<SQLWorkbenchResult>('/api/admin/sql-playground', {
        method: 'POST',
        body: JSON.stringify({ query, mode, confirm_commit: confirmCommit }),
      }),
    explainAnalyze: (query: string) =>
      request<ExplainAnalyzeResult>('/api/admin/explain-analyze', {
        method: 'POST',
        body: JSON.stringify({ query, mode: 'read_only' }),
      }),
    getDatabaseExplorer: () => request<DatabaseExplorerResponse>('/api/admin/db-explorer'),
  },
};
