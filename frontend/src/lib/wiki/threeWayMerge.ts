"use client";

export interface ConflictBlock {
  id: string;              // unique sentinel baked into marker text
  startLine: number;       // line number in the merged output
  baseLines: string[];
  mineLines: string[];
  serverLines: string[];
  /** marker: "ours" | "theirs" | "both" | null (initial = null means user must choose) */
  resolution: "ours" | "theirs" | "both" | null;
}

export interface ThreeWayMergeResult {
  merged: string;             // text with conflict markers if any
  conflicts: ConflictBlock[];
  hasConflicts: boolean;
}

let _nextBlockId = 0;
function _makeBlockId(): string {
  _nextBlockId += 1;
  return `b${_nextBlockId}`;
}

export function threeWayMerge(base: string, mine: string, server: string): ThreeWayMergeResult {
  // Trivial fast paths
  if (mine === server) {
    return { merged: mine, conflicts: [], hasConflicts: false };
  }
  if (base === mine) {
    // Mine didn't change; server wins
    return { merged: server, conflicts: [], hasConflicts: false };
  }
  if (base === server) {
    // Server didn't change; mine wins
    return { merged: mine, conflicts: [], hasConflicts: false };
  }

  const baseLines = base.split("\n");
  const mineLines = mine.split("\n");
  const serverLines = server.split("\n");

  const output: string[] = [];
  const conflicts: ConflictBlock[] = [];

  let i = 0; // base index
  let m = 0; // mine index
  let s = 0; // server index

  while (i < baseLines.length || m < mineLines.length || s < serverLines.length) {
    const baseLine = i < baseLines.length ? baseLines[i] : null;
    const mineLine = m < mineLines.length ? mineLines[m] : null;
    const serverLine = s < serverLines.length ? serverLines[s] : null;

    // All three match → keep
    if (baseLine !== null && baseLine === mineLine && baseLine === serverLine) {
      output.push(baseLine);
      i++; m++; s++;
      continue;
    }

    // Mine and server agree (both same change relative to base) → keep mine
    if (mineLine !== null && mineLine === serverLine) {
      output.push(mineLine);
      i++; m++; s++;
      continue;
    }

    // Mine matches base, server changed → take server
    if (baseLine !== null && baseLine === mineLine && serverLine !== mineLine) {
      output.push(serverLine ?? "");
      i++; m++;
      if (serverLine !== null) s++;
      continue;
    }

    // Server matches base, mine changed → take mine
    if (baseLine !== null && baseLine === serverLine && mineLine !== serverLine) {
      output.push(mineLine ?? "");
      i++; s++;
      if (mineLine !== null) m++;
      continue;
    }

    // True conflict: collect runs of conflicting lines on both sides until
    // we resync. Naive: take one line from each side, emit conflict block, advance.
    const blockId = _makeBlockId();
    const startLine = output.length;
    const block: ConflictBlock = {
      id: blockId,
      startLine,
      baseLines: baseLine !== null ? [baseLine] : [],
      mineLines: mineLine !== null ? [mineLine] : [],
      serverLines: serverLine !== null ? [serverLine] : [],
      resolution: null,
    };
    output.push(`<<<<<<< MINE [${blockId}]`);
    if (mineLine !== null) output.push(mineLine);
    output.push("=======");
    if (serverLine !== null) output.push(serverLine);
    output.push(`>>>>>>> SERVER [${blockId}]`);
    conflicts.push(block);

    if (baseLine !== null) i++;
    if (mineLine !== null) m++;
    if (serverLine !== null) s++;
  }

  return {
    merged: output.join("\n"),
    conflicts,
    hasConflicts: conflicts.length > 0,
  };
}

/**
 * Apply a single block resolution to merged text by looking up the block by its
 * sentinel ID embedded in the marker. This is safe even after other blocks have
 * been resolved (i.e., their markers removed), because each marker carries a unique ID.
 * Returns updated merged string.
 */
export function applyResolutionById(
  merged: string,
  blockId: string,
  resolution: "ours" | "theirs" | "both",
): string {
  const lines = merged.split("\n");
  const startMarker = `<<<<<<< MINE [${blockId}]`;
  const endMarker = `>>>>>>> SERVER [${blockId}]`;
  let startIdx = -1;
  let midIdx = -1;
  let endIdx = -1;

  for (let i = 0; i < lines.length; i++) {
    if (lines[i] === startMarker) {
      startIdx = i;
    } else if (startIdx !== -1 && lines[i] === "=======" && midIdx === -1) {
      midIdx = i;
    } else if (midIdx !== -1 && lines[i] === endMarker) {
      endIdx = i;
      break;
    }
  }

  if (startIdx === -1 || midIdx === -1 || endIdx === -1) return merged;

  let replacement: string[];
  if (resolution === "ours") {
    replacement = lines.slice(startIdx + 1, midIdx);
  } else if (resolution === "theirs") {
    replacement = lines.slice(midIdx + 1, endIdx);
  } else {
    // both
    replacement = [
      ...lines.slice(startIdx + 1, midIdx),
      ...lines.slice(midIdx + 1, endIdx),
    ];
  }

  return [
    ...lines.slice(0, startIdx),
    ...replacement,
    ...lines.slice(endIdx + 1),
  ].join("\n");
}

/**
 * @deprecated Use applyResolutionById instead.
 * Kept for backwards compatibility — finds block by position index.
 * BREAKS after the first block is resolved (markers shift).
 */
export function applyResolutionByIndex(
  merged: string,
  blockIndex: number,
  resolution: "ours" | "theirs" | "both",
): string {
  const lines = merged.split("\n");
  let currentBlock = -1;
  let startIdx = -1;
  let midIdx = -1;
  let endIdx = -1;

  for (let i = 0; i < lines.length; i++) {
    // Match any <<<<<<< MINE [*] marker
    if (lines[i].startsWith("<<<<<<< MINE [")) {
      currentBlock++;
      if (currentBlock === blockIndex) {
        startIdx = i;
      }
    } else if (lines[i] === "=======" && startIdx !== -1 && midIdx === -1 && currentBlock === blockIndex) {
      midIdx = i;
    } else if (lines[i].startsWith(">>>>>>> SERVER [") && midIdx !== -1 && currentBlock === blockIndex) {
      endIdx = i;
      break;
    }
  }
  if (startIdx === -1 || midIdx === -1 || endIdx === -1) return merged;

  let replacement: string[];
  if (resolution === "ours") {
    replacement = lines.slice(startIdx + 1, midIdx);
  } else if (resolution === "theirs") {
    replacement = lines.slice(midIdx + 1, endIdx);
  } else {
    // both
    replacement = [
      ...lines.slice(startIdx + 1, midIdx),
      ...lines.slice(midIdx + 1, endIdx),
    ];
  }
  return [
    ...lines.slice(0, startIdx),
    ...replacement,
    ...lines.slice(endIdx + 1),
  ].join("\n");
}
