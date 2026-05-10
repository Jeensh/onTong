// Phase 7-E — Auto-PR 자바 방어 코드 자동 생성 API client.

const BASE = "/api/simulation/auto_pr";

export interface FailedCaseDto {
  case_id: string;
  description?: string;
  case_type?: "normal" | "boundary" | "error" | "performance";
  expected?: Record<string, unknown>;
  actual_output?: Record<string, unknown>;
}

export interface PatchSuggestion {
  rationale: string;
  patched_method: string;
  additional_imports: string[];
  confidence: number;
  method: "llm" | "fallback";
  risk_notes: string[];
}

export interface AutoPRSuggestRequest {
  java_path: string;
  method_name: string;
  class_name?: string;
  failures: FailedCaseDto[];
  prefer_llm?: boolean;
}

export interface AutoPRSuggestResponse {
  suggestion: PatchSuggestion;
  unified_diff: string;
  java_summary: {
    class_name: string;
    method_name: string;
    signature: string;
    lines: string;
    javadoc: string;
  };
}

export async function suggestPatch(req: AutoPRSuggestRequest): Promise<AutoPRSuggestResponse> {
  const r = await fetch(`${BASE}/suggest`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
  if (!r.ok) throw new Error(`suggestPatch ${r.status}: ${await r.text()}`);
  return r.json();
}

/** step_id → 자바 파일 경로 + 메서드 이름. heatmap.file_path 가 있으면 그걸 사용. */
export interface AutoPRTarget {
  java_path: string;
  method_name: string;
  class_name?: string;
}

const STEP_TO_TARGET: Record<string, AutoPRTarget> = {
  thickness: {
    java_path:
      "sample-repos/slab-design/slab-design-feature/src/main/java/com/example/slabdesign/feature/sd/process/working/action/SdThicknessAction.java",
    method_name: "execute",
    class_name: "SdThicknessAction",
  },
  slab_count: {
    java_path:
      "sample-repos/slab-design/slab-design-feature/src/main/java/com/example/slabdesign/feature/sd/process/working/action/SdSlabCountAction.java",
    method_name: "execute",
    class_name: "SdSlabCountAction",
  },
};

export function targetForStep(stepId: string | undefined | null): AutoPRTarget | null {
  if (!stepId) return null;
  return STEP_TO_TARGET[stepId] ?? null;
}
