/**
 * Tiptap extension: WikiLink inline node.
 *
 * Renders [[document-name]] as a clickable chip that opens the target document.
 * - Input rule: typing [[name]] converts to a WikiLink node
 * - NodeView: renders as a DOM span with direct click handler (avoids ProseMirror selection conflicts)
 * - Markdown round-trip: preserved as [[name]] in markdown source
 */

import { Node, mergeAttributes } from "@tiptap/core";
import { InputRule } from "@tiptap/core";

export interface WikiLinkOptions {
  onClickLink?: (target: string) => void;
}

export const WikiLinkNode = Node.create<WikiLinkOptions>({
  name: "wikiLink",
  group: "inline",
  inline: true,
  atom: true,

  addOptions() {
    return { onClickLink: undefined };
  },

  addAttributes() {
    return {
      target: { default: null },
    };
  },

  parseHTML() {
    return [
      {
        tag: "span[data-wiki-link]",
        getAttrs: (el) => {
          const element = el as HTMLElement;
          return { target: element.getAttribute("data-wiki-link") };
        },
      },
    ];
  },

  renderHTML({ node, HTMLAttributes }) {
    return [
      "span",
      mergeAttributes(HTMLAttributes, {
        "data-wiki-link": node.attrs.target,
        class: "wiki-link",
      }),
      `[[${node.attrs.target}]]`,
    ];
  },

  addNodeView() {
    const onClickLink = this.options.onClickLink;

    return ({ node }) => {
      const dom = document.createElement("span");
      dom.className = "wiki-link";
      dom.setAttribute("data-wiki-link", node.attrs.target ?? "");
      dom.textContent = `[[${node.attrs.target}]]`;
      dom.contentEditable = "false";

      dom.addEventListener("click", (e) => {
        e.preventDefault();
        e.stopPropagation();
        if (onClickLink && node.attrs.target) {
          onClickLink(node.attrs.target);
        }
      });

      return { dom };
    };
  },

  addInputRules() {
    return [
      new InputRule({
        find: /\[\[([^\]]+)\]\]$/,
        handler: ({ state, range, match, chain }) => {
          const target = match[1];
          const node = this.type.create({ target });
          chain()
            .command(({ tr }) => {
              tr.replaceWith(range.from, range.to, node);
              tr.insertText(" ", tr.mapping.map(range.to));
              return true;
            })
            .run();
        },
      }),
    ];
  },
});
