import { diffParagraphs } from "../lib/diff";
import { SafeMarkdown } from "./content";

export function VersionDiff({ before, after, fromLabel, toLabel }: {
  before: string; after: string; fromLabel: string; toLabel: string;
}) {
  const blocks = diffParagraphs(before, after);
  const added = blocks.filter((block) => block.kind === "added").length;
  const removed = blocks.filter((block) => block.kind === "removed").length;
  return <section className="version-diff" aria-label={`${fromLabel} → ${toLabel} 的差异`}>
    <div className="diff-summary">
      <span className="status-chip ok">新增 {added} 段</span>
      <span className="status-chip danger">删除 {removed} 段</span>
      <span className="status-chip">未改 {blocks.length - added - removed} 段</span>
    </div>
    {added + removed === 0 ? <p className="muted">两个版本的正文相同。</p>
      : blocks.filter((block) => block.kind !== "same").map((block, index) => (
        <div key={index} className={`diff-block ${block.kind}`}>
          <p className="diff-label">{block.kind === "added" ? `＋ ${toLabel} 新增` : `－ ${fromLabel} 中的这段被删除`}</p>
          <SafeMarkdown text={block.text} />
        </div>
      ))}
  </section>;
}
