// 공통 Plotly 테마 — Section 3 차트 (ResultChart / ImpactPanel / 기타) 일관 적용용.
//
// 정책
// ----
// 1. paper_bgcolor 는 카드 배경에 녹이기 (transparent) — 카드 border 가 차트 외곽 역할.
// 2. plot_bgcolor 는 살짝 회색 (slate-400 6%) — 차트 영역이 카드와 구분되어 보이도록.
// 3. xaxis / yaxis 는 showline + linecolor + tick + grid 명시 — "축이 없는 그래프" 방지.
// 4. bar / histogram 의 marker 에는 항상 marker.line 으로 outline 추가.
// 5. light / dark 모두에서 보이는 중성 회색 (slate-400 alpha) 사용.

import type { Layout, ScatterMarkerLine } from "plotly.js";

// 축 / 그리드 / 폰트 색 — slate-400 기준 알파만 조절
const AXIS_LINE = "rgba(100,116,139,0.55)"; // slate-500 55%
const GRID_LINE = "rgba(148,163,184,0.18)"; // slate-400 18%
const TICK_FONT = "rgba(100,116,139,0.85)";
const PLOT_FILL = "rgba(148,163,184,0.06)"; // slate-400 6% — 영역 명확화

// 시리즈 기본 색 — Tailwind 토큰과 정렬
export const PLOT_COLORS = {
  primary: "#3b82f6", // blue-500
  primaryDeep: "#1d4ed8", // blue-700 (테두리)
  accent: "#8b5cf6", // violet-500
  accentDeep: "#6d28d9", // violet-700
  emerald: "#10b981",
  emeraldDeep: "#047857",
  amber: "#f59e0b",
  amberDeep: "#b45309",
  red: "#ef4444",
  redDeep: "#b91c1c",
  slate: "#64748b",
  slateDeep: "#334155",
} as const;

const _axisShared = {
  showline: true,
  linecolor: AXIS_LINE,
  linewidth: 1.2,
  showgrid: true,
  gridcolor: GRID_LINE,
  gridwidth: 1,
  zeroline: false,
  ticks: "outside" as const,
  tickcolor: AXIS_LINE,
  ticklen: 4,
  tickwidth: 1,
  tickfont: { size: 10, color: TICK_FONT },
};

/**
 * 차트 공통 layout 베이스. 사용처에서 height / margin / barmode / legend 만 override.
 */
export const PLOT_LAYOUT_BASE: Partial<Layout> = {
  autosize: true,
  paper_bgcolor: "rgba(0,0,0,0)", // 카드 배경에 녹임 (카드 border 가 외곽)
  plot_bgcolor: PLOT_FILL, // plot 영역만 살짝 회색
  font: { size: 10, color: TICK_FONT },
  xaxis: { ..._axisShared },
  yaxis: { ..._axisShared },
  margin: { l: 40, r: 16, t: 8, b: 36 },
  hoverlabel: {
    bgcolor: "rgba(15,23,42,0.92)",
    bordercolor: AXIS_LINE,
    font: { color: "#f8fafc", size: 11 },
  },
};

/**
 * bar / histogram trace 에 항상 적용할 marker outline.
 * (`...marker, line: outline` 형태로 사용)
 */
export function barOutline(strokeHex: string): ScatterMarkerLine {
  return { color: strokeHex, width: 1 };
}

/** Sankey 의 node 외곽선 — 두꺼워야 카드 안에서 도드라짐. */
export const SANKEY_NODE_LINE = {
  color: "rgba(51,65,85,0.85)", // slate-700 알파
  width: 1.2,
};

/** Sankey link 의 기본 외곽선. */
export const SANKEY_LINK_LINE = {
  color: "rgba(100,116,139,0.25)",
  width: 0.5,
};
