// frontend/src/lib/api/modeling.ts

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001";

// ── Code Analysis ──

export interface ParseRequest {
  repo_url: string;
  repo_id: string;
}

export interface ParseResponse {
  repo_id: string;
  files_parsed: number;
  entities_count: number;
  relations_count: number;
}

export async function parseRepo(req: ParseRequest): Promise<ParseResponse> {
  const res = await fetch(`${API_BASE}/api/modeling/code/parse`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export interface CodeEntity {
  id: string;
  name: string;
  kind: string;
  file_path: string;
  parent: string | null;
}

export async function getCodeGraph(repoId: string, kind?: string): Promise<{ entities: CodeEntity[] }> {
  const params = kind ? `?kind=${kind}` : "";
  const res = await fetch(`${API_BASE}/api/modeling/code/graph/${repoId}${params}`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

// ── Domain Ontology ──

export interface DomainNode {
  id: string;
  name: string;
  kind: string;
  parent_id: string | null;
  description?: string;
}

export async function loadTemplate(): Promise<{ loaded: number }> {
  const res = await fetch(`${API_BASE}/api/modeling/ontology/load-template`, { method: "POST" });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function getOntologyTree(): Promise<{ nodes: DomainNode[] }> {
  const res = await fetch(`${API_BASE}/api/modeling/ontology/tree`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

// ── Mappings ──

export interface MappingEntry {
  code: string;
  domain: string;
  granularity: string;
  owner: string;
  status: "draft" | "review" | "confirmed";
  confirmed_by?: string;
}

export async function getMappings(repoId: string): Promise<{ mappings: MappingEntry[] }> {
  const res = await fetch(`${API_BASE}/api/modeling/mapping/${repoId}`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function addMapping(repoId: string, code: string, domain: string, owner: string): Promise<void> {
  const res = await fetch(`${API_BASE}/api/modeling/mapping/${repoId}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ code, domain, owner }),
  });
  if (!res.ok) throw new Error(await res.text());
}

export async function removeMapping(repoId: string, code: string): Promise<void> {
  const res = await fetch(`${API_BASE}/api/modeling/mapping/${repoId}/${code}`, { method: "DELETE" });
  if (!res.ok) throw new Error(await res.text());
}

export async function getMappingGaps(repoId: string): Promise<{ gaps: { qualified_name: string; kind: string; file_path: string }[]; count: number }> {
  const res = await fetch(`${API_BASE}/api/modeling/mapping/${repoId}/gaps`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

// ── Impact Analysis ──

export interface ImpactResult {
  source_term: string;
  source_code_entity: string | null;
  source_domain: string | null;
  affected_processes: {
    domain_id: string;
    domain_name: string;
    path: string[];
    distance: number;
  }[];
  unmapped_entities: string[];
  resolved: boolean;
  message: string;
}

export async function analyzeImpact(term: string, repoId: string): Promise<ImpactResult> {
  const res = await fetch(`${API_BASE}/api/modeling/impact/analyze`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ term, repo_id: repoId }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

// ── Approvals ──

export interface ReviewRequest {
  id: string;
  mapping_code: string;
  mapping_domain: string;
  status: "pending" | "approved" | "rejected";
  requested_by: string;
  reviewer?: string;
  comment?: string;
}

export async function submitReview(repoId: string, code: string, domain: string, requestedBy: string): Promise<ReviewRequest> {
  const res = await fetch(`${API_BASE}/api/modeling/approval/submit`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ mapping_code: code, mapping_domain: domain, repo_id: repoId, requested_by: requestedBy }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function approveReview(reviewId: string, reviewer: string): Promise<ReviewRequest> {
  const res = await fetch(`${API_BASE}/api/modeling/approval/${reviewId}/approve`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ reviewer }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function rejectReview(reviewId: string, reviewer: string, comment: string): Promise<ReviewRequest> {
  const res = await fetch(`${API_BASE}/api/modeling/approval/${reviewId}/reject`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ reviewer, comment }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function addDomainNode(node: { id: string; name: string; kind: string; parent_id: string | null }): Promise<DomainNode> {
  const res = await fetch(`${API_BASE}/api/modeling/ontology/node`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(node),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function getPendingReviews(repoId: string): Promise<{ reviews: ReviewRequest[] }> {
  const res = await fetch(`${API_BASE}/api/modeling/approval/pending/${repoId}`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}
