"use client";

import { type ReactNode } from "react";

export interface ResultColumn<T> {
  key: keyof T & string;
  header: string;
  render?: (value: T[keyof T], row: T) => ReactNode;
  width?: string;
}

interface ResultTableProps<T> {
  columns: ResultColumn<T>[];
  rows: T[];
  emptyMessage?: string;
  caption?: string;
}

export function ResultTable<T extends Record<string, unknown>>({
  columns,
  rows,
  emptyMessage = "결과 없음",
  caption,
}: ResultTableProps<T>) {
  if (rows.length === 0) {
    return (
      <div className="rounded border border-dashed border-gray-300 bg-gray-50 p-4 text-center text-sm text-gray-500">
        {emptyMessage}
      </div>
    );
  }

  return (
    <div className="overflow-x-auto rounded border border-gray-200">
      {caption && (
        <div className="border-b border-gray-200 bg-gray-50 px-3 py-2 text-xs font-semibold uppercase tracking-wide text-gray-600">
          {caption}
        </div>
      )}
      <table className="w-full text-sm">
        <thead className="bg-gray-50 text-left text-xs uppercase tracking-wide text-gray-500">
          <tr>
            {columns.map((c) => (
              <th
                key={c.key}
                className="px-3 py-2 font-semibold"
                style={c.width ? { width: c.width } : undefined}
              >
                {c.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100 bg-white">
          {rows.map((row, i) => (
            <tr key={i} className="hover:bg-blue-50/40">
              {columns.map((c) => {
                const v = row[c.key];
                return (
                  <td key={c.key} className="px-3 py-2 align-top">
                    {c.render ? c.render(v as never, row) : String(v ?? "")}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
