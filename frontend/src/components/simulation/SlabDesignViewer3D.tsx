"use client";

// 3D Slab 뷰어 — @react-three/fiber + @react-three/drei + @react-spring/three
// 파라미터 변경 시 부드러운 보간 애니메이션, 상태별 색상 코딩, 분할수 시각화

import { useRef } from "react";
import { Canvas, useFrame } from "@react-three/fiber";
import { OrbitControls, Html } from "@react-three/drei";
import { useSpring, animated } from "@react-spring/three";
import * as THREE from "three";
import type { SlabSizeParams, SlabDesignResult } from "@/lib/simulation/types";

// ── 상수 ──────────────────────────────────────────────────────────────

const SCALE = 0.001;    // mm → three.js 단위
const GAP   = 0.04;     // 분할 조각 사이 간격

const STATUS_COLOR: Record<string, string> = {
  ok:          "#4A90D9",
  warning:     "#F5A623",
  error:       "#D0021B",
  calculating: "#7B68EE",
};

// ── 진동 효과 (에러 상태) ──────────────────────────────────────────────

function ShakingGroup({
  children,
  enabled,
}: {
  children: React.ReactNode;
  enabled: boolean;
}) {
  const groupRef = useRef<THREE.Group>(null!);
  useFrame(({ clock }) => {
    if (!groupRef.current) return;
    groupRef.current.position.x = enabled
      ? Math.sin(clock.elapsedTime * 22) * 0.035
      : THREE.MathUtils.lerp(groupRef.current.position.x, 0, 0.3);
  });
  return <group ref={groupRef}>{children}</group>;
}

// ── 단일 Slab 조각 ───────────────────────────────────────────────────

interface AnimatedPieceProps {
  targetW: number;
  targetH: number;
  targetD: number;
  color: string;
  yOffset: number;
  isError: boolean;
  label: string;
}

function AnimatedPiece({
  targetW, targetH, targetD, color, yOffset, isError, label,
}: AnimatedPieceProps) {
  const { scaleX, scaleY, scaleZ, col } = useSpring({
    scaleX: targetW,
    scaleY: targetH,
    scaleZ: targetD,
    col:    color,
    config: { mass: 1, tension: 180, friction: 28 },
  });

  return (
    <group position={[0, yOffset, 0]}>
      <ShakingGroup enabled={isError}>
        {/* 본체 */}
        <animated.mesh scale-x={scaleX} scale-y={scaleY} scale-z={scaleZ}>
          <boxGeometry args={[1, 1, 1]} />
          <animated.meshStandardMaterial
            color={col}
            metalness={0.55}
            roughness={0.35}
            transparent
            opacity={0.88}
          />
        </animated.mesh>

        {/* 와이어프레임 테두리 */}
        <animated.lineSegments scale-x={scaleX} scale-y={scaleY} scale-z={scaleZ}>
          <edgesGeometry args={[new THREE.BoxGeometry(1, 1, 1)]} />
          <lineBasicMaterial color="#ffffff" transparent opacity={0.1} />
        </animated.lineSegments>
      </ShakingGroup>

      {/* 단중 라벨 */}
      <Html position={[0, targetH / 2 + 0.14, 0]} center>
        <div
          style={{
            background: "rgba(15,23,42,0.82)",
            color: "#cbd5e1",
            fontSize: "10px",
            padding: "2px 7px",
            borderRadius: "4px",
            whiteSpace: "nowrap",
            pointerEvents: "none",
            border: "1px solid rgba(255,255,255,0.07)",
          }}
        >
          {label}
        </div>
      </Html>
    </group>
  );
}

// ── 치수 라벨 ─────────────────────────────────────────────────────────

function DimLabel({ position, text }: { position: [number, number, number]; text: string }) {
  return (
    <Html position={position} center>
      <div
        style={{
          color: "#475569",
          fontSize: "9px",
          whiteSpace: "nowrap",
          pointerEvents: "none",
          fontFamily: "monospace",
          userSelect: "none",
        }}
      >
        {text}
      </div>
    </Html>
  );
}

// ── 전체 Slab 그룹 ────────────────────────────────────────────────────

interface SlabGroupProps {
  params: SlabSizeParams;
  status: string;
  isCalculating: boolean;
}

function SlabGroup({ params, status, isCalculating }: SlabGroupProps) {
  const color = isCalculating
    ? STATUS_COLOR.calculating
    : STATUS_COLOR[status] ?? STATUS_COLOR.ok;

  const splitCount = Math.max(1, Math.min(5, params.split_count));
  const totalW = params.target_width  * SCALE;
  const totalH = params.thickness     * SCALE;
  const totalD = params.target_length * SCALE;

  // 각 조각 높이
  const pieceH = (totalH - GAP * (splitCount - 1)) / splitCount;
  const weightPerSplit = Math.round(params.unit_weight / splitCount);

  // 각 조각 Y 중심 위치
  const yOffsets = Array.from({ length: splitCount }, (_, i) => {
    const start = -totalH / 2 + pieceH / 2;
    return start + i * (pieceH + GAP);
  });

  const isError = status === "error" && !isCalculating;

  return (
    <group>
      {yOffsets.map((yOff, i) => (
        <AnimatedPiece
          key={i}
          targetW={totalW}
          targetH={pieceH}
          targetD={totalD}
          color={color}
          yOffset={yOff}
          isError={isError}
          label={`${weightPerSplit.toLocaleString()} kg`}
        />
      ))}

      {/* 치수 라벨 */}
      <DimLabel
        position={[totalW / 2 + 0.28, 0, 0]}
        text={`폭 ${params.target_width.toLocaleString()}mm`}
      />
      <DimLabel
        position={[0, totalH / 2 + 0.28, 0]}
        text={`두께 ${params.thickness}mm`}
      />
      <DimLabel
        position={[0, 0, totalD / 2 + 0.28]}
        text={`길이 ${params.target_length.toLocaleString()}mm`}
      />
    </group>
  );
}

// ── 씬 ────────────────────────────────────────────────────────────────

function Scene({ params, result, isCalculating }: {
  params: SlabSizeParams;
  result: SlabDesignResult | null;
  isCalculating: boolean;
}) {
  const status = isCalculating ? "calculating" : (result?.overall_status ?? "ok");
  return (
    <>
      <ambientLight intensity={0.7} />
      <directionalLight position={[5, 8, 5]} intensity={1.0} />
      <directionalLight position={[-4, -3, -4]} intensity={0.2} />
      <SlabGroup params={params} status={status} isCalculating={isCalculating} />
      <OrbitControls enablePan={false} minDistance={1.5} maxDistance={14} />
    </>
  );
}

// ── 상태 오버레이 ─────────────────────────────────────────────────────

function StatusOverlay({
  result, isCalculating,
}: { result: SlabDesignResult | null; isCalculating: boolean }) {
  if (isCalculating) {
    return (
      <div className="absolute bottom-3 left-3 bg-indigo-900/80 text-indigo-200 text-xs px-2 py-1 rounded animate-pulse">
        계산 중…
      </div>
    );
  }
  if (!result) return null;

  const cfg = {
    ok:      { cls: "bg-blue-900/80 text-blue-200",    label: "✅ 설계 가능" },
    warning: { cls: "bg-yellow-900/80 text-yellow-200", label: "⚠️ 경고" },
    error:   { cls: "bg-red-900/80 text-red-200",       label: "🔴 설계 불가" },
  }[result.overall_status] ?? { cls: "bg-slate-800/80 text-slate-400", label: "-" };

  return (
    <div className="absolute bottom-3 left-3 space-y-1 pointer-events-none">
      <div className={`text-xs px-2 py-1 rounded ${cfg.cls}`}>{cfg.label}</div>
      <div className="bg-slate-900/80 text-slate-300 text-[10px] px-2 py-1 rounded">
        {result.summary.split_count}분할 · {result.summary.slab_count}매 ·{" "}
        {result.summary.unit_weight_per_split.toLocaleString()}kg/분할
      </div>
    </div>
  );
}

// ── 메인 컴포넌트 ─────────────────────────────────────────────────────

export function SlabDesignViewer3D({
  params, result, isCalculating,
}: { params: SlabSizeParams; result: SlabDesignResult | null; isCalculating: boolean }) {
  return (
    <div className="relative w-full h-full bg-slate-950 rounded overflow-hidden">
      <div className="absolute top-2 left-3 z-10 text-[10px] text-slate-600 font-medium select-none">
        3D Slab Viewer · 마우스로 회전
      </div>
      <Canvas camera={{ position: [2.2, 1.4, 4.5], fov: 45 }}>
        <Scene params={params} result={result} isCalculating={isCalculating} />
      </Canvas>
      <StatusOverlay result={result} isCalculating={isCalculating} />
    </div>
  );
}
