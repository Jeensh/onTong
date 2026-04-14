"use client";

import { useState } from "react";
import { ChevronDown, ChevronRight, Zap } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
  DialogDescription,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { createSkill } from "@/lib/api/skills";
import { ReferencedDocsPicker } from "./ReferencedDocsPicker";
import { toast } from "sonner";

interface SkillCreateDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onCreated: (path: string) => void;
  categories: string[];
}

export function SkillCreateDialog({
  open,
  onOpenChange,
  onCreated,
  categories,
}: SkillCreateDialogProps) {
  // Basic fields
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [trigger, setTrigger] = useState("");
  const [icon, setIcon] = useState("⚡");
  const [scope, setScope] = useState<"personal" | "shared">("personal");
  const [category, setCategory] = useState("");
  const [priority, setPriority] = useState(5);

  // 6-Layer fields
  const [role, setRole] = useState("");
  const [instructions, setInstructions] = useState("");
  const [workflow, setWorkflow] = useState("");
  const [checklist, setChecklist] = useState("");
  const [outputFormat, setOutputFormat] = useState("");
  const [selfRegulation, setSelfRegulation] = useState("");
  const [referencedDocs, setReferencedDocs] = useState<string[]>([]);
  const [allowedTools, setAllowedTools] = useState<string[]>([]);

  const [showAdvanced, setShowAdvanced] = useState(false);
  const [creating, setCreating] = useState(false);

  const resetForm = () => {
    setTitle(""); setDescription(""); setTrigger(""); setIcon("⚡");
    setScope("personal"); setCategory(""); setPriority(5);
    setRole(""); setInstructions(""); setWorkflow("");
    setChecklist(""); setOutputFormat(""); setSelfRegulation("");
    setReferencedDocs([]); setAllowedTools([]); setShowAdvanced(false);
  };

  const handleCreate = async () => {
    if (!title.trim()) return;
    setCreating(true);
    try {
      const triggers = trigger.split(",").map((s) => s.trim()).filter(Boolean);
      const skill = await createSkill({
        title: title.trim(),
        description: description.trim(),
        trigger: triggers,
        icon: icon || "⚡",
        scope,
        category: category.trim(),
        priority,
        instructions: instructions.trim() || undefined,
        role: role.trim() || undefined,
        workflow: workflow.trim() || undefined,
        checklist: checklist.trim() || undefined,
        output_format: outputFormat.trim() || undefined,
        self_regulation: selfRegulation.trim() || undefined,
        referenced_docs: referencedDocs.length > 0 ? referencedDocs : undefined,
        allowed_tools: allowedTools.length > 0 ? allowedTools : undefined,
      });
      onCreated(skill.path);
      resetForm();
      onOpenChange(false);
    } catch (err) {
      toast.error(`스킬 생성 실패: ${(err as Error).message}`);
    } finally {
      setCreating(false);
    }
  };

  const inputClass = "w-full text-xs px-2 py-1.5 rounded border bg-background";
  const labelClass = "text-xs font-medium text-muted-foreground";
  const textareaClass = "w-full text-xs px-2 py-1.5 rounded border bg-background resize-y font-mono";

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-2xl max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Zap className="h-4 w-4 text-primary" />
            스킬 만들기
          </DialogTitle>
          <DialogDescription>
            AI가 특정 주제에 대해 일관된 방식으로 답변하도록 설정합니다.
            <br />
            <span className="text-muted-foreground/70">이름과 설명만 입력해도 바로 사용할 수 있습니다. 고급 설정은 나중에 추가해도 됩니다.</span>
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-3">
          {/* Basic fields */}
          <div className="space-y-2">
            <div>
              <label className={labelClass}>스킬 이름 *</label>
              <input value={title} onChange={(e) => setTitle(e.target.value)}
                placeholder="예: 출장비 정산 안내" className={inputClass} />
            </div>
            <div>
              <label className={labelClass}>한 줄 설명</label>
              <input value={description} onChange={(e) => setDescription(e.target.value)}
                placeholder="이 스킬이 하는 일을 간단히 적으세요" className={inputClass} />
            </div>
            <div>
              <label className={labelClass}>트리거 키워드 <span className="font-normal text-muted-foreground/60">— 이 단어가 포함되면 자동 제안</span></label>
              <input value={trigger} onChange={(e) => setTrigger(e.target.value)}
                placeholder="쉼표로 구분 (예: 출장비, 정산, 경비)" className={inputClass} />
            </div>
            <div className="flex items-center gap-2">
              <div className="w-16">
                <label className={labelClass}>아이콘</label>
                <input value={icon} onChange={(e) => setIcon(e.target.value)}
                  className={`${inputClass} text-center`} />
              </div>
              <div className="flex-1">
                <label className={labelClass}>범위</label>
                <select value={scope} onChange={(e) => setScope(e.target.value as "personal" | "shared")}
                  className={inputClass}>
                  <option value="personal">개인</option>
                  <option value="shared">공용</option>
                </select>
              </div>
              <div className="flex-1">
                <label className={labelClass}>카테고리</label>
                <input value={category} onChange={(e) => setCategory(e.target.value)}
                  placeholder="예: HR" list="dialog-skill-categories" className={inputClass} />
                <datalist id="dialog-skill-categories">
                  {categories.map((c) => <option key={c} value={c} />)}
                </datalist>
              </div>
              <div className="w-20">
                <label className={labelClass}>우선순위</label>
                <input type="number" min={1} max={10} value={priority}
                  onChange={(e) => setPriority(Math.max(1, Math.min(10, Number(e.target.value) || 5)))}
                  className={`${inputClass} text-center`} />
              </div>
            </div>
          </div>

          {/* Divider */}
          <div className="border-t" />

          {/* Advanced toggle */}
          <button
            type="button"
            onClick={() => setShowAdvanced((v) => !v)}
            className="flex items-center gap-1 text-xs font-medium text-muted-foreground hover:text-foreground"
          >
            {showAdvanced ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
            고급 설정 (6-Layer)
          </button>

          {showAdvanced && (
            <div className="space-y-3 pl-1 border-l-2 border-muted ml-1">
              <p className="text-[11px] text-muted-foreground/70 -mt-1">
                각 항목은 선택 사항입니다. 필요한 것만 채우세요.
              </p>
              <div>
                <label className={labelClass}>역할 (Role) <span className="font-normal text-muted-foreground/60">— AI의 페르소나와 톤</span></label>
                <textarea value={role} onChange={(e) => setRole(e.target.value)}
                  rows={3} className={textareaClass}
                  placeholder={"AI가 어떤 역할/페르소나로 답변할지 정의하세요.\n- 톤: (예: 친절하고 환영하는 분위기)\n- 핵심 목표: (예: 사용자의 불안감을 줄이는 것)"} />
              </div>
              <div>
                <label className={labelClass}>지시사항 (Instructions) <span className="font-normal text-muted-foreground/60">— 핵심 답변 규칙</span></label>
                <textarea value={instructions} onChange={(e) => setInstructions(e.target.value)}
                  rows={4} className={textareaClass}
                  placeholder={"참조 문서를 바탕으로 사용자의 질문에 답변하세요.\n1. (답변에 포함할 내용을 구체적으로 적으세요)\n2. (답변 형식을 지정하세요)\n3. (예외 사항이나 주의점을 포함하세요)"} />
              </div>
              <div>
                <label className={labelClass}>워크플로우 (Workflow) <span className="font-normal text-muted-foreground/60">— 단계별 진행이 필요할 때</span></label>
                <textarea value={workflow} onChange={(e) => setWorkflow(e.target.value)}
                  rows={3} className={textareaClass}
                  placeholder={"답변을 단계별로 진행할 때 정의하세요.\n### 1단계: (단계 이름)\n### 2단계: (단계 이름)"} />
              </div>
              <div>
                <label className={labelClass}>체크리스트 (Checklist) <span className="font-normal text-muted-foreground/60">— 반드시 포함/금지할 내용</span></label>
                <textarea value={checklist} onChange={(e) => setChecklist(e.target.value)}
                  rows={3} className={textareaClass}
                  placeholder={"### 반드시 포함\n- (예: 담당 부서 연락처)\n### 언급 금지\n- (예: 급여 정보)"} />
              </div>
              <div>
                <label className={labelClass}>출력 형식 (Output Format) <span className="font-normal text-muted-foreground/60">— 답변의 구조를 지정</span></label>
                <textarea value={outputFormat} onChange={(e) => setOutputFormat(e.target.value)}
                  rows={3} className={textareaClass}
                  placeholder={"답변은 다음 구조로 작성하세요:\n1. 요약 (3줄 이내)\n2. 상세 내용\n3. 추가 안내"} />
              </div>
              <div>
                <label className={labelClass}>제한사항 (Self-Regulation) <span className="font-normal text-muted-foreground/60">— 길이, 범위 등 제한</span></label>
                <textarea value={selfRegulation} onChange={(e) => setSelfRegulation(e.target.value)}
                  rows={3} className={textareaClass}
                  placeholder={"- 답변 길이: (예: 최대 500자)\n- 참조 문서에 없는 내용은 추측하지 마세요"} />
              </div>
              <div>
                <label className={labelClass}>참조 문서</label>
                <ReferencedDocsPicker value={referencedDocs} onChange={setReferencedDocs} />
              </div>
              <div>
                <label className={labelClass}>허용 도구 (Allowed Tools)</label>
                <p className="text-[10px] text-muted-foreground mb-1">
                  이 스킬이 사용할 수 있는 내장 도구를 선택하세요. 미선택 시 기본 설정을 사용합니다.
                </p>
                <div className="grid grid-cols-2 gap-1">
                  {[
                    { id: "wiki_search", label: "위키 검색" },
                    { id: "wiki_read", label: "문서 읽기" },
                    { id: "llm_generate", label: "LLM 답변 생성" },
                    { id: "conflict_check", label: "충돌 감지" },
                    { id: "query_augment", label: "쿼리 보강" },
                    { id: "wiki_write", label: "문서 생성" },
                    { id: "wiki_edit", label: "문서 편집" },
                  ].map((tool) => (
                    <label key={tool.id} className="flex items-center gap-1.5 text-xs cursor-pointer">
                      <input
                        type="checkbox"
                        checked={allowedTools.includes(tool.id)}
                        onChange={(e) => {
                          if (e.target.checked) {
                            setAllowedTools((prev) => [...prev, tool.id]);
                          } else {
                            setAllowedTools((prev) => prev.filter((t) => t !== tool.id));
                          }
                        }}
                        className="rounded"
                      />
                      <span>{tool.label}</span>
                      <span className="text-muted-foreground">({tool.id})</span>
                    </label>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            취소
          </Button>
          <Button onClick={handleCreate} disabled={creating || !title.trim()}>
            {creating ? "생성 중..." : "생성"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
