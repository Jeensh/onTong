import type { FilterSpec } from "@/lib/search/useSearchStore";
import { getCurrentUserName } from "@/lib/auth/currentUser";

export interface FilterPreset {
  id: string;
  name: string;
  filters: FilterSpec;
  createdAt: string;
}

const KEY_PREFIX = "ontong.search.presets.v1.";
const MAX_PRESETS = 20;

function storageKey(userName?: string): string {
  const u = userName ?? getCurrentUserName();
  return `${KEY_PREFIX}${u}`;
}

export function loadPresets(userName?: string): FilterPreset[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = window.localStorage.getItem(storageKey(userName));
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed.filter(
      (p): p is FilterPreset =>
        p && typeof p.id === "string" && typeof p.name === "string" && p.filters && typeof p.filters === "object"
    );
  } catch {
    return [];
  }
}

function writePresets(presets: FilterPreset[], userName?: string): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(storageKey(userName), JSON.stringify(presets));
  } catch {
    // Quota exceeded or disabled — silently ignore
  }
}

export function savePreset(name: string, filters: FilterSpec, userName?: string): FilterPreset {
  const trimmed = name.trim();
  if (!trimmed) throw new Error("프리셋 이름을 입력해주세요.");
  const presets = loadPresets(userName);
  const existingIdx = presets.findIndex((p) => p.name === trimmed);
  const preset: FilterPreset = {
    id: existingIdx >= 0 ? presets[existingIdx].id : cryptoId(),
    name: trimmed,
    filters: JSON.parse(JSON.stringify(filters)),
    createdAt: new Date().toISOString(),
  };
  if (existingIdx >= 0) {
    presets[existingIdx] = preset;
  } else {
    presets.unshift(preset);
    if (presets.length > MAX_PRESETS) presets.length = MAX_PRESETS;
  }
  writePresets(presets, userName);
  return preset;
}

export function deletePreset(id: string, userName?: string): void {
  const presets = loadPresets(userName).filter((p) => p.id !== id);
  writePresets(presets, userName);
}

function cryptoId(): string {
  if (typeof crypto !== "undefined" && crypto.randomUUID) return crypto.randomUUID();
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
}
