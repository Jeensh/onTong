/**
 * DB 시드 API — POST /api/simulation/seed, GET /seed/status, GET /orders.
 */

export interface SeedCounts {
  plant_mapping: number;
  cast_spec: number;
  hr_spec: number;
  edging_spec: number;
  edging_group: number;
  hr_min_wgt: number;
  hr_max_wgt: number;
  productivity_std: number;
  customer_std: number;
  order_os: number;
}

export interface SeedResponse {
  status: "ok";
  reset: boolean;
  counts: SeedCounts;
}

export interface SeedStatusResponse {
  status: "ok";
  counts: SeedCounts;
}

export interface OrderRow {
  cmp_cd: string;
  org_cd: string;
  order_no: string;
  stock_code: number | null;
  order_width: string | null;
  order_length: string | null;
  order_wgt_low: string | null;
  order_wgt_high: string | null;
  pkg_wgt_low: string | null;
  pkg_wgt_high: string | null;
  grade_cd: string | null;
  customer_cd: string | null;
}

export interface OrdersResponse {
  status: "ok";
  orders: OrderRow[];
  count: number;
}

const BASE = "/api/simulation";

export async function seedDb(reset = true): Promise<SeedResponse> {
  const res = await fetch(`${BASE}/seed?reset=${reset}`, { method: "POST" });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`Seed 실패 (${res.status}): ${detail}`);
  }
  return res.json();
}

export async function getSeedStatus(): Promise<SeedStatusResponse> {
  const res = await fetch(`${BASE}/seed/status`);
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`상태 조회 실패 (${res.status}): ${detail}`);
  }
  return res.json();
}

export async function listOrders(): Promise<OrdersResponse> {
  const res = await fetch(`${BASE}/orders`);
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`주문 조회 실패 (${res.status}): ${detail}`);
  }
  return res.json();
}
