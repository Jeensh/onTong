// Section 3 — simulation lib barrel.
// (2026-05-10) main 정리로 ./types, ./useSlabSimulator 제거됨.
// FieldDiff 는 differentialApi / transpileApi 에서 동시 정의 → 명시적 re-export 로 충돌 회피.

export * from "./agentApi";
export * from "./storageApi";
export {
  type DifferentialStatus,
  type DifferentialResult,
  type FieldDiff,
  getDifferentialStatus,
  runDifferential,
} from "./differentialApi";
export {
  type FieldDiff as TranspileFieldDiff,
  type MethodInfo,
  type LineOrigin,
  type PythonStepDraft,
  type EquivalenceReport,
  type PreviewResponse,
  type PreviewRequest,
  listMethods,
  previewTranspile,
} from "./transpileApi";
export * from "./autoPrApi";
export * from "./seedApi";
export * from "./stepLabels";
