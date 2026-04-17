/**
 * MarkdownShortcuts — Tiptap extension for Notion/Obsidian-style markdown input.
 *
 * Implements block-level shortcuts (triggered by Space at line start):
 *   # … ###### → Heading 1–6
 *   -, *, +    → Bullet list
 *   1.         → Ordered list
 *   >          → Blockquote
 *   []  / [ ]  → Task list
 *   ```        → Code block
 *   ---        → Horizontal rule (also on Enter)
 *
 * Handles hard breaks (<br>) inside paragraphs: only looks at the
 * current "line" (after last hard break) when matching patterns.
 */

import { Extension } from "@tiptap/core";
import { Plugin, PluginKey } from "@tiptap/pm/state";

interface BlockPattern {
  regex: RegExp;
  handler: (
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    editor: any,
    match: RegExpMatchArray,
    range: { from: number; to: number },
  ) => boolean;
}

const blockPatterns: BlockPattern[] = [
  // Headings: # through ######
  {
    regex: /^(#{1,6})$/,
    handler: (editor, match, range) => {
      const level = match[1].length as 1 | 2 | 3 | 4 | 5 | 6;
      editor.chain().focus().deleteRange(range).setHeading({ level }).run();
      return true;
    },
  },
  // Bullet list: -, *, +
  {
    regex: /^([-*+])$/,
    handler: (editor, _match, range) => {
      editor.chain().focus().deleteRange(range).toggleBulletList().run();
      return true;
    },
  },
  // Ordered list: 1.
  {
    regex: /^(\d+)\.$/,
    handler: (editor, _match, range) => {
      editor.chain().focus().deleteRange(range).toggleOrderedList().run();
      return true;
    },
  },
  // Blockquote: >
  {
    regex: /^>$/,
    handler: (editor, _match, range) => {
      editor.chain().focus().deleteRange(range).toggleBlockquote().run();
      return true;
    },
  },
  // Task list: [] or [ ]
  {
    regex: /^\[[\s]?\]$/,
    handler: (editor, _match, range) => {
      editor.chain().focus().deleteRange(range).toggleTaskList().run();
      return true;
    },
  },
  // Code block: ```
  {
    regex: /^```$/,
    handler: (editor, _match, range) => {
      editor.chain().focus().deleteRange(range).toggleCodeBlock().run();
      return true;
    },
  },
  // Horizontal rule: --- or *** or ___
  {
    regex: /^(---|___|[*]{3})$/,
    handler: (editor, _match, range) => {
      editor.chain().focus().deleteRange(range).setHorizontalRule().run();
      return true;
    },
  },
];

/**
 * Get the "current line" text and its absolute start position in the document.
 * A "line" starts after the last hard break node or at the parent paragraph start.
 */
function getCurrentLine(
  $from: ReturnType<typeof import("@tiptap/pm/state").EditorState.prototype.doc.resolve>,
): { text: string; lineStart: number } | null {
  const parent = $from.parent;
  if (parent.type.name !== "paragraph") return null;

  const parentStart = $from.start(); // absolute pos of parent content start
  const cursorOffset = $from.parentOffset; // offset within parent

  // Walk backwards through child nodes to find the last hard break before cursor
  let lastBreakEnd = 0; // offset within parent right after last hardBreak
  let offset = 0;

  for (let i = 0; i < parent.childCount; i++) {
    const child = parent.child(i);
    const childEnd = offset + child.nodeSize;

    if (childEnd > cursorOffset) break; // past cursor

    if (child.type.name === "hardBreak") {
      lastBreakEnd = childEnd;
    }

    offset = childEnd;
  }

  // Text from line start to cursor
  const text = parent.textBetween(lastBreakEnd, cursorOffset, undefined, "\ufffc");
  return { text, lineStart: parentStart + lastBreakEnd };
}

export const MarkdownShortcuts = Extension.create({
  name: "markdownShortcuts",
  priority: 200,

  addProseMirrorPlugins() {
    const editor = this.editor;

    return [
      new Plugin({
        key: new PluginKey("markdownShortcuts"),
        props: {
          handleTextInput(view, from, _to, text) {
            if (text !== " ") return false;

            const $from = view.state.doc.resolve(from);
            const line = getCurrentLine($from);
            if (!line) return false;

            const trimmed = line.text.trimStart();
            if (!trimmed) return false;

            for (const pattern of blockPatterns) {
              const match = trimmed.match(pattern.regex);
              if (!match) continue;

              // Range: from the actual pattern start to cursor (excludes the space being typed)
              const leadingSpaces = line.text.length - trimmed.length;
              const rangeFrom = line.lineStart + leadingSpaces;
              const rangeTo = from;

              // Don't trigger if there's content after cursor on the same line
              const textAfter = $from.parent.textBetween(
                $from.parentOffset,
                $from.parent.content.size,
                undefined,
                "\ufffc",
              );
              if (textAfter.trim().length > 0) return false;

              return pattern.handler(editor, match, {
                from: rangeFrom,
                to: rangeTo,
              });
            }

            return false;
          },

          handleKeyDown(view, event) {
            if (event.key !== "Enter") return false;

            const { $from } = view.state.selection;
            const line = getCurrentLine($from);
            if (!line) return false;

            const trimmed = line.text.trim();

            if (/^(---|___|[*]{3})$/.test(trimmed)) {
              const leadingSpaces = line.text.length - line.text.trimStart().length;
              const rangeFrom = line.lineStart + leadingSpaces;
              const rangeTo = line.lineStart + line.text.length;

              editor
                .chain()
                .focus()
                .deleteRange({ from: rangeFrom, to: rangeTo })
                .setHorizontalRule()
                .run();
              return true;
            }

            return false;
          },
        },
      }),
    ];
  },
});
