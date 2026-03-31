"use client";

import { useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";
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

  const [showAdvanced, setShowAdvanced] = useState(false);
  const [creating, setCreating] = useState(false);

  const resetForm = () => {
    setTitle(""); setDescription(""); setTrigger(""); setIcon("⚡");
    setScope("personal"); setCategory(""); setPriority(5);
    setRole(""); setInstructions(""); setWorkflow("");
    setChecklist(""); setOutputFormat(""); setSelfRegulation("");
    setReferencedDocs([]); setShowAdvanced(false);
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
          <DialogTitle>스킬 생성 (고급)</DialogTitle>
          <DialogDescription>
            6-Layer 구조로 AI 스킬을 상세하게 정의합니다.
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
              <label className={labelClass}>트리거 키워드</label>
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
              <div>
                <label className={labelClass}>역할 (Role)</label>
                <textarea value={role} onChange={(e) => setRole(e.target.value)}
                  rows={3} className={textareaClass}
                  placeholder={"AI가 어떤 역할/페르소나로 답변할지 정의하세요.\n- 톤: (예: 친절하고 환영하는 분위기)\n- 핵심 목표: (예: 사용자의 불안감을 줄이는 것)"} />
              </div>
              <div>
                <label className={labelClass}>지시사항 (Instructions)</label>
                <textarea value={instructions} onChange={(e) => setInstructions(e.target.value)}
                  rows={4} className={textareaClass}
                  placeholder={"참조 문서를 바탕으로 사용자의 질문에 답변하세요.\n1. (답변에 포함할 내용을 구체적으로 적으세요)\n2. (답변 형식을 지정하세요)\n3. (예외 사항이나 주의점을 포함하세요)"} />
              </div>
              <div>
                <label className={labelClass}>워크플로우 (Workflow)</label>
                <textarea value={workflow} onChange={(e) => setWorkflow(e.target.value)}
                  rows={3} className={textareaClass}
                  placeholder={"답변을 단계별로 진행할 때 정의하세요.\n### 1단계: (단계 이름)\n### 2단계: (단계 이름)"} />
              </div>
              <div>
                <label className={labelClass}>체크리스트 (Checklist)</label>
                <textarea value={checklist} onChange={(e) => setChecklist(e.target.value)}
                  rows={3} className={textareaClass}
                  placeholder={"### 반드시 포함\n- (예: 담당 부서 연락처)\n### 언급 금지\n- (예: 급여 정보)"} />
              </div>
              <div>
                <label className={labelClass}>출력 형식 (Output Format)</label>
                <textarea value={outputFormat} onChange={(e) => setOutputFormat(e.target.value)}
                  rows={3} className={textareaClass}
                  placeholder={"답변은 다음 구조로 작성하세요:\n1. 요약 (3줄 이내)\n2. 상세 내용\n3. 추가 안내"} />
              </div>
              <div>
                <label className={labelClass}>제한사항 (Self-Regulation)</label>
                <textarea value={selfRegulation} onChange={(e) => setSelfRegulation(e.target.value)}
                  rows={3} className={textareaClass}
                  placeholder={"- 답변 길이: (예: 최대 500자)\n- 참조 문서에 없는 내용은 추측하지 마세요"} />
              </div>
              <div>
                <label className={labelClass}>참조 문서</label>
                <ReferencedDocsPicker value={referencedDocs} onChange={setReferencedDocs} />
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
