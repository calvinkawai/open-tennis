"use client";

import Markdown from "react-markdown";
import { type Evidence, type Section } from "../lib/contracts";
import { linkTo, safeHref } from "../lib/navigation";

export function SafeMarkdown({ text }: { text: string }) {
  return (
    <div className="prose">
      <Markdown
        skipHtml
        urlTransform={(url) => safeHref(url) ?? ""}
        components={{
          a: ({ href, children }) => href ? (
            <a href={href} target={href.startsWith("#") ? undefined : "_blank"}
              rel="noopener noreferrer" referrerPolicy="no-referrer">
              {children}{!href.startsWith("#") && <span className="sr-only">（外部链接，新窗口）</span>}
            </a>
          ) : <span>{children}</span>,
          img: ({ alt }) => <span className="muted">[图片未加载{alt ? `：${alt}` : ""}]</span>,
          h1: ({ children }) => <h2>{children}</h2>,
        }}
      >{text}</Markdown>
    </div>
  );
}

export function EvidenceLink({ evidence }: { evidence: Evidence }) {
  return (
    <a className="citation-link" href={linkTo("evidence", evidence.id)}>
      <span className="source-kind">{evidence.kind === "technical" ? "技术资料" : "本人原始记录"}</span>
      <span className="citation-title">{evidence.title || "未命名来源"}</span>
      <span className="citation-revision">原版 {evidence.revision}</span>
      <span aria-hidden="true">↗</span>
    </a>
  );
}

export function Citations({ citations }: { citations: Evidence[] }) {
  if (!citations.length) return <p className="muted">未附来源引用；不代表已获资料支持。</p>;
  return <div className="citations">{citations.map((evidence) =>
    <EvidenceLink key={evidence.id} evidence={evidence} />,
  )}</div>;
}

const labels: Record<Section["kind"], string> = {
  source_supported: "资料支持",
  personal_observation: "本人记录 · 主观观察",
  model_supplement: "模型补充 · 未经知识库核验",
};

export function SourcedContent({ sections, citations }: { sections: Section[]; citations: Evidence[] }) {
  return <div className="sourced-content">
    {sections.map((section, index) => (
      <section key={index} className={`evidence-section ${section.kind}`} aria-label={labels[section.kind]}>
        <h3 className="evidence-label"><span className="evidence-dot" aria-hidden="true" />{labels[section.kind]}</h3>
        <SafeMarkdown text={section.text} />
        {section.kind !== "model_supplement" && section.citation_ids.length === 0 &&
          <p className="notice warning">这段内容没有附带引用，不能据此确认来源支持。</p>}
        {section.citation_ids.map((id) => {
          const citation = citations.find((item) => item.id === id);
          return citation
            ? <EvidenceLink key={id} evidence={citation} />
            : <p key={id} className="notice warning">引用缺失，暂时无法核对原文。</p>;
        })}
      </section>
    ))}
  </div>;
}
