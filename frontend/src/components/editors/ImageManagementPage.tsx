"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Trash2, Search, Image as ImageIcon, ChevronLeft, ChevronRight } from "lucide-react";

interface ImageAsset {
  filename: string;
  size_bytes: number;
  width: number;
  height: number;
  ref_count: number;
  referenced_by: string[];
  source: string | null;
  derivatives: string[];
  has_ocr: boolean;
  created_at: string;
}

interface AssetStats {
  total: number;
  unused: number;
  total_bytes: number;
  derivative_count: number;
}

type FilterType = "all" | "used" | "unused" | "derivative";

export function ImageManagementPage() {
  const [stats, setStats] = useState<AssetStats | null>(null);
  const [items, setItems] = useState<ImageAsset[]>([]);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [total, setTotal] = useState(0);
  const [filter, setFilter] = useState<FilterType>("all");
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [detail, setDetail] = useState<ImageAsset | null>(null);
  const [loading, setLoading] = useState(false);
  const searchTimeout = useRef<ReturnType<typeof setTimeout>>(undefined);

  const fetchStats = useCallback(async () => {
    try {
      const res = await fetch("/api/files/assets/stats");
      if (res.ok) setStats(await res.json());
    } catch {}
  }, []);

  const fetchItems = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({
        page: String(page),
        size: "50",
        filter,
        ...(search && { search }),
      });
      const res = await fetch(`/api/files/assets?${params}`);
      if (res.ok) {
        const data = await res.json();
        setItems(data.items);
        setTotalPages(data.pages);
        setTotal(data.total);
      }
    } catch {} finally {
      setLoading(false);
    }
  }, [page, filter, search]);

  useEffect(() => { fetchStats(); }, [fetchStats]);
  useEffect(() => { fetchItems(); }, [fetchItems]);

  const handleSearch = (value: string) => {
    clearTimeout(searchTimeout.current);
    searchTimeout.current = setTimeout(() => {
      setSearch(value);
      setPage(1);
    }, 300);
  };

  const handleDelete = async (filename: string) => {
    if (!confirm(`"${filename}" 을(를) 삭제하시겠습니까?`)) return;
    const res = await fetch(`/api/files/assets/${filename}`, { method: "DELETE" });
    if (res.ok) {
      fetchItems();
      fetchStats();
      setDetail(null);
    } else {
      const err = await res.json();
      alert(err.detail || "삭제 실패");
    }
  };

  const handleBulkDelete = async () => {
    if (!stats) return;
    const msg = `미사용 이미지 ${stats.unused}개를 삭제하시겠습니까?`;
    if (!confirm(msg)) return;

    const res = await fetch("/api/files/assets/bulk-delete", { method: "POST" });
    if (res.ok) {
      const data = await res.json();
      alert(`${data.deleted}개 삭제 완료 (${formatBytes(data.freed_bytes)} 확보)`);
      setSelected(new Set());
      fetchItems();
      fetchStats();
    }
  };

  const selectAllUnused = () => {
    const unused = items.filter((i) => i.ref_count === 0).map((i) => i.filename);
    setSelected(new Set(unused));
  };

  return (
    <div className="flex flex-col h-full">
      {/* Top bar */}
      <div className="flex items-center justify-between px-4 py-3 border-b bg-muted/30">
        <div className="flex items-center gap-3">
          <span className="font-bold text-sm">이미지 관리</span>
          {stats && (
            <>
              <span className="bg-green-100 text-green-700 text-xs px-2 py-0.5 rounded-full">
                전체 {stats.total}개
              </span>
              <span className="bg-orange-100 text-orange-700 text-xs px-2 py-0.5 rounded-full">
                미사용 {stats.unused}개
              </span>
              <span className="bg-blue-100 text-blue-700 text-xs px-2 py-0.5 rounded-full">
                {formatBytes(stats.total_bytes)}
              </span>
            </>
          )}
        </div>
        <div className="flex items-center gap-2">
          <div className="relative">
            <Search size={14} className="absolute left-2 top-1/2 -translate-y-1/2 text-muted-foreground" />
            <input
              type="text"
              placeholder="파일명 검색..."
              onChange={(e) => handleSearch(e.target.value)}
              className="pl-7 pr-3 py-1.5 text-xs border rounded-md w-44 bg-background"
            />
          </div>
          <select
            value={filter}
            onChange={(e) => { setFilter(e.target.value as FilterType); setPage(1); }}
            className="px-2 py-1.5 text-xs border rounded-md bg-background"
          >
            <option value="all">전체</option>
            <option value="used">사용 중</option>
            <option value="unused">미사용</option>
            <option value="derivative">파생본</option>
          </select>
        </div>
      </div>

      {/* Gallery grid */}
      <div className="flex-1 overflow-auto p-4">
        {loading ? (
          <div className="flex items-center justify-center h-full text-muted-foreground text-sm">로딩 중...</div>
        ) : items.length === 0 ? (
          <div className="flex items-center justify-center h-full text-muted-foreground text-sm">
            <ImageIcon size={20} className="mr-2" />
            이미지가 없습니다
          </div>
        ) : (
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
            {items.map((item) => (
              <ImageCard
                key={item.filename}
                item={item}
                isSelected={selected.has(item.filename)}
                onToggleSelect={() => {
                  setSelected((prev) => {
                    const next = new Set(prev);
                    if (next.has(item.filename)) next.delete(item.filename);
                    else next.add(item.filename);
                    return next;
                  });
                }}
                onClick={() => setDetail(item)}
              />
            ))}
          </div>
        )}
      </div>

      {/* Bottom bar */}
      <div className="flex items-center justify-between px-4 py-2.5 border-t bg-muted/30">
        <div className="flex items-center gap-3">
          <span className="text-xs text-muted-foreground">
            {selected.size > 0
              ? `${selected.size}개 선택됨`
              : `${total}개 중 ${items.length}개 표시`}
          </span>
          <div className="flex items-center gap-1">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page <= 1}
              className="p-1 rounded hover:bg-muted disabled:opacity-30"
            >
              <ChevronLeft size={14} />
            </button>
            <span className="text-xs text-muted-foreground px-1">{page}/{totalPages}</span>
            <button
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={page >= totalPages}
              className="p-1 rounded hover:bg-muted disabled:opacity-30"
            >
              <ChevronRight size={14} />
            </button>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={selectAllUnused}
            className="px-3 py-1.5 text-xs border rounded-md hover:bg-muted"
          >
            전체 미사용 선택
          </button>
          <button
            onClick={handleBulkDelete}
            disabled={!stats || stats.unused === 0}
            className="px-3 py-1.5 text-xs bg-red-500 text-white rounded-md hover:bg-red-600 disabled:opacity-50"
          >
            <Trash2 size={12} className="inline mr-1" />
            미사용 전체 삭제
          </button>
        </div>
      </div>

      {/* Detail modal */}
      {detail && (
        <DetailModal
          item={detail}
          onClose={() => setDetail(null)}
          onDelete={() => handleDelete(detail.filename)}
        />
      )}
    </div>
  );
}


function ImageCard({
  item,
  isSelected,
  onToggleSelect,
  onClick,
}: {
  item: ImageAsset;
  isSelected: boolean;
  onToggleSelect: () => void;
  onClick: () => void;
}) {
  const imgRef = useRef<HTMLImageElement>(null);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    const el = imgRef.current;
    if (!el) return;
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          el.src = `/api/files/assets/${item.filename}`;
          observer.disconnect();
        }
      },
      { rootMargin: "200px" }
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, [item.filename]);

  const borderColor = item.ref_count > 0
    ? "border-green-300"
    : "border-orange-400 border-2";

  return (
    <div
      className={`rounded-lg overflow-hidden bg-card cursor-pointer hover:shadow-md transition-shadow ${borderColor} border`}
      onClick={onClick}
    >
      <div className="h-24 bg-muted/30 flex items-center justify-center relative">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          ref={imgRef}
          alt={item.filename}
          onLoad={() => setLoaded(true)}
          className={`max-h-full max-w-full object-contain transition-opacity ${loaded ? "opacity-100" : "opacity-0"}`}
          draggable={false}
        />
        {!loaded && (
          <ImageIcon size={20} className="absolute text-muted-foreground" />
        )}
        <div className="absolute top-1 right-1 flex gap-1">
          {item.ref_count > 0 ? (
            <span className="bg-green-500 text-white text-[9px] px-1.5 py-0.5 rounded">
              참조 {item.ref_count}
            </span>
          ) : (
            <span className="bg-orange-500 text-white text-[9px] px-1.5 py-0.5 rounded">미사용</span>
          )}
        </div>
        {item.source && (
          <span className="absolute top-1 left-1 bg-purple-500 text-white text-[9px] px-1.5 py-0.5 rounded">
            파생
          </span>
        )}
        {item.derivatives.length > 0 && (
          <span className="absolute bottom-1 left-1 bg-purple-500 text-white text-[9px] px-1.5 py-0.5 rounded">
            파생 {item.derivatives.length}
          </span>
        )}
        {item.ref_count === 0 && (
          <div className="absolute bottom-1 right-1" onClick={(e) => e.stopPropagation()}>
            <input
              type="checkbox"
              checked={isSelected}
              onChange={onToggleSelect}
              className="w-4 h-4 cursor-pointer"
            />
          </div>
        )}
      </div>
      <div className="p-2">
        <div className="text-[11px] font-medium truncate">{item.filename}</div>
        <div className="text-[10px] text-muted-foreground">
          {formatBytes(item.size_bytes)} &middot; {item.width}x{item.height}
        </div>
      </div>
    </div>
  );
}


function DetailModal({
  item,
  onClose,
  onDelete,
}: {
  item: ImageAsset;
  onClose: () => void;
  onDelete: () => void;
}) {
  return (
    <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center" onClick={onClose}>
      <div className="bg-card rounded-lg shadow-xl max-w-lg w-full mx-4 max-h-[80vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
        <div className="p-4">
          <div className="flex items-center justify-between mb-3">
            <h3 className="font-bold text-sm">{item.filename}</h3>
            <button onClick={onClose} className="text-muted-foreground hover:text-foreground text-lg">&times;</button>
          </div>

          <div className="bg-muted/30 rounded-lg p-4 flex items-center justify-center mb-4">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={`/api/files/assets/${item.filename}`} alt={item.filename} className="max-h-60 max-w-full object-contain" />
          </div>

          <div className="grid grid-cols-2 gap-2 text-xs mb-4">
            <div className="text-muted-foreground">크기</div>
            <div>{item.width} x {item.height}</div>
            <div className="text-muted-foreground">용량</div>
            <div>{formatBytes(item.size_bytes)}</div>
            <div className="text-muted-foreground">참조 수</div>
            <div>{item.ref_count}</div>
            <div className="text-muted-foreground">OCR</div>
            <div>{item.has_ocr ? "있음" : "없음"}</div>
            {item.source && (
              <>
                <div className="text-muted-foreground">원본</div>
                <div className="text-purple-600">{item.source}</div>
              </>
            )}
            <div className="text-muted-foreground">생성일</div>
            <div>{new Date(item.created_at).toLocaleDateString("ko-KR")}</div>
          </div>

          {item.referenced_by.length > 0 && (
            <div className="mb-4">
              <div className="text-xs font-bold mb-1">참조 문서</div>
              <div className="space-y-0.5">
                {item.referenced_by.map((doc) => (
                  <div key={doc} className="text-xs text-blue-600 truncate">{doc}</div>
                ))}
              </div>
            </div>
          )}

          {item.derivatives.length > 0 && (
            <div className="mb-4">
              <div className="text-xs font-bold mb-1">파생 이미지</div>
              <div className="space-y-0.5">
                {item.derivatives.map((d) => (
                  <div key={d} className="text-xs text-purple-600 truncate">{d}</div>
                ))}
              </div>
            </div>
          )}

          {item.ref_count === 0 && (
            <button
              onClick={onDelete}
              className="w-full py-2 bg-red-500 text-white text-xs rounded-md hover:bg-red-600"
            >
              <Trash2 size={12} className="inline mr-1" />
              삭제
            </button>
          )}
        </div>
      </div>
    </div>
  );
}


function formatBytes(bytes: number): string {
  if (!bytes) return "0B";
  if (bytes < 1024) return `${bytes}B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)}KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)}MB`;
}
