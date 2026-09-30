"use client";

import { useCallback, useEffect, useState } from "react";
import { formatDate, linkTo, navigate } from "../lib/navigation";
import { newDraft, type LocalDraft } from "../lib/offline";
import type { Journal, WikiSummary } from "../lib/contracts";
import { draftStatus, pipeline, runStatus } from "../lib/status";
import type { ViewContext } from "./app-shell";
import { PipelineStepper, StatusChip } from "./status";
import { Failure, Loading, Notice, downloadJson, useAction, useLoad } from "./ui";

export function DraftsView({ context }: { context: ViewContext }) {
  const state = useLoad(useCallback(() => context.offline.listDrafts(), [context.offline]));
  const action = useAction();
  return <section className="workspace-pane narrow"><p className="eyebrow">ON THIS DEVICE</p><h1>先记下来，不急着上传。</h1>
    <p className="muted">草稿只在当前设备。系统清理网站数据可能删除草稿，本机保存不是备份。</p>
    <div className="button-row"><button className="button" disabled={action.busy} onClick={() => void action.act(async () => {
      const draft = await context.offline.saveDraft(newDraft()); navigate("draft", draft.client_id);
    })}>新建训练记录</button><a href="#/records" className="button secondary">查看已提交原始记录</a></div>
    {action.feedback}
    {state.loading ? <Loading /> : state.error ? <Failure message={state.error} retry={state.reload} /> : !state.data?.length ?
      <div className="empty-state"><h2>本机没有待提交的草稿</h2><p>可以先新建一句记录，或从训练卡勾选完成后进入这里。</p></div> :
      <div className="record-list">{state.data.map((draft) => <a href={linkTo("draft", draft.client_id)} className="record-card" key={draft.client_id}>
        <StatusChip status={draftStatus(draft.state)} />
        <h2>{draft.content ? draft.content.slice(0, 85) : "尚未填写感受"}</h2>
        <p>{draft.completed_drill_ids.length} 项完成记录 · {formatDate(draft.updated_at)}</p><span className="text-link">打开草稿 →</span>
      </a>)}</div>}
  </section>;
}

function DraftEditor({ original, topics, context }: { original: LocalDraft; topics: WikiSummary[]; context: ViewContext }) {
  const [draft, setDraft] = useState(original);
  const [dirty, setDirty] = useState(false);
  const [confirmed, setConfirmed] = useState(false);
  const [receipt, setReceipt] = useState<Journal | null>(null);
  const action = useAction();
  useEffect(() => {
    const warn = (event: BeforeUnloadEvent) => {
      if (dirty) { event.preventDefault(); event.returnValue = ""; }
    };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirty]);
  const change = (patch: Partial<LocalDraft>) => {
    setDraft((value) => ({ ...value, ...patch })); setDirty(true); setConfirmed(false);
  };
  const save = async () => {
    const saved = await context.offline.saveDraft(draft);
    setDraft(saved); setDirty(false);
    return saved;
  };
  const locked = draft.state === "locked";
  if (receipt) return <div className="workspace-pane narrow"><p className="eyebrow">ORIGINAL SAVED</p><h1>原话已保存，接下来整理线索。</h1>
    <Notice>服务端回执与本机回执都已保存。Wiki 更新是下一步任务，不等于记录保存。</Notice>
    <PipelineStepper stages={pipeline({ dirty: false, locked: false, receipt: true, online: context.online,
      run: receipt.run_id ? "unknown" : null })} />
    <p className="owner-quote">{receipt.content || "已保留练习完成记录。"}</p>
    {receipt.run_id && <a className="button" href={linkTo("run", receipt.run_id)}>查看 Agent 整理状态</a>}
    <div className="button-row"><a href="#/records" className="text-link">查看原始记录</a><a href="#/personal" className="text-link">我的训练 Wiki</a></div>
  </div>;
  return <section className="workspace-pane narrow"><a href="#/drafts" className="back-link" onClick={(event) => {
    if (dirty && !window.confirm("当前输入还没保存到本机。确定离开吗？")) event.preventDefault();
  }}>← 本机草稿</a>
    <p className="eyebrow">AFTER THE COURT</p><h1>记一个场景，留一句感受。</h1>
    <StatusChip status={draftStatus(draft.state, dirty)} />
    <PipelineStepper stages={pipeline({ dirty, locked, receipt: false, online: context.online, run: null })} />
    {locked && <Notice warning>之前的提交可能已经到达服务器。保留相同编号与原始内容核对重试，避免重复记录。</Notice>}
    <form className="form-stack" onSubmit={(event) => { event.preventDefault(); void action.act(async () => { await save(); }, "原话已保存到本机草稿，尚未同步到电脑。"); }}>
      <label>关联 Wiki 主题<select disabled={locked || action.busy} value={draft.page_id ?? ""} onChange={(event) => change({ page_id: event.target.value || null })}>
        <option value="">暂不分类，让原始记录先保留</option>
        {draft.page_id && !topics.some((topic) => topic.id === draft.page_id) && <option value={draft.page_id}>已关联的主题（离线未保存标题）</option>}
        {topics.map((topic) => <option value={topic.id} key={topic.id}>{topic.space === "personal" ? "我的 / " : "技术 / "}{topic.title}</option>)}
      </select></label>
      <label>什么时候最明显（可选）<input disabled={locked || action.busy} maxLength={500} value={draft.context ?? ""} onChange={(event) => change({ context: event.target.value || null })} placeholder="例如：来球变快、移动之后、长回合…" /></label>
      <label>我的原话<textarea disabled={locked || action.busy} maxLength={10000} value={draft.content} onChange={(event) => change({ content: event.target.value })}
        placeholder="记录自己实际注意到的事情，不需要先给出技术结论。" /></label>
      <label>主观感受（可选）<input disabled={locked || action.busy} maxLength={500} value={draft.feeling ?? ""} onChange={(event) => change({ feeling: event.target.value || null })} placeholder="例如：有一点线索，还需要继续观察。" /></label>
      <p className="muted">{draft.completed_drill_ids.length} 项练习已勾选完成{draft.plan_id ? ` · 关联训练卡 ${draft.plan_id}` : ""}。</p>
      <div className="button-row"><button className="button secondary" disabled={locked || action.busy}>保存到本机</button>
        <button className="button secondary" type="button" onClick={() => downloadJson(draft, `open-tennis-draft-${draft.client_id}.json`)}>导出当前草稿</button></div>
    </form>
    <section className="submit-panel">
      <h2>{context.online ? "联网后，确认提交。" : "离线草稿，不会悄悄上传。"}</h2>
      <p className="muted">提交后原始记录保持原样。若服务器已启用个人内容处理，Agent 会将最小必要记录发送到配置的模型供应商，自动整理个人 Wiki；技术改动仍需审阅。</p>
      <label className="check-label"><input type="checkbox" checked={confirmed} disabled={!context.online || action.busy}
        onChange={(event) => setConfirmed(event.target.checked)} />我确认提交这条原始记录，并理解后续的 Wiki 整理规则</label>
      <button className="button" disabled={!confirmed || !context.online || action.busy} onClick={() => void action.act(async () => {
        const persisted = dirty ? await save() : draft;
        try {
          const result = await context.offline.confirmAndSubmit(persisted.client_id, { confirmed: true, revision: persisted.revision });
          setReceipt(result); setDirty(false);
        } finally {
          const latest = await context.offline.getDraft(persisted.client_id);
          if (latest) setDraft(latest);
        }
      })}>{action.busy ? "正在确认提交…" : locked ? "用相同编号核对重试" : "本人确认，提交到服务器"}</button>
    </section>
    {action.feedback}
    <p className="privacy-note">没有感受时也可以提交已有的完成状态。只写感受、未勾选练习也可以保存；完全空白的记录不能提交。</p>
  </section>;
}

export function DraftView({ id, context }: { id: string; context: ViewContext }) {
  const state = useLoad(useCallback(async () => {
    const draft = await context.offline.getDraft(id);
    if (!draft) {
      const receipt = await context.offline.getReceipt(id);
      if (receipt) return { receipt: receipt.journal, draft: null };
      throw new Error("这台设备没有这份草稿，请检查原设备或导出文件。");
    }
    return { draft, receipt: null };
  }, [context.offline, id]));
  const topics = useLoad(useCallback(async () => context.online
    ? (await Promise.all([context.api.listWiki("technical"), context.api.listWiki("personal")])).flat()
    : (await Promise.all([context.offline.listSavedWiki("technical"), context.offline.listSavedWiki("personal")])).flat().map((item) => item.value),
  [context.api, context.offline, context.online]));
  if (state.loading) return <Loading />;
  if (state.error || !state.data) return <Failure message={state.error ?? "草稿未打开。"} retry={state.reload} />;
  if (state.data.receipt) return <section className="workspace-pane narrow"><Notice>这条记录已有服务端回执，不会重复创建。</Notice>
    {state.data.receipt.run_id && <a href={linkTo("run", state.data.receipt.run_id)} className="button">查看整理状态</a>}<a href="#/records" className="text-link">查看原始记录</a></section>;
  if (!state.data.draft) return <Notice warning>草稿状态无效，无法编辑。</Notice>;
  return <>{topics.error && <Notice warning>主题列表暂时不可用，但你可以继续编辑本机草稿。{topics.error}</Notice>}
    <DraftEditor key={id} original={state.data.draft} topics={topics.data ?? []} context={context} /></>;
}

export function RecordsView({ context }: { context: ViewContext }) {
  const state = useLoad(useCallback(async () => context.online ? context.api.journals()
    : (await context.offline.listReceipts()).map((receipt) => receipt.journal), [context.api, context.offline, context.online]));
  return <section className="workspace-pane narrow"><p className="eyebrow">YOUR ORIGINAL WORDS</p><h1>这里保留你的原话。</h1>
    <p className="muted">个人 Wiki 是派生理解；这里的训练记录不被 Agent 覆盖，也不被当作技术效果的证明。</p>
    <div className="button-row"><a className="button" href="#/drafts">写一条记录</a><a className="button secondary" href="#/personal">回到我的 Wiki</a></div>
    {!context.online && <Notice>仅显示本机留存的提交回执，并非全部服务端历史。</Notice>}
    {state.loading ? <Loading /> : state.error ? <Failure message={state.error} retry={state.reload} /> : !state.data?.length ?
      <div className="empty-state"><h2>还没有已确认的记录</h2><p>可以先在本机写草稿，联网后再提交。</p></div> :
      <div className="record-list">{state.data.map((record) => <article className="record-card" key={record.id}>
        <div className="row"><span className="tag">本人原始记录</span><time>{formatDate(record.created_at)}</time></div>
        <p className="owner-quote">{record.content || "记录了本次练习完成状态。"}</p>
        {record.context && <p className="muted">情境：{record.context}</p>}
        {record.feeling && <p className="muted">主观感受：{record.feeling}</p>}
        <div className="button-row">{record.run_id && <a href={linkTo("run", record.run_id)} className="text-link">查看整理状态 →</a>}
          {record.plan_id && <a href={linkTo("plan", record.plan_id)} className="text-link">关联训练卡</a>}</div>
      </article>)}</div>}
  </section>;
}

const runHeadings = { queued: "等待整理", running: "Agent 正在整理", succeeded: "整理任务已完成", failed: "整理失败，原始记录仍在", needs_input: "需要本人确认后再继续" };

export function RunView({ id, context }: { id: string; context: ViewContext }) {
  const state = useLoad(useCallback(async () => {
    if (!context.online) throw new Error("离线无法确认服务端 Agent 状态。原始本机草稿不会自动提交。");
    return context.api.run(id);
  }, [context.api, context.online, id]));
  const action = useAction();
  useEffect(() => {
    if (state.data && ["queued", "running"].includes(state.data.status)) {
      const timer = setTimeout(state.reload, 2500);
      return () => clearTimeout(timer);
    }
  }, [state.data, state.reload]);
  if (state.loading && !state.data) return <Loading />;
  if (state.error || !state.data) return <Failure message={state.error ?? "任务状态未知。"} retry={state.reload} />;
  const run = state.data;
  return <section className="workspace-pane narrow"><p className="eyebrow">AGENT / RUN</p><h1>{runHeadings[run.status]}</h1>
    <StatusChip status={runStatus(run.status)} />
    {run.entry_id && <PipelineStepper stages={pipeline({ dirty: false, locked: false, receipt: true, online: context.online,
      run: run.status, updated: Boolean(run.result_version_id) })} />}
    <p className="revision-text">运行编号：{run.id}</p>
    <Notice warning={run.status === "failed" || run.status === "needs_input"}>{run.error_message ??
      (run.kind === "technical_wiki" ? "技术 Wiki 任务只提出改动，发布仍需你的审阅。" : "Agent 只更新派生 Wiki；原始记录与历史版本不会被覆盖。")}</Notice>
    {run.error_code && <p className="revision-text">错误类型：{run.error_code}</p>}
    <p className="muted">最后更新：{formatDate(run.updated_at)}</p>
    {["queued", "running"].includes(run.status) && <p className="muted">这个页面会刷新运行状态。关闭页面不会取消已登记的整理任务；Agent 未启用时任务会等待。</p>}
    <div className="button-row">{run.page_id && <a className="button" href={linkTo("wiki", run.page_id)}>打开关联 Wiki / 版本</a>}
      {["failed", "needs_input"].includes(run.status) && <button className="button secondary" disabled={action.busy || !context.online}
        onClick={() => void action.act(async () => { await context.api.retryRun(run.id); state.reload(); })}>本人确认，重试整理</button>}
      <a href="#/records" className="text-link">查看原始记录</a></div>
    {action.feedback}
  </section>;
}

export function DeviceView({ context }: { context: ViewContext }) {
  const state = useLoad(useCallback(() => context.offline.exportData(), [context.offline]));
  const [confirmed, setConfirmed] = useState(false);
  const action = useAction();
  return <section className="workspace-pane narrow"><p className="eyebrow">PRIVATE DEVICE</p><h1>你的资料，也留一份在手边。</h1>
    <p className="muted">在手机浏览器中使用“添加到主屏幕”安装 PWA。iPhone 通常需要在 Safari 的分享菜单中操作；是否可安装取决于浏览器和 HTTPS 环境。</p>
    <Notice>新 Agent 调用需要联网。只有明确保存的页面、原始来源和训练卡可离线阅读；本机草稿联网后也不会自动上传。</Notice>
    {state.loading ? <Loading /> : state.error ? <Failure message={state.error} retry={state.reload} /> : state.data && <>
      <div className="device-summary"><span><strong>{state.data.saved.length}</strong>本机保存项目</span>
        <span><strong>{state.data.drafts.length}</strong>草稿</span><span><strong>{state.data.receipts.length}</strong>提交回执</span></div>
      <div className="button-row"><button className="button" onClick={() => void action.act(async () => {
        downloadJson(await context.offline.exportData(), "open-tennis-device-export.json");
      })}>导出本机内容与草稿</button><a href="#/drafts" className="button secondary">打开本机草稿</a></div>
      <div className="saved-list">{state.data.saved.map((item) => <div className="row" key={item.key}>
        <a className="text-link" href={linkTo(item.kind === "evidence" ? "evidence" : item.kind, item.value.id)}>{item.value.title}</a>
        <span className="tag">{item.kind} · {formatDate(item.saved_at)}</span>
      </div>)}</div>
    </>}
    <section className="submit-panel"><h2>清除这台设备的保存内容</h2>
      <p className="muted">这不会删除服务端记录，但未提交草稿将无法从服务器恢复。导出文件含个人内容，请妥善保存。浏览器清理网站数据也可能移除本机内容。</p>
      <label className="check-label"><input type="checkbox" checked={confirmed} onChange={(event) => setConfirmed(event.target.checked)} />我已导出需要保留的内容，确认清除本机数据</label>
      <button className="button danger" disabled={!confirmed || action.busy} onClick={() => void action.act(async () => {
        await context.offline.clearDeviceData(); setConfirmed(false); state.reload();
      }, "本机保存的数据已清除。服务端内容没有删除。")}>确认清除本机数据</button>
    </section>{action.feedback}
  </section>;
}
