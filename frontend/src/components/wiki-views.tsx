"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import type { Answer, Space, WikiDetail, WikiVersion } from "../lib/contracts";
import { citationLabels } from "../lib/evidence";
import { formatDate, linkTo, navigate, safeHref } from "../lib/navigation";
import { pageStatuses } from "../lib/status";
import type { ViewContext } from "./app-shell";
import { Citations, SafeMarkdown, SourcedContent } from "./content";
import { EvidencePanel } from "./evidence-panel";
import { StatusChip } from "./status";
import { Failure, Loading, Notice, useAction, useLoad } from "./ui";
import { VersionDiff } from "./version-diff";

function AgentPanel({ context, page }: { context: ViewContext; page: WikiDetail }) {
  const [query, setQuery] = useState("");
  const [personal, setPersonal] = useState(false);
  const [answer, setAnswer] = useState<Answer | null>(null);
  const action = useAction();
  return <div className="agent-panel">
    <div className="row"><h2>问资料，也问自己的经历。</h2><span className="agent-star" aria-hidden="true">✧</span></div>
    <p className="muted small-text">Agent 不修改原文。技术改动先审阅，个人 Wiki 的整理保留引用和版本。</p>
    <form onSubmit={(event) => {
      event.preventDefault();
      void action.act(async () => setAnswer(await context.api.ask({
        query, page_id: page.id, include_personal: personal,
      })));
    }}>
      <label>围绕这篇 Wiki 提问<textarea value={query} onChange={(event) => setQuery(event.target.value)}
        maxLength={2000} minLength={3} required placeholder="结合这个主题，我下一次应该观察什么？" /></label>
      <label className="check-label"><input type="checkbox" checked={personal} onChange={(event) => setPersonal(event.target.checked)} />
        同时使用我的训练经历</label>
      <p className="privacy-note">提问会将最小必要资料交给已配置的模型供应商。勾选后还可能包含个人原始记录；不是纯本机 AI。</p>
      <button className="button" disabled={action.busy || !context.online}>{action.busy ? "正在查找和组织…" : "带着来源回答"}</button>
    </form>
    {!context.online && <Notice>离线不能发起新的模型调用。可以继续阅读已保存的资料。</Notice>}
    {action.feedback}
    {answer && <div className="agent-answer">
      {answer.warning && <Notice warning>{answer.warning}</Notice>}
      <SourcedContent sections={answer.sections} citations={answer.citations} />
      <a className="text-link" href={linkTo("preview", page.id)}>结合这篇 Wiki 预览训练卡 →</a>
    </div>}
  </div>;
}

function VersionReview({ page, context, onChanged }: {
  page: WikiDetail; context: ViewContext; onChanged: () => void;
}) {
  const state = useLoad(useCallback(() => context.api.versions(page.id), [context.api, page.id]));
  const action = useAction();
  const [selected, setSelected] = useState<WikiVersion | null>(null);
  const [confirmed, setConfirmed] = useState(false);
  const [instructions, setInstructions] = useState("");
  useEffect(() => { setSelected(null); setConfirmed(false); }, [page.id, page.version]);
  const current = selected ?? state.data?.find((version) => version.status === "draft") ?? state.data?.[0];
  return <section className="version-panel">
    <h2>引用、变更与版本</h2>
    <p className="muted">发布技术版本需要你的审阅。回退会创建保留历史的新版本，不会覆盖原始资料。</p>
    {state.loading ? <Loading /> : state.error ? <Failure message={state.error} retry={state.reload} /> : <>
      <div className="version-list">{state.data?.map((version) => <button
        key={version.id} className={`version-chip ${current?.id === version.id ? "chosen" : ""}`}
        onClick={() => { setSelected(version); setConfirmed(false); }}>
        v{version.number} · {version.status === "draft" ? "待审阅" : "已发布"}<small>{formatDate(version.created_at)}</small>
      </button>)}</div>
      {current && <div className="version-detail">
        <p className="change-summary">{current.change_summary}</p>
        {page.version_id !== current.id && <VersionDiff before={page.content} after={current.content}
          fromLabel={page.version ? `当前 v${page.version}` : "当前"} toLabel={`v${current.number}`} />}
        <details open><summary>此版本的内容和来源</summary>
          {current.sections.length ? <SourcedContent sections={current.sections} citations={current.citations} /> : <SafeMarkdown text={current.content} />}
          <Citations citations={current.citations} /></details>
        <label className="check-label"><input type="checkbox" checked={confirmed} onChange={(event) => setConfirmed(event.target.checked)} />
          我已核对内容、来源与版本，确认执行{current.status === "draft" ? "发布" : "回退"}</label>
        <button className="button" disabled={!confirmed || action.busy || !context.online || (current.status === "draft" && page.space !== "technical")}
          onClick={() => void action.act(async () => {
            if (current.status === "draft") await context.api.approve(page.id, current.id, page.version);
            else await context.api.rollback(page.id, current.id, page.version);
            setConfirmed(false); setSelected(null); state.reload(); onChanged();
          }, "版本操作已确认。原始资料和历史版本保持不变。")}>
          {current.status === "draft" ? "确认发布此版本" : "确认回退到此版本"}
        </button>
      </div>}
    </>}
    {action.feedback}
    {page.space === "technical" && <form className="proposal-form" onSubmit={(event) => {
      event.preventDefault(); void action.act(async () => {
        const run = await context.api.propose(page.id, instructions); navigate("run", run.id);
      });
    }}><label>让 Agent 提出改动（不会自行发布）<textarea minLength={3} maxLength={2000} required value={instructions}
      onChange={(event) => setInstructions(event.target.value)} placeholder="例如：按准备、观察、练习重新组织现有资料；不要新增未有依据的技术结论。" /></label>
      <button className="button secondary" disabled={action.busy || !context.online}>生成待审阅提案</button></form>}
  </section>;
}

export function WikiView({ id, context, onSpaceChange }: {
  id: string; context: ViewContext; onSpaceChange?: (space: Space) => void;
}) {
  const state = useLoad(useCallback(async () => {
    if (context.online) return context.api.wiki(id);
    const saved = await context.offline.getSavedWiki(id);
    if (!saved) throw new Error("这篇 Wiki 没有保存在本机。请联网后打开并选择“离线保存”。");
    return saved.value;
  }, [context.api, context.offline, context.online, id]));
  const action = useAction();
  const [review, setReview] = useState(false);
  const [selected, setSelected] = useState<string | null>(null);
  const [tab, setTab] = useState<"sources" | "agent">("sources");
  const labels = useMemo(() => state.data ? citationLabels(state.data.sections, state.data.citations)
    : new Map<string, string>(), [state.data]);
  useEffect(() => {
    if (state.data) onSpaceChange?.(state.data.space);
  }, [state.data, onSpaceChange]);
  if (state.loading) return <Loading />;
  if (state.error || !state.data) return <Failure message={state.error ?? "未取得页面。"} retry={state.reload} />;
  const page = state.data;
  const select = (evidenceId: string) => {
    setSelected(evidenceId);
    setTab("sources");
  };
  return <div className="reader-workspace">
    <article className="reading-pane"><div className="reading-column">
      <a href={page.space === "personal" ? "#/personal" : "#/knowledge"} className="back-link">← {page.space === "personal" ? "我的训练 Wiki" : "技术 Wiki"}</a>
      <p className="eyebrow">{page.space === "personal" ? "PERSONAL WIKI" : "TECHNICAL WIKI"}</p>
      <div className="chip-row">{pageStatuses(page).map((status) => <StatusChip key={status.label} status={status} />)}</div>
      <h1>{page.title}</h1>
      <div className="page-meta"><span>{page.topic}</span><span>{page.citations.length} 个来源</span><span>{formatDate(page.updated_at)}</span></div>
      {!context.online && <Notice>本机保存的版本可能不是最新版本，原有证据标记已保留。</Notice>}
      {page.status === "draft" && <Notice warning>草稿尚未成为正式技术依据。请在下面核对原文与引用，再决定是否发布。</Notice>}
      {page.status === "published" && page.has_draft && <Notice>还有一份改动等待审阅，当前展示的仍是已发布版本。请打开“查看变更 / 审阅 / 回退”。</Notice>}
      {page.status === "empty" && <Notice>原始记录已保留，Wiki 尚未整理完成。请到原始记录查看 Agent 运行状态。</Notice>}
      <div className="button-row">
        <button className="button secondary small" disabled={action.busy || !context.online}
          onClick={() => void action.act(async () => { await context.offline.saveWiki(page); }, "页面及原始引用已保存到本机。系统清理网站数据仍可能移除此副本。")}>离线保存</button>
        <a className="button secondary small" href={linkTo("preview", page.id)}>生成训练卡预览</a>
        <button className="button secondary small" disabled={!context.online} onClick={() => setReview((value) => !value)}>
          {review ? "收起版本" : "查看变更 / 审阅 / 回退"}</button>
        {context.online && <a className="text-link" href={`/api/v1/wiki/${encodeURIComponent(page.id)}/export`} download>导出 Markdown</a>}
      </div>
      {action.feedback}
      {page.sections.length
        ? <SourcedContent sections={page.sections} citations={page.citations} labels={labels} selectedId={selected} onSelect={select} />
        : <SafeMarkdown text={page.content} />}
      {(review || page.status === "draft") && context.online && <VersionReview page={page} context={context} onChanged={state.reload} />}
    </div></article>
    <aside className="reader-aside" aria-label="来源与提问">
      <div className="panel-tabs" role="tablist" aria-label="来源与提问">
        <button type="button" role="tab" aria-selected={tab === "sources"} onClick={() => setTab("sources")}>
          来源 <small>{page.citations.length}</small></button>
        <button type="button" role="tab" aria-selected={tab === "agent"} onClick={() => setTab("agent")}>问 Agent</button>
      </div>
      <div role="tabpanel" aria-label={tab === "sources" ? "来源" : "问 Agent"}>
        {tab === "sources"
          ? <EvidencePanel citations={page.citations} labels={labels} selectedId={selected} onSelect={select} onClose={() => setSelected(null)} />
          : <AgentPanel context={context} page={page} />}
      </div>
    </aside>
    {selected && <div className="sheet-scrim" aria-hidden="true" onClick={() => setSelected(null)} />}
  </div>;
}

export function EvidenceView({ id, context }: { id: string; context: ViewContext }) {
  const state = useLoad(useCallback(async () => {
    if (context.online) return context.api.evidence(id);
    const saved = await context.offline.getSavedEvidence(id);
    if (!saved) throw new Error("这份原始来源没有保存在本机。");
    return saved.value;
  }, [context.api, context.offline, context.online, id]));
  const action = useAction();
  if (state.loading) return <Loading />;
  if (state.error || !state.data) return <Failure message={state.error ?? "来源不可用。"} retry={state.reload} />;
  const evidence = state.data;
  const sourceUrl = safeHref(evidence.source_url);
  return <article className="workspace-pane narrow">
    <a href="#/knowledge" className="back-link">← 知识库</a>
    <p className="eyebrow">{evidence.kind === "technical" ? "ORIGINAL SOURCE" : "ORIGINAL JOURNAL"}</p>
    <h1>{evidence.title}</h1><span className="tag">{evidence.kind === "technical" ? "技术资料原始快照" : "本人原始记录 · 不是技术结论"}</span>
    <p className="revision-text">来源版本：{evidence.revision}</p>
    {!context.online && <Notice>正在阅读明确保存到本机的来源版本。</Notice>}
    <div className="button-row"><button className="button secondary" disabled={action.busy}
      onClick={() => void action.act(async () => { await context.offline.saveEvidence(evidence); }, "原始来源已保存到本机。")}>离线保存原文</button>
      {sourceUrl && <a href={sourceUrl} target="_blank" rel="noopener noreferrer" referrerPolicy="no-referrer" className="button secondary">打开原始链接 ↗</a>}</div>
    {action.feedback}<div className="source-excerpt"><h2>被引用的片段</h2><SafeMarkdown text={evidence.excerpt} /></div>
    <h2>完整原始内容</h2><SafeMarkdown text={evidence.content} />
  </article>;
}
