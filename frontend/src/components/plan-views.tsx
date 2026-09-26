"use client";

import { useCallback, useState } from "react";
import type { Plan, Preview } from "../lib/contracts";
import { formatDate, linkTo, navigate } from "../lib/navigation";
import { newDraft, type LocalDraft } from "../lib/offline";
import type { ViewContext } from "./app-shell";
import { Citations, SafeMarkdown, SourcedContent } from "./content";
import { Failure, Loading, Notice, useAction, useLoad } from "./ui";

export function PlansView({ context }: { context: ViewContext }) {
  const state = useLoad(useCallback(async () => context.online ? context.api.plans()
    : (await context.offline.listSavedPlans()).map((item) => item.value), [context.api, context.offline, context.online]));
  return <section className="workspace-pane"><header className="section-heading"><div>
    <p className="eyebrow">TRAINING CARDS</p><h1>这一场，只练一件事。</h1><p className="muted">你采用的训练安排，来源和模型补充分开放。</p></div>
    <a href="#/preview" className="button">预览一张新训练卡</a></header>
    {!context.online && <Notice>离线只显示你已保存的训练卡。</Notice>}
    {state.loading ? <Loading /> : state.error ? <Failure message={state.error} retry={state.reload} /> :
      !state.data?.length ? <div className="empty-state"><div className="empty-court" /><h2>还没有采用的训练卡</h2><p>先阅读一个主题，再将有用的内容变成可调整的练习。</p><a href="#/knowledge" className="button secondary">去知识库看看</a></div> :
      <div className="library-grid">{state.data.map((plan) => <a href={linkTo("plan", plan.id)} key={plan.id} className="topic-card">
        <div className="row"><span className="eyebrow">SESSION / {plan.id}</span><span className="tag">{plan.drills.length} 项练习</span></div>
        <h2>{plan.title}</h2><p>{plan.focus_area}</p><footer><span>{formatDate(plan.created_at)}</span><span>打开 →</span></footer>
      </a>)}</div>}
  </section>;
}

export function PreviewView({ context, pageId }: { context: ViewContext; pageId?: string }) {
  const [query, setQuery] = useState("");
  const [personal, setPersonal] = useState(false);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [edited, setEdited] = useState("");
  const [confirmed, setConfirmed] = useState(false);
  const action = useAction();
  return <section className="workspace-pane narrow"><a href="#/plans" className="back-link">← 我的训练卡</a>
    <p className="eyebrow">PLAN / PREVIEW BEFORE ADOPTION</p><h1>先看看，再决定是否去练。</h1>
    <p className="muted">问题越具体，越容易找到相关的资料和个人观察。不会自动采用生成结果。</p>
    {pageId && <a href={linkTo("wiki", pageId)} className="text-link">查看关联 Wiki →</a>}
    <form className="form-stack" onSubmit={(event) => { event.preventDefault(); void action.act(async () => {
      const result = await context.api.preview({ query, page_id: pageId || null, include_personal: personal });
      setPreview(result); setConfirmed(false); setEdited("");
    }); }}>
      <label>这次想关注什么<textarea value={query} required minLength={3} maxLength={2000} onChange={(event) => setQuery(event.target.value)}
        placeholder="例如：我的正手来球一快就容易失去空间；这次有 20 分钟练习。" /></label>
      <label className="check-label"><input type="checkbox" checked={personal} onChange={(event) => setPersonal(event.target.checked)} />同时使用我的训练经历</label>
      <p className="privacy-note">新生成需要联网。选中的资料及允许使用的个人上下文会发送到服务器配置的模型供应商。</p>
      <button className="button" disabled={!context.online || action.busy}>{action.busy ? "正在组织训练预览…" : "生成训练卡预览"}</button>
    </form>
    {action.feedback}
    {!context.online && <Notice>离线时可以打开已保存训练卡，但不能请求新的模型生成。</Notice>}
    {preview && <div className="plan-preview">
      <h2>{preview.title}</h2><p className="muted">{preview.focus_area}</p>
      {preview.warning && <Notice warning>{preview.warning}</Notice>}
      <SourcedContent sections={preview.sections} citations={preview.citations} />
      <h2>练习编排</h2><Notice warning>以下动作安排、顺序与组数均作为模型补充展示，未经知识库核验。</Notice>
      <ol className="drill-list">{preview.drills.map((drill, index) => <li key={index}>
        <span className="drill-number">{String(index + 1).padStart(2, "0")}</span><div><h3>{drill.name}</h3><p>{drill.description}</p></div>
      </li>)}</ol>
      <label>我的调整或备注（可选）<textarea value={edited} maxLength={20000} onChange={(event) => setEdited(event.target.value)} /></label>
      <label className="check-label"><input type="checkbox" checked={confirmed} onChange={(event) => setConfirmed(event.target.checked)} />
        我已查看依据与未核验内容，决定采用这张卡</label>
      <button className="button" disabled={!confirmed || !context.online || action.busy} onClick={() => void action.act(async () => {
        const plan = await context.api.adopt(preview.preview_id, edited || null); navigate("plan", plan.id);
      })}>确认采用，保存训练卡</button>
    </div>}
  </section>;
}

function PlanEditor({ plan, context, done }: { plan: Plan; context: ViewContext; done: () => void }) {
  const [title, setTitle] = useState(plan.title);
  const [note, setNote] = useState(plan.edited_content ?? "");
  const [drills, setDrills] = useState(plan.drills.map(({ id, name, description }) => ({ id, name, description })));
  const action = useAction();
  return <form className="form-stack edit-panel" onSubmit={(event) => { event.preventDefault(); void action.act(async () => {
    await context.api.editPlan(plan.id, { title, edited_content: note, drills }); done();
  }); }}>
    <h2>我的调整</h2><p className="muted">调整不会改变原始模型输出和来源记录。</p>
    <label>卡片标题<input required maxLength={200} value={title} onChange={(event) => setTitle(event.target.value)} /></label>
    <label>备注<textarea value={note} maxLength={20000} onChange={(event) => setNote(event.target.value)} /></label>
    {drills.map((drill, index) => <fieldset key={drill.id}><legend>练习 {index + 1}</legend>
      <label>名称<input required maxLength={200} value={drill.name} onChange={(event) => setDrills((items) =>
        items.map((item) => item.id === drill.id ? { ...item, name: event.target.value } : item))} /></label>
      <label>内容<textarea required maxLength={2000} value={drill.description} onChange={(event) => setDrills((items) =>
        items.map((item) => item.id === drill.id ? { ...item, description: event.target.value } : item))} /></label>
    </fieldset>)}
    {action.feedback}<button className="button" disabled={action.busy || !context.online}>保存我的调整</button>
  </form>;
}

function PracticeCard({ plan, context }: { plan: Plan; context: ViewContext }) {
  const [draft, setDraft] = useState<LocalDraft | null>(null);
  const action = useAction();
  const stored = useLoad(useCallback(async () => (await context.offline.listDrafts()).find((item) =>
    item.plan_id === plan.id && item.state === "editable"), [context.offline, plan.id]));
  const current = draft ?? stored.data;
  const update = async (drillId: number, checked: boolean) => {
    const next = current ?? newDraft({ plan_id: plan.id, page_id: plan.wiki_page_id });
    const completed = checked ? [...next.completed_drill_ids, drillId]
      : next.completed_drill_ids.filter((id) => id !== drillId);
    setDraft(await context.offline.saveDraft({ ...next, completed_drill_ids: completed }));
  };
  return <section className="practice-card"><div className="row"><h2>一次只看一个练习</h2><span className="tag">{current?.completed_drill_ids.length ?? 0} / {plan.drills.length}</span></div>
    <p className="muted">休息时勾选即可。状态保存在本机草稿，尚未提交或同步到电脑。</p>
    {stored.error && <Notice warning>{stored.error}</Notice>}
    <div className="practice-list">{plan.drills.map((drill, index) => <label className="practice-step" key={drill.id}>
      <input type="checkbox" disabled={stored.loading || action.busy || !!stored.error}
        checked={current?.completed_drill_ids.includes(drill.id) ?? false}
        onChange={(event) => void action.act(() => update(drill.id, event.target.checked), "完成状态已存入本机草稿。")} />
      <span className="drill-number">{String(index + 1).padStart(2, "0")}</span>
      <span><strong>{drill.name}</strong><span className="drill-description">{drill.description}</span></span>
    </label>)}</div>
    <p className="privacy-note">练习编排和组数未经知识库核验。可撤销勾选，也可以跳过；出现不适时停止练习。</p>
    {action.feedback}
    <button className="button" disabled={stored.loading || action.busy || !!stored.error}
      onClick={() => void action.act(async () => {
        const next = current ?? await context.offline.saveDraft(newDraft({ plan_id: plan.id, page_id: plan.wiki_page_id }));
        navigate("draft", next.client_id);
      })}>结束，留一句练后感受 →</button>
  </section>;
}

export function PlanView({ id, context }: { id: number; context: ViewContext }) {
  const state = useLoad(useCallback(async () => {
    if (!Number.isSafeInteger(id) || id < 1) throw new Error("训练卡编号无效。");
    if (context.online) return context.api.plan(id);
    const saved = await context.offline.getSavedPlan(id);
    if (!saved) throw new Error("这张卡没有保存到本机。请联网后打开并选择离线保存。");
    return saved.value;
  }, [context.api, context.offline, context.online, id]));
  const [editing, setEditing] = useState(false);
  const action = useAction();
  if (state.loading) return <Loading />;
  if (state.error || !state.data) return <Failure message={state.error ?? "训练卡不可用。"} retry={state.reload} />;
  const plan = state.data;
  return <article className="workspace-pane narrow"><a href="#/plans" className="back-link">← 我的训练卡</a>
    <p className="eyebrow">ONE FOCUS / SESSION {plan.id}</p><h1>{plan.title}</h1><p className="muted">{plan.focus_area}</p>
    {!context.online && <Notice>离线查看本机保存版本，完成记录也只在本机。</Notice>}
    <div className="button-row"><button className="button secondary" disabled={action.busy || !context.online}
      onClick={() => void action.act(async () => { await context.offline.savePlan(plan); }, "训练卡和原始来源已保存，可离线查阅。")}>离线保存这张卡</button>
      <button className="button secondary" disabled={!context.online} onClick={() => setEditing(!editing)}>调整训练卡</button>
      {plan.wiki_page_id && <a className="text-link" href={linkTo("wiki", plan.wiki_page_id)}>回到关联 Wiki</a>}</div>
    {action.feedback}
    {editing ? <PlanEditor key={plan.updated_at} plan={plan} context={context} done={() => { setEditing(false); state.reload(); }} /> :
      <PracticeCard plan={plan} context={context} />}
    {plan.edited_content && <section className="owner-note"><h2>我的调整与备注</h2><SafeMarkdown text={plan.edited_content} /></section>}
    <details><summary>查看原始说明、资料支持与模型补充</summary>
      <SourcedContent sections={plan.sections} citations={plan.citations} /><Citations citations={plan.citations} /></details>
  </article>;
}
