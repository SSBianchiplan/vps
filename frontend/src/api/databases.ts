import { API_BASE } from "./config";

export interface DbBase {
  key: string;
  name: string;
  kind: string;
  status: "ok" | "warn" | "off";
  detail: string;
  metrics: Record<string, number | boolean | null>;
  group?: string;
}

export interface DbStatus {
  bases: DbBase[];
  resumo: { total: number; ok: number };
  groups?: string[];
}

export async function getDatabases(): Promise<DbStatus> {
  const res = await fetch(`${API_BASE}/databases`);
  if (!res.ok) throw new Error(`databases -> ${res.status}`);
  return res.json() as Promise<DbStatus>;
}

// Projeto Teste Sistema (PostgreSQL) — inventário + relacionamentos
export interface TableRow { name: string; rows: number }
export interface SchemaInv { desc: string; tables: TableRow[] }
export interface RelGroup { k: string; n: number }
export interface TesteInventory {
  available: boolean;
  message?: string;
  db?: string;
  schemas?: Record<string, SchemaInv>;
  relationships?: Record<string, RelGroup[]>;
  totals?: { schemas: number; tables: number; rows: number; ops: number };
}
export async function getTesteInventory(): Promise<TesteInventory> {
  const res = await fetch(`${API_BASE}/databases/teste`);
  if (!res.ok) throw new Error(`teste -> ${res.status}`);
  return res.json() as Promise<TesteInventory>;
}
