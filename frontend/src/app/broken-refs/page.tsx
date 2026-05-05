import { BrokenRefsContent } from "@/components/sections/wiki/BrokenRefsContent";

export default function BrokenRefsPage() {
  return (
    <div className="container mx-auto max-w-5xl p-6">
      <header className="mb-6">
        <h1 className="text-2xl font-bold">깨진 참조 리포트</h1>
        <p className="text-sm text-muted-foreground mt-1">
          ReferenceIndex 가 감지한 broken references. 대상 문서가 존재하지 않는 모든 참조를 표시합니다.
          클릭 시 참조하는 문서(source) 를 엽니다.
        </p>
      </header>
      <BrokenRefsContent />
    </div>
  );
}
