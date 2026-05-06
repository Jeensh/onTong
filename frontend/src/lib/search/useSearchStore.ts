import { create } from "zustand";

export interface SearchResult {
  path: string;
  title: string;
  snippet: string;
  tags: string[];
  score: number;
}

export interface HybridSearchResult {
  path: string;
  title: string;
  snippet: string;
  score: number;
  tags: string[];
  status: string;
}

export interface TagFilter {
  include?: string[];
  exclude?: string[];
  mode?: "AND" | "OR";
}

export interface FilterSpec {
  path?: string;
  folders?: string[];
  tags?: TagFilter;
  authors?: string[];
  types?: string[];
  mtime_from?: string;
  mtime_to?: string;
  statuses?: string[];
  acl?: string[];
  boolean?: string;
}

export type FilterKey = keyof FilterSpec;

interface SearchState {
  isOpen: boolean;
  query: string;
  results: SearchResult[];
  searchMode: "local" | "semantic";
  semanticResults: HybridSearchResult[];
  semanticLoading: boolean;
  isLoaded: boolean;
  isLoading: boolean;
  filters: FilterSpec;
  filterSheetOpen: boolean;
  setOpen: (open: boolean) => void;
  toggle: () => void;
  setQuery: (query: string) => void;
  setSearchMode: (mode: "local" | "semantic") => void;
  loadIndex: () => Promise<void>;
  search: (query: string) => void;
  searchSemantic: (query: string) => Promise<void>;
  clear: () => void;
  setFilter: <K extends FilterKey>(key: K, value: FilterSpec[K]) => void;
  removeFilter: (key: FilterKey) => void;
  clearFilters: () => void;
  mergeFilters: (patch: Partial<FilterSpec>) => void;
  setFilterSheetOpen: (open: boolean) => void;
  openWithFilters: (patch: Partial<FilterSpec>) => void;
}

let debounceTimer: ReturnType<typeof setTimeout> | null = null;

function isEmptyFilters(f: FilterSpec): boolean {
  if (!f) return true;
  const tags = f.tags ?? {};
  return (
    !f.path &&
    !(f.folders && f.folders.length) &&
    !(tags.include && tags.include.length) &&
    !(tags.exclude && tags.exclude.length) &&
    !(f.authors && f.authors.length) &&
    !(f.types && f.types.length) &&
    !f.mtime_from &&
    !f.mtime_to &&
    !(f.statuses && f.statuses.length) &&
    !(f.acl && f.acl.length) &&
    !f.boolean
  );
}

function normalizeFilters(f: FilterSpec): FilterSpec {
  // Strip empty arrays / undefined keys so backend sees a clean spec
  const out: FilterSpec = {};
  if (f.path) out.path = f.path;
  if (f.folders?.length) out.folders = [...f.folders];
  if (f.tags) {
    const t: TagFilter = {};
    if (f.tags.include?.length) t.include = [...f.tags.include];
    if (f.tags.exclude?.length) t.exclude = [...f.tags.exclude];
    if (f.tags.mode) t.mode = f.tags.mode;
    if (Object.keys(t).length) out.tags = t;
  }
  if (f.authors?.length) out.authors = [...f.authors];
  if (f.types?.length) out.types = [...f.types];
  if (f.mtime_from) out.mtime_from = f.mtime_from;
  if (f.mtime_to) out.mtime_to = f.mtime_to;
  if (f.statuses?.length) out.statuses = [...f.statuses];
  if (f.acl?.length) out.acl = [...f.acl];
  if (f.boolean) out.boolean = f.boolean;
  return out;
}

function buildFiltersQuery(f: FilterSpec): string {
  const normalized = normalizeFilters(f);
  if (isEmptyFilters(normalized)) return "";
  return `&filters=${encodeURIComponent(JSON.stringify(normalized))}`;
}

export const useSearchStore = create<SearchState>((set, get) => ({
  isOpen: false,
  query: "",
  results: [],
  searchMode: "local",
  semanticResults: [],
  semanticLoading: false,
  isLoaded: true,
  isLoading: false,
  filters: {},
  filterSheetOpen: false,

  setOpen: (open) => {
    set({ isOpen: open });
  },

  toggle: () => {
    const { isOpen, setOpen } = get();
    setOpen(!isOpen);
  },

  setQuery: (query) => {
    set({ query });
    const { searchMode } = get();
    if (searchMode === "local") {
      get().search(query);
    }
  },

  setSearchMode: (mode) => {
    set({ searchMode: mode });
    const { query } = get();
    if (mode === "local" && query) {
      get().search(query);
    } else if (mode === "semantic" && query) {
      get().searchSemantic(query);
    }
  },

  loadIndex: async () => {
    // No-op: server-side search, no client index needed
  },

  search: (query) => {
    if (!query.trim()) {
      set({ results: [] });
      return;
    }
    if (debounceTimer) clearTimeout(debounceTimer);
    debounceTimer = setTimeout(async () => {
      set({ isLoading: true });
      try {
        const { filters } = get();
        const qs = buildFiltersQuery(filters);
        const res = await fetch(
          `/api/search/quick?q=${encodeURIComponent(query)}&limit=20${qs}`
        );
        if (!res.ok) throw new Error("Quick search failed");
        const data: HybridSearchResult[] = await res.json();
        const results: SearchResult[] = data.map((r) => ({
          path: r.path,
          title: r.title,
          snippet: r.snippet,
          tags: r.tags,
          score: r.score,
        }));
        set({ results });
      } catch (err) {
        console.error("Quick search failed:", err);
        set({ results: [] });
      } finally {
        set({ isLoading: false });
      }
    }, 200);
  },

  searchSemantic: async (query) => {
    if (!query.trim()) {
      set({ semanticResults: [] });
      return;
    }
    set({ semanticLoading: true });
    try {
      const { filters } = get();
      const qs = buildFiltersQuery(filters);
      const res = await fetch(
        `/api/search/hybrid?q=${encodeURIComponent(query)}&n=15${qs}`
      );
      if (!res.ok) throw new Error("Hybrid search failed");
      const data: HybridSearchResult[] = await res.json();
      set({ semanticResults: data });
    } catch (err) {
      console.error("Semantic search failed:", err);
      set({ semanticResults: [] });
    } finally {
      set({ semanticLoading: false });
    }
  },

  clear: () => {
    set({ query: "", results: [], semanticResults: [], isOpen: false });
  },

  setFilter: (key, value) => {
    const { filters, searchMode, query } = get();
    const next: FilterSpec = { ...filters, [key]: value };
    set({ filters: next });
    // Re-run current search if query active
    if (query.trim()) {
      if (searchMode === "local") get().search(query);
      else get().searchSemantic(query);
    }
  },

  removeFilter: (key) => {
    const { filters, searchMode, query } = get();
    const next: FilterSpec = { ...filters };
    delete next[key];
    set({ filters: next });
    if (query.trim()) {
      if (searchMode === "local") get().search(query);
      else get().searchSemantic(query);
    }
  },

  clearFilters: () => {
    const { searchMode, query } = get();
    set({ filters: {} });
    if (query.trim()) {
      if (searchMode === "local") get().search(query);
      else get().searchSemantic(query);
    }
  },

  mergeFilters: (patch) => {
    const { filters, searchMode, query } = get();
    // Shallow merge, but merge tags subfields
    const next: FilterSpec = { ...filters };
    for (const [k, v] of Object.entries(patch)) {
      if (k === "tags" && v && typeof v === "object") {
        next.tags = { ...(filters.tags ?? {}), ...(v as TagFilter) };
      } else {
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        (next as any)[k] = v;
      }
    }
    set({ filters: next });
    if (query.trim()) {
      if (searchMode === "local") get().search(query);
      else get().searchSemantic(query);
    }
  },

  setFilterSheetOpen: (open) => set({ filterSheetOpen: open }),

  openWithFilters: (patch) => {
    const { filters } = get();
    const next: FilterSpec = { ...filters };
    for (const [k, v] of Object.entries(patch)) {
      if (k === "tags" && v && typeof v === "object") {
        next.tags = { ...(filters.tags ?? {}), ...(v as TagFilter) };
      } else {
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        (next as any)[k] = v;
      }
    }
    set({ filters: next, isOpen: true });
  },
}));

/**
 * Resolve a wiki-link target (stem name) to a full file path.
 * Uses server-side resolution endpoint.
 */
export async function resolveWikiLink(target: string): Promise<string | null> {
  try {
    const res = await fetch(
      `/api/search/resolve-link?target=${encodeURIComponent(target)}`
    );
    if (!res.ok) return null;
    const data = await res.json();
    return data.path ?? null;
  } catch {
    return null;
  }
}
