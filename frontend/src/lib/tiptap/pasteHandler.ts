/**
 * Tiptap extension: custom paste handler for HTML tables, images, and wiki-links.
 */

import { Extension } from "@tiptap/core";
import { Plugin, PluginKey, NodeSelection } from "@tiptap/pm/state";
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

// ── Image Copy Extension ────────────────────────────────────────────

export const ImageCopyExtension = Extension.create({
  name: "imageCopy",

  addProseMirrorPlugins() {
    return [
      new Plugin({
        key: new PluginKey("imageCopy"),
        props: {
          handleKeyDown(view, event) {
            if ((event.ctrlKey || event.metaKey) && event.key === "c") {
              const { selection } = view.state;
              if (selection instanceof NodeSelection && selection.node.type.name === "image") {
                const src = selection.node.attrs.src;
                if (src) {
                  copyImageToClipboard(src);
                  event.preventDefault();
                  return true;
                }
              }
            }
            return false;
          },
          handleDOMEvents: {
            contextmenu(view, event) {
              const pos = view.posAtCoords({ left: event.clientX, top: event.clientY });
              if (!pos) return false;

              const node = view.state.doc.nodeAt(pos.pos);
              if (node?.type.name === "image") {
                event.preventDefault();
                showImageContextMenu(event.clientX, event.clientY, node.attrs.src);
                return true;
              }
              return false;
            },
          },
        },
      }),
    ];
  },
});

async function copyImageToClipboard(src: string): Promise<void> {
  try {
    const res = await fetch(src);
    const blob = await res.blob();
    const pngBlob = blob.type === "image/png" ? blob : await convertToPng(blob);
    await navigator.clipboard.write([
      new ClipboardItem({ "image/png": pngBlob }),
    ]);
  } catch (err) {
    console.error("Failed to copy image:", err);
  }
}

function convertToPng(blob: Blob): Promise<Blob> {
  return new Promise((resolve, reject) => {
    const img = new window.Image();
    img.onload = () => {
      const canvas = document.createElement("canvas");
      canvas.width = img.width;
      canvas.height = img.height;
      const ctx = canvas.getContext("2d");
      if (!ctx) return reject(new Error("No canvas context"));
      ctx.drawImage(img, 0, 0);
      canvas.toBlob((b) => (b ? resolve(b) : reject(new Error("toBlob failed"))), "image/png");
    };
    img.onerror = reject;
    img.src = URL.createObjectURL(blob);
  });
}

let _menuEl: HTMLDivElement | null = null;

function showImageContextMenu(x: number, y: number, src: string): void {
  removeImageContextMenu();

  _menuEl = document.createElement("div");
  _menuEl.style.cssText = `
    position: fixed; left: ${x}px; top: ${y}px; z-index: 9999;
    background: white; border: 1px solid #ddd; border-radius: 6px;
    box-shadow: 0 4px 12px rgba(0,0,0,0.15); padding: 4px 0;
    font-size: 13px; min-width: 160px;
  `;

  const copyItem = document.createElement("div");
  copyItem.textContent = "이미지 복사";
  copyItem.style.cssText = "padding: 6px 12px; cursor: pointer;";
  copyItem.onmouseenter = () => (copyItem.style.background = "#f0f0f0");
  copyItem.onmouseleave = () => (copyItem.style.background = "transparent");
  copyItem.onclick = () => {
    copyImageToClipboard(src);
    removeImageContextMenu();
  };
  _menuEl.appendChild(copyItem);

  document.body.appendChild(_menuEl);

  const dismiss = (e: MouseEvent) => {
    if (_menuEl && !_menuEl.contains(e.target as Node)) {
      removeImageContextMenu();
      document.removeEventListener("mousedown", dismiss);
    }
  };
  setTimeout(() => document.addEventListener("mousedown", dismiss), 0);
}

function removeImageContextMenu(): void {
  if (_menuEl) {
    _menuEl.remove();
    _menuEl = null;
  }
}
