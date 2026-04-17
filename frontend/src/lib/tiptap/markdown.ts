import TurndownService from "turndown";
import { marked } from "marked";

const turndown = new TurndownService({
  headingStyle: "atx",
  codeBlockStyle: "fenced",
  bulletListMarker: "-",
});

// Table support for turndown
turndown.addRule("tableCell", {
  filter: ["th", "td"],
  replacement(content) {
    return ` ${content.trim()} |`;
  },
});

turndown.addRule("tableRow", {
  filter: "tr",
  replacement(content) {
    return `|${content}\n`;
  },
});

turndown.addRule("table", {
  filter: "table",
  replacement(_content, node) {
    const element = node as HTMLElement;

    // If any cell has a custom column width (from Tiptap table resizing),
    // output the table as raw HTML so colwidth attributes survive the roundtrip.
    // Markdown supports inline HTML blocks; marked will pass them through on load.
    const hasColwidths =
      element.querySelector("td[colwidth], th[colwidth], col[style]") !== null;

    if (hasColwidths) {
      return "\n\n" + element.outerHTML + "\n\n";
    }

    // No custom widths — use readable markdown pipe format
    const rows = element.querySelectorAll("tr");
    const lines: string[] = [];

    rows.forEach((row, i) => {
      const cells = row.querySelectorAll("th, td");
      const line =
        "| " +
        Array.from(cells)
          .map((c) => c.textContent?.trim() ?? "")
          .join(" | ") +
        " |";
      lines.push(line);

      if (i === 0) {
        const separator =
          "| " +
          Array.from(cells)
            .map(() => "---")
            .join(" | ") +
          " |";
        lines.push(separator);
      }
    });

    return "\n" + lines.join("\n") + "\n";
  },
});

// Task list support
turndown.addRule("taskListItem", {
  filter(node) {
    return (
      node.nodeName === "LI" &&
      node.getAttribute("data-type") === "taskItem"
    );
  },
  replacement(content, node) {
    const element = node as HTMLElement;
    const checked = element.getAttribute("data-checked") === "true";
    return `- [${checked ? "x" : " "}] ${content.trim()}\n`;
  },
});

// Wiki image: strip /api/files/ prefix so stored markdown uses relative paths
turndown.addRule("wikiImage", {
  filter: "img",
  replacement(_content, node) {
    const el = node as HTMLElement;
    let src = el.getAttribute("src") || "";
    const alt = el.getAttribute("alt") || "";
    const title = el.getAttribute("title");
    if (src.startsWith("/api/files/")) {
      src = src.slice("/api/files/".length);
    }
    const titlePart = title ? ` "${title}"` : "";
    return `![${alt}](${src}${titlePart})`;
  },
});

// WikiLink support: <span data-wiki-link="name">[[name]]</span> → [[name]]
turndown.addRule("wikiLink", {
  filter(node) {
    return (
      node.nodeName === "SPAN" && node.hasAttribute("data-wiki-link")
    );
  },
  replacement(_content, node) {
    const element = node as HTMLElement;
    const target = element.getAttribute("data-wiki-link") ?? "";
    return `[[${target}]]`;
  },
});

// Zero-width space used to preserve empty paragraphs through markdown roundtrip.
// Turndown strips empty <p></p> during DOM preprocessing (before any rule fires),
// so we inject ZWSP into them before Turndown processes the HTML.
const ZWSP = "\u200B";

export function htmlToMarkdown(html: string): string {
  const preserved = html
    .replace(/<p><br\s*\/?><\/p>/g, `<p>${ZWSP}</p>`)
    .replace(/<p><\/p>/g, `<p>${ZWSP}</p>`);
  return turndown.turndown(preserved);
}

// Custom marked extension: parse [[wiki-link]] into <span data-wiki-link>
marked.use({
  extensions: [
    {
      name: "wikiLink",
      level: "inline" as const,
      start(src: string) {
        return src.indexOf("[[");
      },
      tokenizer(src: string) {
        const match = /^\[\[([^\]]+)\]\]/.exec(src);
        if (match) {
          return {
            type: "wikiLink",
            raw: match[0],
            target: match[1],
          };
        }
        return undefined;
      },
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      renderer(token: any) {
        return `<span data-wiki-link="${token.target}" class="wiki-link">[[${token.target}]]</span>`;
      },
    },
  ],
});

// Prefix relative image paths with /api/files/ so the browser can fetch wiki assets
marked.use({
  renderer: {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    image({ href, title, text }: any) {
      if (href && !href.startsWith("http://") && !href.startsWith("https://") && !href.startsWith("/")) {
        href = `/api/files/${href}`;
      }
      const alt = text ? ` alt="${text}"` : "";
      const titleAttr = title ? ` title="${title}"` : "";
      return `<img src="${href}"${alt}${titleAttr}>`;
    },
  },
});

export function markdownToHtml(md: string): string {
  const html = marked.parse(md, { async: false }) as string;
  // Strip ZWSP that was injected by htmlToMarkdown to preserve empty paragraphs.
  // Tiptap handles empty <p></p> natively — no invisible chars needed in the editor.
  return html.replace(/\u200B/g, "");
}
