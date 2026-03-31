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

export function htmlToMarkdown(html: string): string {
  return turndown.turndown(html);
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

export function markdownToHtml(md: string): string {
  return marked.parse(md, { async: false }) as string;
}
