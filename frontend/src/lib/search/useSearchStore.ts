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

interface SearchState {
  isOpen: boolean;
  query: string;
  results: SearchResult[];
  searchMode: "local" | "semantic";
  semanticResults: HybridSearchResult[];
  semanticLoading: boolean;
  isLoaded: boolean;
  isLoading: boolean;
  setOpen: (open: boolean) => void;
  toggle: () => void;
  setQuery: (query: string) => void;
  setSearchMode: (mode: "local" | "semantic") => void;
  loadIndex: () => Promise<void>;
  search: (query: string) => void;
  searchSemantic: (query: string) => Promise<void>;
  clear: () => void;
}

let debounceTimer: ReturnType<typeof setTimeout> | null = null;

export const useSearchStore = create<SearchState>((set, get) => ({
  isOpen: false,
  query: "",
  results: [],
  searchMode: "local",
  semanticResults: [],
  semanticLoading: false,
  isLoaded: true, // No client-side index to load
  isLoading: false,

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
    // Debounce server calls (200ms)
    if (debounceTimer) clearTimeout(debounceTimer);
    debounceTimer = setTimeout(async () => {
      set({ isLoading: true });
      try {
        const res = await fetch(
          `/api/search/quick?q=${encodeURIComponent(query)}&limit=20`
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
      const res = await fetch(
        `/api/search/hybrid?q=${encodeURIComponent(query)}&n=15`
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
