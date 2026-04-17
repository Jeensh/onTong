"use client";

import dynamic from "next/dynamic";
import type { TabType } from "@/types";
import { MarkdownEditor } from "@/components/editors/MarkdownEditor";
import { SpreadsheetViewer } from "@/components/editors/SpreadsheetViewer";
import { ImageViewer } from "@/components/editors/ImageViewer";
import { PresentationViewer } from "@/components/editors/PresentationViewer";
import { MetadataTemplateEditor } from "@/components/editors/MetadataTemplateEditor";
import { UntaggedDashboard } from "@/components/editors/UntaggedDashboard";
import { ConflictDashboard } from "@/components/editors/ConflictDashboard";
import { DiffViewer } from "@/components/editors/DiffViewer";
import { PermissionEditor } from "@/components/admin/PermissionEditor";
import { ScoringDashboard } from "@/components/editors/ScoringDashboard";
import { MaintenanceDigest } from "@/components/editors/MaintenanceDigest";
import { ImageManagementPage } from "@/components/editors/ImageManagementPage";

const DocumentGraph = dynamic(
  () => import("@/components/editors/DocumentGraph").then((m) => m.DocumentGraph),
  { ssr: false, loading: () => <ViewerLoading label="그래프" /> },
);

const PdfViewer = dynamic(
  () => import("@/components/editors/PdfViewer").then((m) => m.PdfViewer),
  { ssr: false, loading: () => <ViewerLoading label="PDF" /> },
);

function ViewerLoading({ label }: { label: string }) {
  return (
    <div className="flex items-center justify-center h-full text-muted-foreground">
      <p className="text-sm">{label} 뷰어 로딩 중...</p>
    </div>
  );
}

interface FileRouterProps {
  filePath: string;
  fileType: TabType;
  tabId: string;
}

export function FileRouter({ filePath, fileType, tabId }: FileRouterProps) {
  switch (fileType) {
    case "markdown":
      return <MarkdownEditor filePath={filePath} tabId={tabId} />;
    case "spreadsheet":
      return <SpreadsheetViewer filePath={filePath} tabId={tabId} />;
    case "image":
      return <ImageViewer filePath={filePath} />;
    case "presentation":
      return <PresentationViewer filePath={filePath} />;
    case "pdf":
      return <PdfViewer filePath={filePath} />;
    case "metadata-templates":
      return <MetadataTemplateEditor tabId={tabId} />;
    case "untagged-dashboard":
      return <UntaggedDashboard />;
    case "conflict-dashboard":
      return <ConflictDashboard />;
    case "document-graph":
      return <DocumentGraph />;
    case "permission-editor":
      return <PermissionEditor />;
    case "scoring-dashboard":
      return <ScoringDashboard />;
    case "maintenance-digest":
      return <MaintenanceDigest />;
    case "image-management":
      return <ImageManagementPage />;
    case "document-compare": {
      // filePath format: __compare__pathA__pathB__
      const match = filePath.match(/^__compare__(.+?)__(.+?)__$/);
      if (match) {
        return <DiffViewer pathA={match[1]} pathB={match[2]} />;
      }
      return <div className="p-4 text-sm text-muted-foreground">비교할 문서가 지정되지 않았습니다.</div>;
    }
    default:
      return (
        <div className="flex items-center justify-center h-full text-muted-foreground">
          <p className="text-sm">지원하지 않는 파일 형식입니다</p>
        </div>
      );
  }
}
