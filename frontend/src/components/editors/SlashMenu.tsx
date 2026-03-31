"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import type { Editor } from "@tiptap/react";
import {
  SLASH_COMMANDS,
  getSlashPluginKey,
  type SlashMenuState,
} from "@/lib/tiptap/slashCommand";

interface SlashMenuProps {
  editor: Editor;
}

export function SlashMenu({ editor }: SlashMenuProps) {
  const [menuState, setMenuState] = useState<SlashMenuState>({
    active: false,
    query: "",
    range: { from: 0, to: 0 },
    top: 0,
    left: 0,
  });
  const [selectedIndex, setSelectedIndex] = useState(0);
  const menuRef = useRef<HTMLDivElement>(null);

  // Watch plugin state
  useEffect(() => {
    const key = getSlashPluginKey();

    function update() {
      const state = key.getState(editor.state) as SlashMenuState | undefined;
      if (state) {
        setMenuState(state);
        if (state.active) setSelectedIndex(0);
      }
    }

    editor.on("transaction", update);
    return () => {
      editor.off("transaction", update);
    };
  }, [editor]);

  const filtered = useMemo(() => {
    if (!menuState.query) return SLASH_COMMANDS;
    const q = menuState.query.toLowerCase();
    return SLASH_COMMANDS.filter(
      (cmd) =>
        cmd.title.toLowerCase().includes(q) ||
        cmd.description.toLowerCase().includes(q)
    );
  }, [menuState.query]);

  // Keyboard navigation
  useEffect(() => {
    if (!menuState.active) return;

    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === "ArrowDown") {
        e.preventDefault();
        setSelectedIndex((i) => (i + 1) % filtered.length);
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        setSelectedIndex((i) => (i - 1 + filtered.length) % filtered.length);
      } else if (e.key === "Enter") {
        e.preventDefault();
        const cmd = filtered[selectedIndex];
        if (cmd) {
          cmd.command({ editor, range: menuState.range });
          // Close menu
          const key = getSlashPluginKey();
          editor.view.dispatch(
            editor.state.tr.setMeta(key, { active: false } as SlashMenuState)
          );
        }
      }
    }

    window.addEventListener("keydown", handleKeyDown, true);
    return () => window.removeEventListener("keydown", handleKeyDown, true);
  }, [menuState.active, menuState.range, filtered, selectedIndex, editor]);

  if (!menuState.active || filtered.length === 0) return null;

  return (
    <div
      ref={menuRef}
      className="fixed z-50 w-64 max-h-72 overflow-y-auto rounded-md border bg-popover shadow-md"
      style={{
        top: menuState.top + 4,
        left: menuState.left,
      }}
    >
      {filtered.map((cmd, i) => (
        <button
          key={cmd.title}
          className={`w-full text-left px-3 py-2 text-sm hover:bg-muted ${
            i === selectedIndex ? "bg-muted" : ""
          }`}
          onMouseEnter={() => setSelectedIndex(i)}
          onClick={() => {
            cmd.command({ editor, range: menuState.range });
            const key = getSlashPluginKey();
            editor.view.dispatch(
              editor.state.tr.setMeta(key, { active: false } as SlashMenuState)
            );
          }}
        >
          <div className="font-medium">{cmd.title}</div>
          <div className="text-xs text-muted-foreground">
            {cmd.description}
          </div>
        </button>
      ))}
    </div>
  );
}
