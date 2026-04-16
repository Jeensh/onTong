"use client";

import { useRef, useMemo, useEffect } from "react";
import type { SlabState } from "@/lib/simulation/types";

interface SlabViewer3DProps {
  slabs: SlabState[];
}

// Status colors for slabs
const STATUS_COLORS = {
  normal: "#22c55e",
  error: "#ef4444",
  warning: "#f59e0b",
  adjusted: "#3b82f6",
  optimal: "#8b5cf6",
};

// Canvas-based 3D-perspective slab renderer (no Three.js SSR issues)
export function SlabViewer3D({ slabs }: SlabViewer3DProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const animFrameRef = useRef<number>(0);
  const rotationRef = useRef(0);
  const animatingRef = useRef(false);

  const hasSlabs = slabs.length > 0;

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    // Check if any slab is animating (split animation)
    const anyAnimating = slabs.some((s) => s.animating);
    if (anyAnimating && !animatingRef.current) {
      animatingRef.current = true;
    }

    let animSplit = 0;
    let lastTime = 0;

    const draw = (timestamp: number) => {
      const dt = timestamp - lastTime;
      lastTime = timestamp;

      // Slow auto-rotation
      rotationRef.current += 0.003;

      // Split animation progress
      if (anyAnimating && animSplit < 1) {
        animSplit = Math.min(1, animSplit + dt / 1500);
      }

      const W = canvas.width;
      const H = canvas.height;
      ctx.clearRect(0, 0, W, H);

      // Dark background
      ctx.fillStyle = "#0f172a";
      ctx.fillRect(0, 0, W, H);

      if (!hasSlabs) {
        // Placeholder
        ctx.fillStyle = "rgba(148, 163, 184, 0.3)";
        ctx.fillRect(W / 2 - 80, H / 2 - 30, 160, 60);
        ctx.fillStyle = "#94a3b8";
        ctx.font = "12px sans-serif";
        ctx.textAlign = "center";
        ctx.fillText("Slab 시각화", W / 2, H / 2 - 5);
        ctx.font = "10px sans-serif";
        ctx.fillStyle = "#64748b";
        ctx.fillText("에이전트 실행 시 표시됩니다", W / 2, H / 2 + 12);
        animFrameRef.current = requestAnimationFrame(draw);
        return;
      }

      // Draw each slab
      const spacing = W / (slabs.length + 1);
      slabs.forEach((slab, idx) => {
        const cx = spacing * (idx + 1);
        const cy = H / 2;

        // Normalize dimensions for display
        const maxW = 150;
        const displayW = Math.max(40, Math.min(maxW, (slab.width / 1800) * maxW));
        const displayH = Math.max(20, Math.min(60, (slab.thickness / 300) * 60));
        const displayD = Math.max(60, Math.min(120, (slab.length / 12000) * 120));

        const color = STATUS_COLORS[slab.status] ?? "#9ca3af";

        // Pulsing effect for error
        const pulse = slab.status === "error"
          ? 0.7 + 0.3 * Math.sin(timestamp / 300)
          : 1;

        // 3D perspective box (isometric-like)
        const angle = rotationRef.current;
        const cos = Math.cos(angle);
        const sin = Math.sin(angle);

        // If animating (split), draw multiple pieces
        if (slab.animating && slab.split_count && slab.split_count > 1) {
          const n = slab.split_count;
          const pieceH = displayH * 0.8;
          const gap = displayH * 0.3 * animSplit;
          const totalH = pieceH * n + gap * (n - 1);
          const startY = cy - totalH / 2;

          for (let i = 0; i < n; i++) {
            const pieceY = startY + i * (pieceH + gap);
            drawIsometricBox(ctx, cx, pieceY + pieceH / 2, displayW * cos, pieceH, displayD * 0.4, color, pulse);
          }
        } else {
          drawIsometricBox(ctx, cx, cy, displayW * cos, displayH, displayD * 0.4, color, pulse);
        }

        // Status badge
        const badgeColor = STATUS_COLORS[slab.status] ?? "#9ca3af";
        ctx.fillStyle = badgeColor + "33";
        ctx.strokeStyle = badgeColor;
        ctx.lineWidth = 1;
        const badgeW = 80;
        const badgeX = cx - badgeW / 2;
        const badgeY = cy + displayH / 2 + 30;
        roundRect(ctx, badgeX, badgeY, badgeW, 18, 3);
        ctx.fill();
        ctx.stroke();

        ctx.fillStyle = badgeColor;
        ctx.font = "bold 9px sans-serif";
        ctx.textAlign = "center";
        ctx.fillText(slab.id, cx, badgeY + 12);

        // Dimension labels
        ctx.fillStyle = "#94a3b8";
        ctx.font = "9px sans-serif";
        ctx.fillText(`${slab.width}mm × ${slab.length}mm`, cx, badgeY + 28);

        if (slab.split_count && slab.split_count > 1) {
          ctx.fillStyle = STATUS_COLORS[slab.status] ?? "#9ca3af";
          ctx.font = "bold 9px sans-serif";
          ctx.fillText(`÷${slab.split_count}`, cx, badgeY + 40);
        }

        // Satisfaction rate for scenario C
        if (slab.label && slab.label.includes("만족률")) {
          const match = slab.label.match(/만족률\s*(\d+)%/);
          if (match) {
            const pct = parseInt(match[1]) / 100;
            const barW = 70;
            const barX = cx - barW / 2;
            const barY = badgeY + 46;

            ctx.fillStyle = "#1e293b";
            roundRect(ctx, barX, barY, barW, 6, 3);
            ctx.fill();

            const fillColor = pct >= 0.8 ? "#22c55e" : pct >= 0.6 ? "#f59e0b" : "#ef4444";
            ctx.fillStyle = fillColor;
            roundRect(ctx, barX, barY, barW * pct, 6, 3);
            ctx.fill();

            ctx.fillStyle = "#94a3b8";
            ctx.font = "8px sans-serif";
            ctx.fillText(`만족률 ${(pct * 100).toFixed(0)}%`, cx, barY + 16);
          }
        }
      });

      animFrameRef.current = requestAnimationFrame(draw);
    };

    animFrameRef.current = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(animFrameRef.current);
  }, [slabs, hasSlabs]);

  return (
    <div className="w-full h-full bg-slate-900 rounded relative overflow-hidden">
      {/* Title */}
      <div className="absolute top-2 left-2 z-10">
        <span className="text-[10px] text-slate-400 font-medium">3D Slab Viewer</span>
      </div>

      {/* Status legend */}
      {hasSlabs && (
        <div className="absolute top-2 right-2 z-10 bg-slate-800/80 rounded p-1.5 text-[9px] space-y-1">
          {Object.entries(STATUS_COLORS).map(([status, color]) => (
            <div key={status} className="flex items-center gap-1">
              <div className="w-2 h-2 rounded-sm" style={{ backgroundColor: color }} />
              <span className="text-slate-300 capitalize">{status}</span>
            </div>
          ))}
        </div>
      )}

      <canvas
        ref={canvasRef}
        className="w-full h-full"
        width={600}
        height={320}
        style={{ display: "block" }}
      />
    </div>
  );
}

// Helper: draw isometric box on canvas
function drawIsometricBox(
  ctx: CanvasRenderingContext2D,
  cx: number,
  cy: number,
  w: number,
  h: number,
  d: number,
  color: string,
  alpha: number = 1
) {
  const hex = hexToRgb(color);
  if (!hex) return;
  const { r, g, b } = hex;

  // Top face
  ctx.beginPath();
  ctx.moveTo(cx - w / 2, cy - h / 2);
  ctx.lineTo(cx + w / 2, cy - h / 2);
  ctx.lineTo(cx + w / 2 + d * 0.5, cy - h / 2 - d * 0.3);
  ctx.lineTo(cx - w / 2 + d * 0.5, cy - h / 2 - d * 0.3);
  ctx.closePath();
  ctx.fillStyle = `rgba(${Math.min(255, r + 40)},${Math.min(255, g + 40)},${Math.min(255, b + 40)},${alpha})`;
  ctx.fill();
  ctx.strokeStyle = `rgba(${r},${g},${b},0.5)`;
  ctx.lineWidth = 0.5;
  ctx.stroke();

  // Front face
  ctx.beginPath();
  ctx.moveTo(cx - w / 2, cy - h / 2);
  ctx.lineTo(cx + w / 2, cy - h / 2);
  ctx.lineTo(cx + w / 2, cy + h / 2);
  ctx.lineTo(cx - w / 2, cy + h / 2);
  ctx.closePath();
  ctx.fillStyle = `rgba(${r},${g},${b},${alpha})`;
  ctx.fill();
  ctx.strokeStyle = `rgba(${r},${g},${b},0.5)`;
  ctx.stroke();

  // Right face
  ctx.beginPath();
  ctx.moveTo(cx + w / 2, cy - h / 2);
  ctx.lineTo(cx + w / 2 + d * 0.5, cy - h / 2 - d * 0.3);
  ctx.lineTo(cx + w / 2 + d * 0.5, cy + h / 2 - d * 0.3);
  ctx.lineTo(cx + w / 2, cy + h / 2);
  ctx.closePath();
  ctx.fillStyle = `rgba(${Math.max(0, r - 40)},${Math.max(0, g - 40)},${Math.max(0, b - 40)},${alpha})`;
  ctx.fill();
  ctx.strokeStyle = `rgba(${r},${g},${b},0.5)`;
  ctx.stroke();
}

function hexToRgb(hex: string) {
  const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
  return result
    ? {
        r: parseInt(result[1], 16),
        g: parseInt(result[2], 16),
        b: parseInt(result[3], 16),
      }
    : null;
}

function roundRect(
  ctx: CanvasRenderingContext2D,
  x: number, y: number, w: number, h: number, r: number
) {
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.lineTo(x + w - r, y);
  ctx.quadraticCurveTo(x + w, y, x + w, y + r);
  ctx.lineTo(x + w, y + h - r);
  ctx.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
  ctx.lineTo(x + r, y + h);
  ctx.quadraticCurveTo(x, y + h, x, y + h - r);
  ctx.lineTo(x, y + r);
  ctx.quadraticCurveTo(x, y, x + r, y);
  ctx.closePath();
}
