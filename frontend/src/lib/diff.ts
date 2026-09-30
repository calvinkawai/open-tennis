export type DiffBlock = { kind: "same" | "added" | "removed"; text: string };

function paragraphs(text: string) {
  return text.split(/\n\s*\n/).map((part) => part.trim()).filter(Boolean);
}

export function diffParagraphs(before: string, after: string): DiffBlock[] {
  const a = paragraphs(before);
  const b = paragraphs(after);
  const common = Array.from({ length: a.length + 1 }, () => new Array<number>(b.length + 1).fill(0));
  for (let i = a.length - 1; i >= 0; i -= 1) {
    for (let j = b.length - 1; j >= 0; j -= 1) {
      common[i][j] = a[i] === b[j] ? common[i + 1][j + 1] + 1 : Math.max(common[i + 1][j], common[i][j + 1]);
    }
  }
  const blocks: DiffBlock[] = [];
  let i = 0;
  let j = 0;
  while (i < a.length && j < b.length) {
    if (a[i] === b[j]) {
      blocks.push({ kind: "same", text: a[i] });
      i += 1;
      j += 1;
    } else if (common[i + 1][j] >= common[i][j + 1]) {
      blocks.push({ kind: "removed", text: a[i] });
      i += 1;
    } else {
      blocks.push({ kind: "added", text: b[j] });
      j += 1;
    }
  }
  for (; i < a.length; i += 1) blocks.push({ kind: "removed", text: a[i] });
  for (; j < b.length; j += 1) blocks.push({ kind: "added", text: b[j] });
  return blocks;
}
