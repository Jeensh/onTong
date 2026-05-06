"use client";

import { useEffect, useState } from "react";
import { useWorkbench, type MainMode } from "./store";
import { ontologyApi, type ActionDTO, type AnchorBindingDTO } from "@/lib/api/ontology";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { BackwardMode } from "./BackwardMode";
import { AuthoringMode } from "./AuthoringMode";

const MODE_LABELS: { id: MainMode | "graph"; label: string }[] = [
  { id: "detail", label: "Detail" },
  { id: "split", label: "↕ Split" },
  { id: "graph", label: "🌐 Graph" },
  { id: "authoring", label: "✏️ Authoring" },
];

export function MainPanel() {
  const { mainMode, setMainMode, direction, setDirection, setGraphMode, selectedActionFqn } =
    useWorkbench();

  return (
    <>
      <div className="h-8 px-3 bg-card border-b border-border flex items-center gap-2 flex-shrink-0">
        {/* selection 표시는 TopBar breadcrumb 으로 통일 — 여기는 view 전환만 */}
        <div className="text-[11px] text-muted-foreground flex-1 truncate">
          {selectedActionFqn ? (
            <>현재 Action: <code className="font-mono text-foreground">{selectedActionFqn.split(".").pop()}</code></>
          ) : (
            "Action 미선택 — 좌측 패키지 트리에서 선택"
          )}
        </div>
        {/* Direction toggle (Backward 는 다음 phase) */}
        <div className="flex bg-muted border border-border rounded overflow-hidden mr-2">
          <button
            onClick={() => setDirection("fwd")}
            className={cn(
              "px-2.5 py-0.5 text-[11px] border-r border-border",
              direction === "fwd" ? "bg-primary text-primary-foreground" : "text-muted-foreground",
            )}
          >
            🔍 Forward
          </button>
          <button
            disabled
            className="px-2.5 py-0.5 text-[11px] text-muted-foreground/40 cursor-not-allowed"
            title="Backward 모드 — 다음 phase"
          >
            🔧 Backward
          </button>
        </div>
        {/* Mode toggle */}
        <div className="flex bg-muted border border-border rounded overflow-hidden">
          {MODE_LABELS.map((m) => (
            <button
              key={m.id}
              onClick={() => {
                if (m.id === "graph") setGraphMode(true);
                else setMainMode(m.id);
              }}
              className={cn(
                "px-2.5 py-0.5 text-[11px] border-r border-border last:border-r-0",
                m.id !== "graph" && mainMode === m.id
                  ? "bg-primary text-primary-foreground"
                  : "text-muted-foreground hover:text-foreground",
              )}
            >
              {m.label}
            </button>
          ))}
        </div>
      </div>
      <div
        className={cn(
          "flex-1 overflow-auto",
          direction === "bwd" && "bg-amber-500/[0.02]",
        )}
      >
        {direction === "fwd" && mainMode === "detail" && <ForwardDetail />}
        {direction === "fwd" && mainMode === "split" && <SplitMode />}
        {direction === "fwd" && mainMode === "authoring" && <AuthoringMode />}
        {direction === "bwd" && <BackwardMode />}
      </div>
    </>
  );
}

// ── Forward Detail (Phase 1 핵심 view) ─────────────────────────────────
function ForwardDetail() {
  const { selectedActionFqn } = useWorkbench();
  const [action, setAction] = useState<ActionDTO | null>(null);
  const [anchors, setAnchors] = useState<AnchorBindingDTO[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!selectedActionFqn) {
      setAction(null);
      setAnchors([]);
      return;
    }
    let cancelled = false;
    setLoading(true);
    Promise.all([
      ontologyApi.getAction(selectedActionFqn).catch(() => null),
      ontologyApi.getAnchorBindingsForAction(selectedActionFqn).catch(() => []),
    ]).then(([a, b]) => {
      if (cancelled) return;
      setAction(a);
      setAnchors(b);
      setLoading(false);
    });
    return () => {
      cancelled = true;
    };
  }, [selectedActionFqn]);

  if (loading) {
    return <div className="p-6 text-muted-foreground text-sm">Loading...</div>;
  }
  if (!action) {
    return (
      <div className="p-6 text-muted-foreground text-sm">
        Action 선택 또는 backend 에 데이터 없음 (Phase 1 시작 직후 빈 상태가 정상).
      </div>
    );
  }

  return (
    <div className="p-5 max-w-[920px]">
      <div className="bg-primary/5 border-l-2 border-primary px-3 py-1.5 mb-3 text-[11.5px] text-muted-foreground">
        🔍 <strong className="text-primary">Forward 매핑</strong> — 코드를 도메인 의미로 매핑 (초기 작업)
      </div>

      <h1 className="text-lg font-semibold mb-1 flex items-center gap-2">
        {action.label}
        <span className="text-[11px] px-1.5 py-px rounded-full border text-orange-400 border-orange-400 bg-orange-400/10">
          action
        </span>
        <span className="text-[11px] px-1.5 py-px rounded-full border text-muted-foreground border-border">
          {action.kind}
        </span>
        {action.is_abstract && (
          <span className="text-[11px] px-1.5 py-px rounded-full border text-muted-foreground border-border">
            abstract
          </span>
        )}
      </h1>
      <div className="text-xs text-muted-foreground mb-4 font-mono">
        {action.fqn}
        {action.declared_on_term && (
          <>
            {" "}
            · declared on <span className="text-foreground">{action.declared_on_term}</span>
          </>
        )}
        <span className="ml-2 text-[11px] px-1.5 py-px rounded-full border border-amber-400 text-amber-400 bg-amber-400/10">
          {action.verification_level.toUpperCase()}
        </span>
      </div>

      <Section title={`Parameters · ${action.params.length}`}>
        {action.params.map((p, i) => (
          <ParamRow
            key={i}
            k={`params[${i}]`}
            name={p.name}
            refTerm={p.object_ref_term ?? null}
            confirmed={p.confirmed}
          />
        ))}
      </Section>

      {action.output && (
        <Section title="Output">
          <ParamRow
            k="return"
            name={action.output.type}
            refTerm={action.output.object_ref_term ?? null}
            confirmed
          />
        </Section>
      )}

      <Section title={`Realizations · ${action.realizations.length} (다형성)`}>
        {action.realizations.map((r, i) => (
          <div key={i} className="bg-muted px-3 py-2 rounded my-1.5">
            <div className="flex items-center gap-2 text-xs">
              <span className="text-[10px] text-amber-400 border border-amber-400 bg-amber-400/10 px-1 rounded">
                code
              </span>
              <span className="font-mono">{r.code_method_fqn}</span>
              {r.is_override && (
                <span className="text-[10px] px-1.5 py-px rounded-full border border-border text-muted-foreground">
                  @Override
                </span>
              )}
              {r.confirmed && (
                <span className="text-[10px] px-1.5 py-px rounded-full border border-emerald-400 text-emerald-400 bg-emerald-400/10 ml-auto">
                  ✓ {r.scope}
                </span>
              )}
            </div>
            <div className="text-[11px] text-muted-foreground mt-0.5">
              applies to{" "}
              <span className="font-mono">{r.applies_to_code_type_fqn ?? "(base)"}</span> ·{" "}
              {r.dispatch_source} · conf {r.confidence}
            </div>
          </div>
        ))}
      </Section>

      {action.preconditions.length > 0 && (
        <Section title={`Preconditions · ${action.preconditions.length}`}>
          {action.preconditions.map((p, i) => (
            <div key={i} className="flex items-center gap-2 text-xs my-1">
              <span className="font-mono text-primary">[{i}]</span>
              <span className="text-[10px] text-pink-400 border border-pink-400 bg-pink-400/10 px-1 rounded">
                rule
              </span>
              <span className="font-mono text-muted-foreground">{p}</span>
            </div>
          ))}
        </Section>
      )}

      <Section
        title={`Anchor Bindings · ${anchors.length}`}
        action={
          <Button
            size="sm"
            variant="outline"
            onClick={() => useWorkbench.setState({ mainMode: "split" })}
          >
            ↕ Split mode 로
          </Button>
        }
      >
        {anchors.map((ab) => (
          <div
            key={ab.id}
            className={cn(
              "bg-muted px-3 py-1.5 rounded my-1 grid grid-cols-[110px_1fr_60px] gap-2 items-center text-xs",
              !ab.confirmed && "border-l-2 border-amber-400 pl-2",
            )}
          >
            <span className="font-mono text-primary">{ab.anchor_locator}</span>
            <span className="font-mono text-[11px] truncate">{ab.target_slot}</span>
            {ab.confirmed ? (
              <span className="text-[10px] text-emerald-400 border border-emerald-400 bg-emerald-400/10 px-1 rounded text-center">
                ✓
              </span>
            ) : (
              <Button size="sm" className="text-[11px] h-6">
                매핑
              </Button>
            )}
          </div>
        ))}
        {anchors.length === 0 && (
          <p className="text-muted-foreground text-[11.5px]">
            anchor 미등록 (Java 분석 + Action 매핑 후 표시)
          </p>
        )}
      </Section>
    </div>
  );
}

function Section({
  title,
  children,
  action,
}: {
  title: string;
  children: React.ReactNode;
  action?: React.ReactNode;
}) {
  return (
    <section className="bg-card border border-border rounded-md my-3 p-3">
      <h3 className="text-[12.5px] font-semibold uppercase tracking-wider text-muted-foreground mb-2 flex items-center justify-between">
        <span>{title}</span>
        {action}
      </h3>
      {children}
    </section>
  );
}

function ParamRow({
  k,
  name,
  refTerm,
  confirmed,
}: {
  k: string;
  name: string;
  refTerm: string | null;
  confirmed: boolean;
}) {
  return (
    <div className="bg-muted px-3 py-1.5 rounded my-1 grid grid-cols-[110px_1fr_60px] gap-2 items-center text-xs">
      <span className="font-mono text-primary">{k}</span>
      <span>
        <strong>{name}</strong>
        {refTerm && (
          <span className="ml-2 text-[10px] text-violet-400 border border-violet-400 bg-violet-400/10 px-1 rounded">
            → {refTerm}
          </span>
        )}
      </span>
      <span
        className={cn(
          "text-[10px] px-1 rounded text-center",
          confirmed
            ? "text-emerald-400 border border-emerald-400 bg-emerald-400/10"
            : "text-amber-400 border border-amber-400 bg-amber-400/10",
        )}
      >
        {confirmed ? "✓" : "..."}
      </span>
    </div>
  );
}

// ── Split mode (Phase 1) ──────────────────────────────────────────────
function SplitMode() {
  const { selectedActionFqn } = useWorkbench();
  return (
    <div className="grid grid-rows-2 h-full">
      <div className="overflow-auto p-4 border-b border-border">
        <h3 className="text-[11px] uppercase tracking-wider text-muted-foreground font-semibold mb-2">
          Java 본체 · 클릭하여 매핑
        </h3>
        <pre className="bg-muted border border-border p-3 rounded text-[12px] font-mono whitespace-pre overflow-x-auto leading-relaxed">
{`@Override
public ValidationResult validate() {
  if (priority < 1 || priority > 5)
    return fail("우선도 범위");
  if (spec.diameter > 200.0)  // ← 매핑 중
    return fail("긴급주문 직경 한도");
  return ok();
}`}
        </pre>
        <div className="mt-2 text-[11.5px] text-muted-foreground">
          (Java parser 출력 + anchor highlight 는 backend 분석 데이터 연결 시 표시 — Phase 1.5)
        </div>
      </div>
      <div className="overflow-auto p-4">
        <h3 className="text-[11px] uppercase tracking-wider text-muted-foreground font-semibold mb-2">
          Action 카드 — 매핑 슬롯
        </h3>
        <p className="text-muted-foreground text-[12px]">
          Action <code className="text-[11px]">{selectedActionFqn ?? "(선택 없음)"}</code> 의
          parameters / preconditions / anchor 슬롯 목록.
        </p>
      </div>
    </div>
  );
}

// Backward — BackwardMode.tsx 로 분리 (Phase 2a 완료)
