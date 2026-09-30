"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { ApiClient } from "../lib/api";
import { OfflineClient } from "../lib/offline";
import { formatDate, linkTo, navigate } from "../lib/navigation";
import type { Space } from "../lib/contracts";
import { connectionStatus, pageStatuses } from "../lib/status";
import { Failure, Loading, Notice, useAction, useLoad } from "./ui";
import { Icon, type IconName } from "./icons";
import { StatusChip } from "./status";
import { ThemeToggle } from "./theme-toggle";
import { EvidenceView, WikiView } from "./wiki-views";
import { PlansView, PlanView, PreviewView } from "./plan-views";
import { DeviceView, DraftsView, DraftView, RecordsView, RunView } from "./journal-views";

const defaultApi = new ApiClient();

export type ViewContext = { api: ApiClient; offline: OfflineClient; online: boolean };
type Section = "knowledge" | "plans" | "records" | "personal";

const navItems: { key: Section; href: string; label: string; icon: IconName }[] = [
  { key: "knowledge", href: "#/knowledge", label: "知识", icon: "book" },
  { key: "plans", href: "#/plans", label: "训练", icon: "court" },
  { key: "records", href: "#/drafts", label: "记录", icon: "pen" },
  { key: "personal", href: "#/personal", label: "我的 Wiki", icon: "note" },
];

function sectionOf(route: { kind: string; id: string }, wikiSpace: Space): Section | null {
  if (["plans", "plan", "preview"].includes(route.kind)) return "plans";
  if (["records", "drafts", "draft", "run"].includes(route.kind) ||
    (route.kind === "evidence" && route.id.startsWith("journal:"))) return "records";
  if (route.kind === "personal" || (route.kind === "wiki" && wikiSpace === "personal")) return "personal";
  if (["knowledge", "wiki", "evidence"].includes(route.kind)) return "knowledge";
  return null;
}

function DraftBadge({ count }: { count: number }) {
  return count ? <span className="nav-badge" aria-hidden="true">{count}</span> : null;
}

function DraftNote({ count }: { count: number }) {
  return count ? <span className="sr-only">，本机 {count} 条草稿未提交</span> : null;
}

function NavLinks({ section, drafts, icons }: { section: Section | null; drafts: number; icons: boolean }) {
  return <>{navItems.map((item) => {
    const count = item.key === "records" ? drafts : 0;
    return <a key={item.key} href={item.href} aria-current={section === item.key ? "page" : undefined}>
      {icons && <span className="nav-icon"><Icon name={item.icon} size={22} /><DraftBadge count={count} /></span>}
      {item.label}
      {!icons && <DraftBadge count={count} />}
      <DraftNote count={count} />
    </a>;
  })}</>;
}

function Brand() {
  return <a href="#/knowledge" className="brand" aria-label="Open Tennis 知识首页">
    <svg viewBox="0 0 64 64" aria-hidden="true"><path d="M41 19A19 19 0 1 0 42 47" fill="none" stroke="currentColor" strokeWidth="7" />
      <path d="M29 12h23M41 12v22" fill="none" stroke="currentColor" strokeWidth="6" />
      <path d="M7 55Q23 30 52 22" fill="none" stroke="#c4a34b" strokeWidth="2.6" />
      <circle cx="54" cy="12" r="4.5" fill="#c4a34b" /></svg>
    <span>open <em>tennis</em></span>
  </a>;
}

export function LibraryView({ context, space }: { context: ViewContext; space: Space }) {
  const { api, offline, online } = context;
  const [query, setQuery] = useState("");
  const action = useAction();
  const loader = useCallback(async () => ({
    pages: online ? await api.listWiki(space, query)
      : (await offline.listSavedWiki(space, query)).map((item) => item.value),
  }), [api, offline, online, space, query]);
  const state = useLoad(loader);
  return <section className="workspace-pane">
    <header className="section-heading"><div><p className="eyebrow">{space === "technical" ? "TECHNICAL WIKI" : "PERSONAL WIKI"}</p>
      <h1>{space === "technical" ? "读懂一件事，再把它带上场。" : "让每次练习，留下一点线索。"}</h1>
      <p className="muted">{space === "technical" ? "先看来源，再形成自己的理解。" : "Agent 整理你的记录，原始表达始终保留。"}</p></div>
      {space === "personal" && <button className="button" onClick={() => navigate("drafts")}>写一条训练记录</button>}
    </header>
    {!online && <Notice>当前离线，只显示你明确保存过的页面，不代表完整资料库。</Notice>}
    {space === "personal" && <div className="button-row"><a className="text-link" href="#/records">查看原始记录</a><a className="text-link" href="#/drafts">本机草稿</a></div>}
    <label className="search-field"><span>搜索主题</span><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="正手、击球点、来球变快…" /></label>
    {action.feedback}
    {state.loading ? <Loading /> : state.error ? <Failure message={state.error} retry={state.reload} /> : state.data?.pages.length ? (
      <div className="library-grid">{state.data.pages.map((page) => <a className="topic-card" href={linkTo("wiki", page.id)} key={page.id}>
        <div className="chip-row">{pageStatuses(page).map((status) => <StatusChip key={status.label} status={status} />)}</div>
        <h2>{page.title}</h2><p>{page.topic}</p>
        <footer><span>{space === "personal" ? `${page.record_count} 条原始记录` : "阅读与来源"}</span><Icon name="chevron" size={16} /></footer>
        <small>{formatDate(page.updated_at)}</small>
      </a>)}</div>
    ) : <div className="empty-state"><div className="empty-court" aria-hidden="true" /><h2>{space === "technical" ? "你的知识库还没有资料" : "你的训练 Wiki 还没有主题"}</h2>
      <p>{space === "technical" ? "从服务器的现有教程目录导入，只创建待审阅草稿；你批准后才作为正式技术依据。" : "先记录一次练习。确认提交后，Agent 会在启用且获准使用个人内容时整理主题。"}</p>
      {space === "technical" && online && <button className="button" disabled={action.busy} onClick={() => void action.act(async () => {
        await api.importWiki(); state.reload();
      }, "导入完成。请打开页面，审阅原文与引用后再发布。")}>{action.busy ? "正在导入…" : "导入现有教程"}</button>}
      {space === "personal" && <a className="button" href="#/drafts">开始一条记录</a>}
    </div>}
  </section>;
}

export function AppShell({ api = defaultApi, offline: injected }: { api?: ApiClient; offline?: OfflineClient }) {
  const offline = useMemo(() => injected ?? new OfflineClient(api), [api, injected]);
  const [online, setOnline] = useState(true);
  const [route, setRoute] = useState({ kind: "knowledge", id: "" });
  const [wikiSpace, setWikiSpace] = useState<Space>("technical");
  const [systemMessage, setSystemMessage] = useState<string | null>(null);
  useEffect(() => {
    const connection = () => setOnline(navigator.onLine);
    const unreachable = () => setOnline(false);
    const location = () => {
      const [kind = "knowledge", encoded = ""] = window.location.hash.replace(/^#\/?/, "").split("/");
      try { setRoute({ kind: kind || "knowledge", id: decodeURIComponent(encoded) }); }
      catch { setSystemMessage("链接包含无效编号，请返回知识首页。"); }
    };
    connection(); location();
    window.addEventListener("online", connection);
    window.addEventListener("offline", connection);
    window.addEventListener("open-tennis:connection-lost", unreachable);
    window.addEventListener("hashchange", location);
    if ("serviceWorker" in navigator) {
      const offlineMessage = (event: MessageEvent) => {
        if (event.data?.type === "OFFLINE_ERROR") {
          setSystemMessage(event.data.code === "SHELL_REFRESH_FAILED"
            ? "暂时无法更新离线应用缓存，保留已有版本。知识页和训练卡是否可离线读取，以各自的保存状态为准。"
            : "应用页面未完整保存到本机。离线阅读可能不可用，请联网重试；不要把当前页面当作已保存的备份。");
        } else if (event.data?.type === "OFFLINE_READY") {
          setSystemMessage(null);
        }
      };
      navigator.serviceWorker.addEventListener("message", offlineMessage);
      navigator.serviceWorker.register("/sw.js")
        .then(() => navigator.serviceWorker.ready)
        .then((registration) => registration.active?.postMessage({ type: "PREPARE_SHELL" }))
        .catch(() => {
          setSystemMessage("离线页面暂时不可用。请保持联网；本机记录仍需单独确认保存状态。");
        });
      return () => {
        window.removeEventListener("online", connection);
        window.removeEventListener("offline", connection);
        window.removeEventListener("open-tennis:connection-lost", unreachable);
        window.removeEventListener("hashchange", location);
        navigator.serviceWorker.removeEventListener("message", offlineMessage);
        void offline.close().catch(() => console.warn("local_storage_close_failed"));
      };
    }
    return () => {
      window.removeEventListener("online", connection);
      window.removeEventListener("offline", connection);
      window.removeEventListener("open-tennis:connection-lost", unreachable);
      window.removeEventListener("hashchange", location);
      void offline.close().catch(() => console.warn("local_storage_close_failed"));
    };
  }, [offline]);
  const [drafts, setDrafts] = useState(0);
  useEffect(() => {
    let cancelled = false;
    offline.listDrafts().then(
      (items) => { if (!cancelled) setDrafts(items.length); },
      () => { if (!cancelled) setDrafts(0); },
    );
    return () => { cancelled = true; };
  }, [offline, route]);
  const statusLoader = useCallback(() => online ? api.status() : Promise.resolve(null), [api, online]);
  const status = useLoad(statusLoader);
  const context = { api, offline, online };
  const section = sectionOf(route, wikiSpace);
  return <div className="app-shell">
    <a className="skip-link" href="#main-content">跳到正文</a>
    <header className="app-header"><Brand /><span className="private-label">PRIVATE</span>
      <nav aria-label="主导航"><NavLinks section={section} drafts={drafts} icons={false} /></nav>
      <div className="header-status">
        {status.data && status.data.pending_reviews > 0 && <span className="review-chip">
          <StatusChip status={{ label: `待审阅 ${status.data.pending_reviews}`, tone: "warn", icon: "clock" }} /></span>}
        <a href="#/device" className="device-link" aria-label="本机草稿与离线设置"><StatusChip status={connectionStatus(online)} /></a>
        <ThemeToggle />
      </div>
    </header>
    <div className="shell-body"><aside className="sidebar"><p className="eyebrow">WIKI SPACES</p>
      <a className={section === "knowledge" ? "active" : ""} href="#/knowledge">技术 Wiki</a>
      <a className={section === "personal" ? "active" : ""} href="#/personal">我的训练 Wiki</a>
      <p className="eyebrow">ON &amp; OFF COURT</p>
      <a className={section === "plans" ? "active" : ""} href="#/plans">带去球场的训练卡</a>
      <a className={route.kind === "records" ? "active" : ""} href="#/records">原始训练记录</a>
      <a className={["drafts", "draft"].includes(route.kind) ? "active" : ""} href="#/drafts">本机草稿<DraftBadge count={drafts} /><DraftNote count={drafts} /></a>
      <a className={route.kind === "device" ? "active" : ""} href="#/device">离线保存与导出</a>
      <div className="sidebar-bottom"><strong>资料、记录、推测，分开放。</strong><p>原文不被 Agent 覆盖。每次理解，都能找到来处。</p>
        {status.data && <span>{status.data.sources_count} 份技术资料 · {status.data.pending_reviews} 项待审阅</span>}</div>
    </aside>
    <main id="main-content" tabIndex={-1}>
      {!online && <div className="connection-banner row"><span>连接不可用 · 只读已保存内容，草稿不会自动上传</span>
        <button className="button secondary small" onClick={() => { setOnline(navigator.onLine); status.reload(); }}>检测连接</button></div>}
      {systemMessage && <Notice warning>{systemMessage}</Notice>}
      {status.error && online && <Notice warning>{status.error}</Notice>}
      {status.data && (!status.data.agent_enabled || !status.data.model_configured) &&
        <div className="connection-banner">Agent 尚未启用或模型未配置。阅读与记录可用，整理任务会保留等待。</div>}
      {route.kind === "wiki" ? <WikiView key={route.id} id={route.id} context={context} onSpaceChange={setWikiSpace} /> :
        route.kind === "evidence" ? <EvidenceView key={route.id} id={route.id} context={context} /> :
        route.kind === "plans" ? <PlansView context={context} /> :
        route.kind === "plan" ? <PlanView key={route.id} id={Number(route.id)} context={context} /> :
        route.kind === "preview" ? <PreviewView key={route.id} context={context} pageId={route.id} /> :
        route.kind === "records" ? <RecordsView context={context} /> :
        route.kind === "drafts" ? <DraftsView context={context} /> :
        route.kind === "draft" ? <DraftView key={route.id} id={route.id} context={context} /> :
        route.kind === "run" ? <RunView key={route.id} id={route.id} context={context} /> :
        route.kind === "device" ? <DeviceView context={context} /> :
        (route.kind === "knowledge" || route.kind === "personal") ?
        <LibraryView key={route.kind} context={context} space={route.kind === "personal" ? "personal" : "technical"} /> :
        <div className="workspace-pane"><Notice warning>没有找到这个工作区，请检查链接。</Notice><a href="#/knowledge">返回知识库</a></div>}
    </main></div>
    <nav className="mobile-nav" aria-label="手机导航"><NavLinks section={section} drafts={drafts} icons /></nav>
  </div>;
}
