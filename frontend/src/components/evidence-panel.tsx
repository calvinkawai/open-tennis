"use client";

import { useEffect, useRef } from "react";
import type { Evidence } from "../lib/contracts";
import { linkTo, safeHref } from "../lib/navigation";
import { Icon } from "./icons";

function order(label: string | undefined) {
  if (!label) return Number.MAX_SAFE_INTEGER;
  return (label.startsWith("S") ? 0 : 10_000) + Number(label.slice(1));
}

export function EvidencePanel({ citations, labels, selectedId, onSelect, onClose }: {
  citations: Evidence[]; labels: Map<string, string>; selectedId: string | null;
  onSelect: (id: string) => void; onClose: () => void;
}) {
  const selectedRef = useRef<HTMLElement>(null);
  useEffect(() => { selectedRef.current?.scrollIntoView?.({ block: "nearest" }); }, [selectedId]);
  if (!citations.length) return <p className="evidence-empty muted">这页没有附来源引用；不代表已获资料支持。</p>;
  const ordered = [...citations].sort((a, b) => order(labels.get(a.id)) - order(labels.get(b.id)));
  const index = ordered.findIndex((item) => item.id === selectedId);
  return <div className={`evidence-list${index >= 0 ? " open" : ""}`}>
    <div className="sheet-bar">
      <button type="button" className="icon-button" aria-label="关闭来源" onClick={onClose}><Icon name="close" /></button>
    </div>
    {ordered.map((evidence) => {
      const label = labels.get(evidence.id) ?? "";
      const selected = evidence.id === selectedId;
      const title = evidence.title || "未命名来源";
      const href = safeHref(evidence.source_url);
      return <article key={evidence.id} ref={selected ? selectedRef : undefined} aria-label={`${label} ${title}`}
        aria-current={selected ? "true" : undefined} className={`evidence-card ${evidence.kind}${selected ? " selected" : ""}`}>
        <header>
          <button type="button" className={`marker ${evidence.kind}`} aria-pressed={selected}
            onClick={() => onSelect(evidence.id)}>{label}</button>
          <span>{evidence.kind === "technical" ? "技术资料" : "本人原始记录"}</span>
        </header>
        <h3>{title}</h3>
        <p className="revision-text">快照 {evidence.revision}</p>
        {evidence.excerpt && <blockquote className="excerpt">{evidence.excerpt}</blockquote>}
        {evidence.kind === "journal" && <p className="small-text journal-note">主观观察，不作技术证据 · 原话未改写</p>}
        <div className="card-actions">
          <a className="button secondary small" href={linkTo("evidence", evidence.id)}>打开原文</a>
          {href ? <a className="button secondary small" href={href} target="_blank" rel="noopener noreferrer" referrerPolicy="no-referrer">
            原始链接<Icon name="external" size={14} /><span className="sr-only">（外部链接，新窗口）</span></a>
            : evidence.kind === "technical" && <span className="status-chip warn">原始链接缺失</span>}
        </div>
      </article>;
    })}
    <div className="sheet-pager">
      <button type="button" disabled={index <= 0} onClick={() => onSelect(ordered[index - 1].id)}>上一个</button>
      <span>{index + 1} / {ordered.length}</span>
      <button type="button" disabled={index < 0 || index >= ordered.length - 1} onClick={() => onSelect(ordered[index + 1].id)}>下一个</button>
    </div>
  </div>;
}
