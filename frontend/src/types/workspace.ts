// ── Workspace ─────────────────────────────────────────────────────────

export type FileType =
  | "markdown"
  | "spreadsheet"
  | "presentation"
  | "pdf"
  | "image"
  | "unknown";

/** Virtual tab types for non-file workspace panels */
export type VirtualTabType =
  | "metadata-templates"
  | "untagged-dashboard"
  | "conflict-dashboard"
  | "document-compare"
  | "document-graph"
  | "permission-editor";

export type TabType = FileType | VirtualTabType;

export interface Tab {
  id: string;
  filePath: string;
  fileType: TabType;
  title: string;
  isDirty: boolean;
}
