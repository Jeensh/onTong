import { Extension } from "@tiptap/react";
import { Plugin, PluginKey } from "@tiptap/pm/state";
// pm/view types not needed for this extension

export interface SlashCommandItem {
  title: string;
  description: string;
  command: (props: { editor: ReturnType<typeof import("@tiptap/react").useEditor>; range: { from: number; to: number } }) => void;
}

export const SLASH_COMMANDS: SlashCommandItem[] = [
  {
    title: "제목 1",
    description: "Heading 1",
    command: ({ editor, range }) => {
      editor?.chain().focus().deleteRange(range).setHeading({ level: 1 }).run();
    },
  },
  {
    title: "제목 2",
    description: "Heading 2",
    command: ({ editor, range }) => {
      editor?.chain().focus().deleteRange(range).setHeading({ level: 2 }).run();
    },
  },
  {
    title: "제목 3",
    description: "Heading 3",
    command: ({ editor, range }) => {
      editor?.chain().focus().deleteRange(range).setHeading({ level: 3 }).run();
    },
  },
  {
    title: "글머리 기호",
    description: "Bullet List",
    command: ({ editor, range }) => {
      editor?.chain().focus().deleteRange(range).toggleBulletList().run();
    },
  },
  {
    title: "번호 목록",
    description: "Ordered List",
    command: ({ editor, range }) => {
      editor?.chain().focus().deleteRange(range).toggleOrderedList().run();
    },
  },
  {
    title: "체크리스트",
    description: "Task List",
    command: ({ editor, range }) => {
      editor?.chain().focus().deleteRange(range).toggleTaskList().run();
    },
  },
  {
    title: "테이블",
    description: "3x3 Table",
    command: ({ editor, range }) => {
      editor
        ?.chain()
        .focus()
        .deleteRange(range)
        .insertTable({ rows: 3, cols: 3, withHeaderRow: true })
        .run();
    },
  },
  {
    title: "코드 블록",
    description: "Code Block",
    command: ({ editor, range }) => {
      editor?.chain().focus().deleteRange(range).toggleCodeBlock().run();
    },
  },
  {
    title: "인용",
    description: "Blockquote",
    command: ({ editor, range }) => {
      editor?.chain().focus().deleteRange(range).toggleBlockquote().run();
    },
  },
  {
    title: "구분선",
    description: "Horizontal Rule",
    command: ({ editor, range }) => {
      editor?.chain().focus().deleteRange(range).setHorizontalRule().run();
    },
  },
];

const slashPluginKey = new PluginKey("slashCommand");

export interface SlashMenuState {
  active: boolean;
  query: string;
  range: { from: number; to: number };
  top: number;
  left: number;
}

export const SlashCommandExtension = Extension.create({
  name: "slashCommand",

  addProseMirrorPlugins() {
    return [
      new Plugin({
        key: slashPluginKey,
        state: {
          init: () => ({ active: false } as SlashMenuState),
          apply(tr, prev) {
            const meta = tr.getMeta(slashPluginKey);
            if (meta) return meta;
            if (prev.active && tr.docChanged) {
              // Re-check if slash is still valid
              const { from } = tr.selection;
              const $from = tr.doc.resolve(from);
              const textBefore = $from.parent.textContent.slice(
                0,
                $from.parentOffset
              );
              const match = textBefore.match(/^\/(\S*)$/);
              if (match) {
                return {
                  ...prev,
                  query: match[1],
                  range: { from: $from.start(), to: from },
                };
              }
              return { active: false } as SlashMenuState;
            }
            return prev;
          },
        },
        props: {
          handleKeyDown(view, event) {
            const state = slashPluginKey.getState(view.state) as SlashMenuState;

            if (event.key === "/" && !state?.active) {
              const { from } = view.state.selection;
              const $from = view.state.doc.resolve(from);
              const textBefore = $from.parent.textContent.slice(
                0,
                $from.parentOffset
              );

              // Only trigger on empty line or start of line
              if (textBefore.trim() === "") {
                // Delay to let the character be inserted
                setTimeout(() => {
                  const coords = view.coordsAtPos(from);
                  view.dispatch(
                    view.state.tr.setMeta(slashPluginKey, {
                      active: true,
                      query: "",
                      range: { from, to: from + 1 },
                      top: coords.bottom,
                      left: coords.left,
                    } as SlashMenuState)
                  );
                }, 0);
              }
              return false;
            }

            if (state?.active && event.key === "Escape") {
              view.dispatch(
                view.state.tr.setMeta(slashPluginKey, {
                  active: false,
                } as SlashMenuState)
              );
              return true;
            }

            return false;
          },
        },
      }),
    ];
  },
});

export function getSlashPluginKey() {
  return slashPluginKey;
}
