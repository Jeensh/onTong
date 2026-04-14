"use client";

import { useEffect, useRef, useState } from "react";

export interface MenuItemDef {
  label: string;
  icon?: React.ReactNode;
  action: () => void;
  visible?: boolean;   // default true — false hides the item entirely
  separator?: boolean;  // render separator before this item
}

interface ContextMenuProps {
  x: number;
  y: number;
  items: MenuItemDef[];
  onClose: () => void;
}

export function ContextMenu({ x, y, items, onClose }: ContextMenuProps) {
  const menuRef = useRef<HTMLDivElement>(null);
  const [pos, setPos] = useState({ x, y });

  // Position correction after mount
  useEffect(() => {
    const el = menuRef.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    const vw = window.innerWidth;
    const vh = window.innerHeight;
    let nx = x;
    let ny = y;
    // Flip horizontal if overflows right
    if (x + rect.width > vw - 8) nx = Math.max(8, x - rect.width);
    // Flip vertical if overflows bottom
    if (y + rect.height > vh - 8) ny = Math.max(8, y - rect.height);
    // Clamp to viewport
    nx = Math.min(nx, vw - rect.width - 8);
    ny = Math.min(ny, vh - rect.height - 8);
    setPos({ x: nx, y: ny });
  }, [x, y]);

  // Close on click outside or Escape
  useEffect(() => {
    const handleClick = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        onClose();
      }
    };
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("mousedown", handleClick);
    document.addEventListener("keydown", handleKey);
    return () => {
      document.removeEventListener("mousedown", handleClick);
      document.removeEventListener("keydown", handleKey);
    };
  }, [onClose]);

  const visibleItems = items.filter((item) => item.visible !== false);
  if (visibleItems.length === 0) return null;

  return (
    <div
      ref={menuRef}
      className="fixed z-50 min-w-[180px] rounded-md border bg-popover p-1 shadow-lg"
      style={{ left: pos.x, top: pos.y }}
    >
      {visibleItems.map((item, i) => (
        <div key={i}>
          {item.separator && i > 0 && (
            <div className="my-1 h-px bg-border" />
          )}
          <button
            className="flex w-full items-center gap-2 rounded-sm px-2 py-1.5 text-sm
                       hover:bg-accent hover:text-accent-foreground"
            onClick={() => {
              item.action();
              onClose();
            }}
          >
            {item.icon && (
              <span className="h-4 w-4 flex-shrink-0">{item.icon}</span>
            )}
            {item.label}
          </button>
        </div>
      ))}
    </div>
  );
}
