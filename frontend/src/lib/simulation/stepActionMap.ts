/**
 * step_id → ontology action_fqn 매핑
 *
 * 옛 storage API 기반 panel (SandboxPanel / RunHistoryPanel / RegressionPanel)
 * 의 step_id 를 Section 2 ontology 의 실 sub-action 으로 변환.
 *
 * Source: `action.scm.슬랩설계_실행` 의 delegates_to_tree 21-step (실 ontology DB).
 *   curl /api/ontology/actions/action.scm.슬랩설계_실행/delegates-to-tree
 */

export const STEP_TO_ACTION: Record<string, string> = {
  // root workflow
  pipeline: "action.scm.슬랩설계_실행",
  pipeline_full: "action.scm.슬랩설계_실행",

  // 21-step sub-actions
  validator: "action.scm.order.정합성_검증",
  productivity: "action.scm.product.cumulative_productivity",
  thickness: "action.scm.thickness_실행",
  width_range: "action.scm.width_range_실행",
  length_range: "action.scm.length_range_실행",
  second_wgt: "action.scm.second_wgt_low_실행",
  max_split: "action.scm.max_split_count_실행",
  split_range: "action.scm.split_range_실행",
  slab_count: "action.scm.slab.slab_count_실행",
  slab_weight: "action.scm.slab.initial_slab_wgt_실행",
  final_width_range: "action.scm.final_width_range_실행",
  final_length_range: "action.scm.final_length_range_실행",
  target_size: "action.scm.target_width_실행",
};

/** step_id 가 매핑 표에 없으면 root workflow 로 fallback. */
export function resolveActionFqn(stepId: string | null | undefined): string {
  if (!stepId) return "action.scm.슬랩설계_실행";
  return STEP_TO_ACTION[stepId] ?? "action.scm.슬랩설계_실행";
}
