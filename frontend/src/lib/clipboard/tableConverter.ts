/**
 * Convert pasted HTML table (e.g. from Excel/Google Sheets) into
 * Tiptap-compatible table HTML structure.
 */

/** Check if an HTML string contains a <table> element. */
export function containsHtmlTable(html: string): boolean {
  return /<table[\s>]/i.test(html);
}

/**
 * Parse an HTML table string and return a Tiptap-compatible table HTML.
 * Tiptap expects: <table><tbody><tr><th>…</th></tr><tr><td>…</td></tr>…</tbody></table>
 */
export function htmlTableToTiptap(html: string): string {
  const parser = new DOMParser();
  const doc = parser.parseFromString(html, "text/html");
  const table = doc.querySelector("table");
  if (!table) return html;

  const rows = Array.from(table.querySelectorAll("tr"));
  if (rows.length === 0) return html;

  const output: string[] = ["<table><tbody>"];

  rows.forEach((row, rowIdx) => {
    output.push("<tr>");
    const cells = Array.from(row.querySelectorAll("th, td"));
    cells.forEach((cell) => {
      // First row → header cells
      const tag = rowIdx === 0 ? "th" : "td";
      const text = cell.textContent?.trim() ?? "";
      output.push(`<${tag}><p>${escapeHtml(text)}</p></${tag}>`);
    });
    output.push("</tr>");
  });

  output.push("</tbody></table>");
  return output.join("");
}

function escapeHtml(text: string): string {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}
