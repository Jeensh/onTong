/**
 * Tiptap extension: custom paste handler for HTML tables, images, and wiki-links.
 */

import { Extension } from "@tiptap/core";
import { Plugin, PluginKey } from "@tiptap/pm/state";
import { Fragment, Slice } from "@tiptap/pm/model";
import {
  containsHtmlTable,
  htmlTableToTiptap,
} from "@/lib/clipboard/tableConverter";
import { uploadImage } from "@/lib/clipboard/imagePaste";

const WIKI_LINK_RE = /\[\[([^\]]+)\]\]/g;

export const PasteHandlerExtension = Extension.create({
  name: "pasteHandler",

  addProseMirrorPlugins() {
    const editor = this.editor;

    return [
      new Plugin({
        key: new PluginKey("pasteHandler"),
        props: {
          handlePaste(view, event) {
            const clipboardData = event.clipboardData;
            if (!clipboardData) return false;

            // --- HTML table paste (check BEFORE image) ---
            const html = clipboardData.getData("text/html");
            if (html && containsHtmlTable(html)) {
              event.preventDefault();
              const tiptapHtml = htmlTableToTiptap(html);
              editor.commands.insertContent(tiptapHtml);
              return true;
            }

            // --- Wiki-link paste: [[document-name]] ---
            const text = clipboardData.getData("text/plain");
            if (text && WIKI_LINK_RE.test(text)) {
              WIKI_LINK_RE.lastIndex = 0;

              const schema = view.state.schema;
              const wikiLinkType = schema.nodes.wikiLink;
              if (!wikiLinkType) return false;

              // Build fragment: interleave text and wikiLink nodes
              // eslint-disable-next-line @typescript-eslint/no-explicit-any
              const nodes: any[] = [];
              let lastIndex = 0;
              let match: RegExpExecArray | null;

              while ((match = WIKI_LINK_RE.exec(text)) !== null) {
                if (match.index > lastIndex) {
                  nodes.push(schema.text(text.slice(lastIndex, match.index)));
                }
                nodes.push(wikiLinkType.create({ target: match[1] }));
                lastIndex = match.index + match[0].length;
              }
              if (lastIndex < text.length) {
                nodes.push(schema.text(text.slice(lastIndex)));
              }

              if (nodes.length > 0) {
                event.preventDefault();
                const fragment = Fragment.from(nodes);
                const paragraph = schema.nodes.paragraph.create(null, fragment);
                const slice = new Slice(Fragment.from(paragraph), 0, 0);
                view.dispatch(view.state.tr.replaceSelection(slice));
                return true;
              }
            }

            // --- Image paste ---
            const imageFile = getImageFile(clipboardData);
            if (imageFile) {
              event.preventDefault();
              handleImageUpload(editor, imageFile);
              return true;
            }

            return false;
          },

          handleDrop(_view, event) {
            const dataTransfer = event.dataTransfer;
            if (!dataTransfer) return false;

            const imageFile = getImageFile(dataTransfer);
            if (imageFile) {
              event.preventDefault();
              handleImageUpload(editor, imageFile);
              return true;
            }

            return false;
          },
        },
      }),
    ];
  },
});

function getImageFile(data: DataTransfer): File | null {
  for (const item of Array.from(data.items)) {
    if (item.type.startsWith("image/")) {
      const file = item.getAsFile();
      if (file) return file;
    }
  }
  return null;
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
async function handleImageUpload(editor: any, file: File) {
  try {
    const path = await uploadImage(file);
    editor.commands.insertContent({
      type: "image",
      attrs: { src: `/api/files/${path}` },
    });
  } catch (err) {
    console.error("Image upload failed:", err);
  }
}
