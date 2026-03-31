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
    title: "Heading 1",
    description: "큰 제목",
    command: ({ editor, range }) => {
      editor?.chain().focus().deleteRange(range).setHeading({ level: 1 }).run();
    },
  },
  {
    title: "Heading 2",
    description: "중간 제목",
    command: ({ editor, range }) => {
      editor?.chain().focus().deleteRange(range).setHeading({ level: 2 }).run();
    },
  },
  {
    title: "Heading 3",
    description: "작은 제목",
    command: ({ editor, range }) => {
      editor?.chain().focus().deleteRange(range).setHeading({ level: 3 }).run();
    },
  },
  {
    title: "Bullet List",
    description: "글머리 기호 목록",
    command: ({ editor, range }) => {
      editor?.chain().focus().deleteRange(range).toggleBulletList().run();
    },
  },
  {
    title: "Ordered List",
    description: "번호 매기기 목록",
    command: ({ editor, range }) => {
      editor?.chain().focus().deleteRange(range).toggleOrderedList().run();
    },
  },
  {
    title: "Task List",
    description: "체크리스트",
    command: ({ editor, range }) => {
      editor?.chain().focus().deleteRange(range).toggleTaskList().run();
    },
  },
  {
    title: "Table",
    description: "3x3 테이블 삽입",
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
    title: "Code Block",
    description: "코드 블록",
    command: ({ editor, range }) => {
      editor?.chain().focus().deleteRange(range).toggleCodeBlock().run();
    },
  },
  {
    title: "Blockquote",
    description: "인용 블록",
    command: ({ editor, range }) => {
      editor?.chain().focus().deleteRange(range).toggleBlockquote().run();
    },
  },
  {
    title: "Horizontal Rule",
    description: "구분선",
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
