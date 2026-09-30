# 视觉稿 v2 前端落地 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 `docs/design/visual-v2/` 的视觉稿落到 `guoqing` 分支的 Next.js 前端：统一 token、可读的字号和对比度、固定的状态词汇、四个导航入口和本机草稿角标、阅读页的来源标记与证据栏（手机上是底部抽屉）、版本段落差异、可选深色模式。

**Architecture:** 只改前端，不改后端和数据契约。纯逻辑（状态词汇、四段流程、来源编号、段落差异）放在 `src/lib/` 的小模块里，先写单元测试；展示组件放在 `src/components/`。样式全部改为读取 `src/app/tokens.css` 的变量，用一条设计检查测试守住“不写死色值、不小于 12px、文字对比度 ≥ 4.5:1”。

**Tech Stack:** Next.js 16 · React 19 · TypeScript · Vitest + Testing Library（jsdom、fake-indexeddb）· Tailwind v4 preflight + 手写 CSS

**不在本计划内（需要后端，另行设计）：** 五类分类字段与目录页、多来源主题（知识编译层）、来源登记字段（作者 / 时间码 / 许可）、句内来源锚点、“删掉了有来源支持的说法”这类审阅规则、提案的运行来源展示。

**提交策略：** 用户本轮没有要求提交。每个任务结束只做“检查点”（跑测试），最后统一询问是否提交、提交到哪个分支。

---

## 文件结构

| 文件 | 职责 |
| --- | --- |
| `.gitignore` | 让 `frontend/src/lib/` 不再被 Python 模板的 `lib/` 规则忽略 |
| `frontend/src/app/tokens.css`（新，从设计稿移入） | 唯一的设计 token 来源，浅色 + 深色 |
| `frontend/src/app/globals.css`（重写） | 只引用 token 的全站样式 |
| `frontend/src/app/layout.tsx` | 首屏前应用已保存的主题；浅色 themeColor |
| `frontend/public/manifest.webmanifest` | PWA 颜色改为浅色纸色 |
| `frontend/src/lib/theme.ts`（新） | 主题存储键与首屏脚本（非 client 模块） |
| `frontend/src/lib/status.ts`（新） | 状态词汇与“本机 → 提交 → 整理 → Wiki”四段流程 |
| `frontend/src/lib/evidence.ts`（新） | 来源编号 S1 / J1 |
| `frontend/src/lib/diff.ts`（新） | 段落级版本差异 |
| `frontend/src/components/icons.tsx`（新） | 内联 SVG 图标 |
| `frontend/src/components/status.tsx`（新） | `StatusChip`、`PipelineStepper` |
| `frontend/src/components/theme-toggle.tsx`（新） | 深浅色切换按钮 |
| `frontend/src/components/evidence-panel.tsx`（新） | 证据栏定位卡；手机上变成底部抽屉 |
| `frontend/src/components/version-diff.tsx`（新） | 只显示变化段落的差异视图 |
| `frontend/src/components/content.tsx` | `SourcedContent` 增加可点击的来源标记模式 |
| `frontend/src/components/wiki-views.tsx` | 阅读页右栏改为“来源 / 问 Agent”两个标签；版本审阅显示差异 |
| `frontend/src/components/app-shell.tsx` | 四个导航入口、草稿角标、顶栏状态、主题切换、卡片状态 |
| `frontend/src/components/journal-views.tsx` | 草稿与运行页使用状态词汇和四段流程 |
| `frontend/tests/*.test.ts(x)` | 新增 6 个测试文件，扩充 1 个 |
| `docs/design/visual-v2/*` | 画廊改为引用 `frontend/src/app/tokens.css`，删除副本 |

---

### Task 0: 让 `frontend/src/lib/` 进入版本控制

**Files:**
- Modify: `.gitignore:17`
- Add to index later: `frontend/src/lib/api.ts`, `contracts.ts`, `navigation.ts`, `offline.ts`

- [x] **Step 1: 确认问题存在**

Run: `git check-ignore -v frontend/src/lib/contracts.ts`
Expected: `.gitignore:17:lib/	frontend/src/lib/contracts.ts`

- [x] **Step 2: 在第 17 行 `lib/` 之后加一行**

```gitignore
lib/
!frontend/src/lib/
```

- [x] **Step 3: 验证只放开了这个目录**

Run: `git check-ignore -v frontend/src/lib/contracts.ts; echo "exit=$?"; git check-ignore -v backend/lib/x.py`
Expected: 第一条无输出、`exit=1`；第二条仍输出 `.gitignore:17:lib/	backend/lib/x.py`

Run: `git status --short frontend/src/lib`
Expected: `?? frontend/src/lib/`（四个文件变为可跟踪）

- [x] **Step 4: 撤掉重复的后台任务卡片**（此前为同一问题开的 `task_fbb9d302`）

- [x] **Step 5: 检查点** — `cd frontend && npm test`，Expected: 15 passed。

---

### Task 1: token 进入应用，并加设计检查测试

**Files:**
- Create: `frontend/src/app/tokens.css`（由 `docs/design/visual-v2/tokens.css` 移入并补充）
- Test: `frontend/tests/design-tokens.test.ts`

- [x] **Step 1: 写失败的测试**

```ts
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const app = join(__dirname, "../src/app");
const tokens = readFileSync(join(app, "tokens.css"), "utf8");
const globals = readFileSync(join(app, "globals.css"), "utf8");

function block(selector: string) {
  const open = tokens.indexOf("{", tokens.indexOf(selector));
  return tokens.slice(open + 1, tokens.indexOf("}", open));
}

function colors(css: string): Record<string, string> {
  return Object.fromEntries([...css.matchAll(/(--ot-[\w-]+):\s*(#[0-9a-f]{6})\b/gi)].map((m) => [m[1], m[2]]));
}

function luminance(hex: string) {
  const [r, g, b] = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255)
    .map((c) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4));
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

function contrast(a: string, b: string) {
  const [high, low] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (high + 0.05) / (low + 0.05);
}

const light = colors(block(":root,"));
const dark = { ...light, ...colors(block('[data-theme="dark"]')) };
const texts = ["--ot-ink", "--ot-ink-2", "--ot-ink-3", "--ot-court", "--ot-gold-ink", "--ot-source",
  "--ot-journal", "--ot-model", "--ot-pending", "--ot-danger", "--ot-ok", "--ot-warn"];
const surfaces = ["--ot-paper", "--ot-surface", "--ot-rail"];
const fills = [["--ot-on-court", "--ot-court"], ["--ot-on-ok", "--ot-ok"],
  ["--ot-on-warn", "--ot-warn"], ["--ot-on-danger", "--ot-danger"]];

describe("design tokens", () => {
  it.each([["light", light], ["dark", dark]])("keeps %s text at 4.5:1 or better", (_, theme) => {
    for (const text of texts) {
      for (const surface of surfaces) {
        expect(contrast(theme[text], theme[surface]), `${text} on ${surface}`).toBeGreaterThanOrEqual(4.5);
      }
    }
    for (const [text, fill] of fills) {
      expect(contrast(theme[text], theme[fill]), `${text} on ${fill}`).toBeGreaterThanOrEqual(4.5);
    }
  });

  it("styles components through tokens instead of raw colors", () => {
    expect(globals.match(/#[0-9a-f]{3,8}\b/gi) ?? []).toEqual([]);
  });

  it("never ships text smaller than 12px", () => {
    const sizes = [...globals.matchAll(/font(?:-size)?:[^;]*?(\d+(?:\.\d+)?)px/g)].map((m) => Number(m[1]));
    expect(sizes.filter((size) => size < 12)).toEqual([]);
  });
});
```

- [x] **Step 2: 运行，确认失败**

Run: `cd frontend && npx vitest run tests/design-tokens.test.ts`
Expected: FAIL — `ENOENT ... tokens.css`

- [x] **Step 3: 移入 token 并补充四个新变量**

`git mv` 不适用（设计稿目录未跟踪），直接 `mv docs/design/visual-v2/tokens.css frontend/src/app/tokens.css`，然后在浅色块 `--ot-lime` 一行之后加入：

```css
  --ot-gold-ink: #7d5f16;     /* wordmark text — 5.1:1 */
  --ot-on-ok: #ffffff;
  --ot-on-warn: #ffffff;
  --ot-on-danger: #ffffff;
```

在深色块 `--ot-focus` 一行之后加入：

```css
  --ot-gold-ink: #dcc376;
  --ot-on-ok: #17261e;
  --ot-on-warn: #17261e;
  --ot-on-danger: #17261e;
```

并把文件头注释里的 “Port these names into frontend/src/app/globals.css” 改为 “globals.css imports this file; components use only these names”。

- [x] **Step 4: 再次运行**

Run: `npx vitest run tests/design-tokens.test.ts`
Expected: 对比度两项 PASS；“raw colors”“12px” 两项 FAIL（旧 `globals.css` 有 121 个色值、17 处小字号）——由 Task 2 修复。

- [x] **Step 5: 检查点** — 其余测试不受影响：`npx vitest run --exclude tests/design-tokens.test.ts` → 15 passed。

---

### Task 2: 全站样式改为 token，浅色为默认

**Files:**
- Rewrite: `frontend/src/app/globals.css`
- Create: `frontend/src/lib/theme.ts`
- Modify: `frontend/src/app/layout.tsx`, `frontend/public/manifest.webmanifest`

- [x] **Step 1: 新建 `frontend/src/lib/theme.ts`**

```ts
export const THEME_KEY = "open-tennis-theme";

export const themeScript =
  `try{if(localStorage.getItem("${THEME_KEY}")==="dark")document.documentElement.dataset.theme="dark"}catch(e){}`;
```

（不能放进 `"use client"` 文件：服务端 layout 从 client 模块导入的非组件值会变成引用，拿不到字符串。）

- [x] **Step 2: 修改 `layout.tsx`**

```tsx
import type { Metadata, Viewport } from "next";
import { themeScript } from "../lib/theme";
import "./globals.css";

export const metadata: Metadata = {
  title: "Open Tennis · 球场页边",
  description: "A private tennis knowledge wiki and training journal.",
  manifest: "/manifest.webmanifest",
  appleWebApp: { capable: true, title: "Open Tennis", statusBarStyle: "default" },
  icons: { icon: "/icon.svg", apple: "/apple-touch-icon.png" },
};
export const viewport: Viewport = { width: "device-width", initialScale: 1, themeColor: "#f3f2ea" };

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="zh-CN" suppressHydrationWarning>
    <head><script dangerouslySetInnerHTML={{ __html: themeScript }} /></head>
    <body>{children}</body>
  </html>;
}
```

- [x] **Step 3: `manifest.webmanifest` 两个颜色改为纸色**

```json
  "background_color": "#f3f2ea",
  "theme_color": "#f3f2ea",
```

- [x] **Step 4: 重写 `globals.css`**（完整内容；保留全部现有类名，新增后续任务用到的类名）

```css
@import "tailwindcss";
@import "./tokens.css";

* { box-sizing: border-box; }
html { background: var(--ot-paper); }
body { margin: 0; color: var(--ot-ink); background: var(--ot-paper); font-family: var(--ot-font-sans); font-size: 15px; -webkit-font-smoothing: antialiased; }
button, input, textarea, select { font: inherit; }
button, a, input, textarea, select { -webkit-tap-highlight-color: transparent; }
button, a { touch-action: manipulation; }
button { cursor: pointer; color: inherit; }
button:disabled { cursor: not-allowed; opacity: .55; }
a { color: inherit; text-decoration: none; }
a:focus-visible, button:focus-visible, input:focus-visible, textarea:focus-visible, select:focus-visible, summary:focus-visible { outline: 3px solid var(--ot-focus); outline-offset: 3px; }
input, textarea, select { width: 100%; min-height: 44px; color: var(--ot-ink); background: var(--ot-surface); border: 1px solid var(--ot-line-strong); border-radius: var(--ot-r-control); padding: 11px 13px; }
textarea { min-height: 120px; resize: vertical; line-height: 1.8; }
label { display: block; font-size: 14px; line-height: 1.7; }
h1, h2, h3, h4, p { overflow-wrap: anywhere; }
h1 { font-size: clamp(26px, 3vw, 32px); letter-spacing: -.8px; font-weight: 600; margin: 12px 0; line-height: 1.35; }
h2 { font-size: 21px; font-weight: 600; line-height: 1.5; margin: 12px 0; }
h3 { font-weight: 600; }
p { line-height: 1.8; }
.icon { display: inline-block; flex: 0 0 auto; vertical-align: middle; }
.muted { color: var(--ot-ink-2); }
.small-text { font-size: 13px; }
.eyebrow { color: var(--ot-ink-3); font: 12px/1.6 var(--ot-font-mono); letter-spacing: 1.6px; margin: 0 0 10px; }
.sr-only { position: absolute; width: 1px; height: 1px; padding: 0; overflow: hidden; clip: rect(0, 0, 0, 0); white-space: nowrap; }
.skip-link { position: fixed; top: -100px; left: 12px; z-index: 99; padding: 14px; background: var(--ot-surface); color: var(--ot-ink); }
.skip-link:focus { top: 12px; }

/* actions */
.button { display: inline-flex; align-items: center; justify-content: center; gap: 8px; min-height: 44px; padding: 10px 18px; border: 1px solid transparent; border-radius: var(--ot-r-control); background: var(--ot-court); color: var(--ot-on-court); font-size: 14px; font-weight: 600; text-align: center; }
.button.secondary { color: var(--ot-ink); border-color: var(--ot-line-strong); background: var(--ot-surface); }
.button.danger { color: var(--ot-danger); border-color: color-mix(in srgb, var(--ot-danger) 35%, transparent); background: var(--ot-danger-bg); }
.button.small { min-height: 36px; padding: 6px 12px; font-size: 13px; }
.button-row { display: flex; flex-wrap: wrap; align-items: center; gap: 10px; margin: 20px 0; }
.text-link { display: inline-flex; align-items: center; min-height: 44px; color: var(--ot-court); font-size: 14px; text-decoration: underline; text-underline-offset: 4px; }
.icon-button { display: inline-grid; place-items: center; width: 44px; height: 44px; border: 1px solid var(--ot-line); border-radius: var(--ot-r-control); background: var(--ot-surface); color: var(--ot-ink-2); }
.row { display: flex; align-items: center; justify-content: space-between; gap: 15px; }

/* status */
.tag { display: inline-flex; align-items: center; min-height: 24px; padding: 2px 8px; border: 1px solid var(--ot-line-strong); border-radius: 6px; color: var(--ot-ink-2); font-size: 12px; }
.tag.amber { color: var(--ot-warn); border-color: var(--ot-model-line); background: var(--ot-warn-bg); }
.notice { margin: 14px 0; padding: 12px 16px; border: 1px solid var(--ot-line); border-left: 3px solid var(--ot-court); border-radius: var(--ot-r-control); background: var(--ot-surface); color: var(--ot-ink); font-size: 14px; line-height: 1.75; overflow-wrap: anywhere; }
.notice.warning { color: var(--ot-warn); background: var(--ot-warn-bg); border-color: var(--ot-model-line); border-left-color: var(--ot-warn); }
.status-chip { display: inline-flex; align-items: center; gap: 6px; min-height: 26px; padding: 3px 10px; border: 1px solid var(--ot-line-strong); border-radius: var(--ot-r-pill); background: var(--ot-surface); color: var(--ot-ink-2); font-size: 12px; font-weight: 500; line-height: 1.3; white-space: nowrap; }
.status-chip.ok { color: var(--ot-ok); background: var(--ot-ok-bg); border-color: color-mix(in srgb, var(--ot-ok) 28%, transparent); }
.status-chip.warn { color: var(--ot-warn); background: var(--ot-warn-bg); border-color: var(--ot-model-line); }
.status-chip.danger { color: var(--ot-danger); background: var(--ot-danger-bg); border-color: color-mix(in srgb, var(--ot-danger) 30%, transparent); }
.status-chip.journal { color: var(--ot-journal); background: var(--ot-journal-bg); border-color: color-mix(in srgb, var(--ot-journal) 28%, transparent); }
.status-chip.pending { color: var(--ot-pending); border-style: dashed; border-color: var(--ot-model-line); background: repeating-linear-gradient(135deg, transparent 0 5px, color-mix(in srgb, var(--ot-pending) 10%, transparent) 5px 6px), var(--ot-surface); }
.chip-row { display: flex; flex-wrap: wrap; gap: 6px; margin: 4px 0; }
.stepper { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); margin: 18px 0; padding: 0; list-style: none; }
.stepper li { position: relative; display: flex; flex-direction: column; align-items: center; gap: 4px; padding: 0 4px; text-align: center; }
.stepper li::before { content: ""; position: absolute; top: 11px; left: -50%; right: 50%; height: 2px; background: repeating-linear-gradient(90deg, var(--ot-line-strong) 0 4px, transparent 4px 8px); }
.stepper li:first-child::before { display: none; }
.stepper li.done::before, .stepper li.current::before, .stepper li.failed::before { background: var(--ot-ok); }
.stepper-dot { position: relative; z-index: 1; display: grid; place-items: center; width: 24px; height: 24px; border: 2px solid var(--ot-line-strong); border-radius: 50%; background: var(--ot-surface); }
.stepper li.done .stepper-dot { border-color: var(--ot-ok); background: var(--ot-ok); color: var(--ot-on-ok); }
.stepper li.current .stepper-dot { border-color: var(--ot-warn); background: var(--ot-warn-bg); }
.stepper li.current .stepper-dot::after { content: ""; width: 8px; height: 8px; border-radius: 50%; background: var(--ot-warn); }
.stepper li.failed .stepper-dot { border-color: var(--ot-danger); background: var(--ot-danger-bg); color: var(--ot-danger); }
.stepper-label { font-size: 13px; font-weight: 600; }
.stepper small { font-size: 12px; line-height: 1.4; color: var(--ot-ink-3); }
.stepper li.done small { color: var(--ot-ok); }
.stepper li.current small { color: var(--ot-warn); }
.stepper li.failed small { color: var(--ot-danger); }
.loading-state { display: flex; align-items: center; justify-content: center; gap: 12px; padding: 70px 16px; color: var(--ot-ink-2); }
.loading-dot { width: 8px; height: 8px; border-radius: 50%; background: var(--ot-court); }
.empty-state { max-width: 640px; margin: 44px auto; padding: 24px; text-align: center; }
.empty-state p { color: var(--ot-ink-2); font-size: 15px; }
.empty-state .button { margin-top: 18px; }
.empty-court { position: relative; width: 150px; height: 96px; margin: 20px auto 28px; border: 1px solid var(--ot-line-strong); background: var(--ot-surface); }
.empty-court::before { content: ""; position: absolute; inset: 0 12%; border-left: 1px solid var(--ot-line-strong); border-right: 1px solid var(--ot-line-strong); }
.empty-court::after { content: ""; position: absolute; top: 50%; left: 0; right: 0; border-top: 1px solid var(--ot-line-strong); }

/* shell */
.app-header { position: sticky; top: 0; z-index: 30; display: flex; align-items: center; gap: 22px; height: 60px; padding: 0 24px; border-bottom: 1px solid var(--ot-line); background: var(--ot-surface); }
.brand { display: flex; align-items: center; gap: 9px; flex-shrink: 0; min-height: 44px; color: var(--ot-court); font-size: 19px; font-weight: 600; letter-spacing: -.5px; }
.brand svg { width: 32px; height: 32px; }
.brand em { font-style: normal; color: var(--ot-gold-ink); }
.private-label { color: var(--ot-ink-3); font: 12px var(--ot-font-mono); letter-spacing: 1.2px; }
.app-header nav { display: flex; align-self: stretch; gap: 4px; margin-left: 12px; }
.app-header nav a { display: flex; align-items: center; gap: 6px; padding: 0 12px; border-bottom: 2px solid transparent; color: var(--ot-ink-2); font-size: 15px; }
.app-header nav a[aria-current="page"] { border-bottom-color: var(--ot-court); color: var(--ot-ink); font-weight: 600; }
.header-status { display: flex; align-items: center; gap: 10px; margin-left: auto; }
.device-link { display: flex; align-items: center; min-height: 44px; }
.nav-badge { display: inline-block; min-width: 18px; height: 18px; padding: 0 5px; border-radius: 9px; background: var(--ot-warn); color: var(--ot-on-warn); font-size: 12px; font-weight: 600; line-height: 18px; text-align: center; }
.shell-body { display: flex; min-height: calc(100dvh - 60px); }
.sidebar { position: relative; flex: 0 0 232px; padding: 28px 14px 210px; border-right: 1px solid var(--ot-line); background: var(--ot-rail); }
.sidebar > a { display: flex; justify-content: space-between; align-items: center; gap: 8px; min-height: 44px; margin-bottom: 2px; padding: 10px 12px; border-radius: var(--ot-r-control); color: var(--ot-ink-2); font-size: 14px; }
.sidebar > a.active { color: var(--ot-ink); background: var(--ot-court-soft); font-weight: 600; box-shadow: inset 2px 0 0 var(--ot-court); }
.sidebar .eyebrow { margin: 0 12px 8px; }
.sidebar .eyebrow:not(:first-child) { margin-top: 30px; }
.sidebar-bottom { position: absolute; bottom: 24px; left: 26px; right: 20px; padding-top: 16px; border-top: 1px solid var(--ot-line); color: var(--ot-ink-2); font-size: 12px; }
.sidebar-bottom strong { color: var(--ot-ink); font-weight: 600; }
.sidebar-bottom p { line-height: 1.8; }
main { flex: 1; min-width: 0; }
.connection-banner { padding: 10px 24px; border-bottom: 1px solid var(--ot-model-line); background: var(--ot-warn-bg); color: var(--ot-warn); font-size: 14px; line-height: 1.7; }
.mobile-nav { display: none; }
.workspace-pane { max-width: 1180px; margin: auto; padding: 40px clamp(20px, 4vw, 60px) 80px; }
.narrow { max-width: 820px; }
.section-heading { display: flex; flex-wrap: wrap; align-items: flex-end; justify-content: space-between; gap: 20px; margin-bottom: 28px; }
.search-field { max-width: 520px; margin-bottom: 24px; color: var(--ot-ink-2); }
.search-field span { display: block; margin-bottom: 8px; }
.library-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 16px; }
.topic-card { display: flex; flex-direction: column; gap: 6px; padding: 20px; border: 1px solid var(--ot-line); border-radius: var(--ot-r-card); background: var(--ot-surface); transition: border-color .15s; }
.topic-card:hover { border-color: var(--ot-court); }
.topic-card h2 { margin: 10px 0 0; font-size: 18px; }
.topic-card p { margin: 0; color: var(--ot-ink-2); font-size: 13px; }
.topic-card footer { display: flex; justify-content: space-between; align-items: center; margin-top: 14px; padding-top: 12px; border-top: 1px solid var(--ot-line); color: var(--ot-ink-2); font-size: 13px; }
.topic-card small { color: var(--ot-ink-3); font-size: 12px; }

/* reading and evidence */
.prose { font-size: 17px; line-height: 1.8; overflow-wrap: anywhere; }
.prose h2 { margin-top: 24px; }
.prose a { color: var(--ot-court); text-decoration: underline; text-underline-offset: 4px; }
.prose ul, .prose ol { padding-left: 24px; }
.prose pre { overflow-x: auto; padding: 14px; border-radius: var(--ot-r-control); background: var(--ot-sunken); font-size: 14px; white-space: pre-wrap; }
.prose blockquote { margin-left: 0; padding-left: 18px; border-left: 3px solid var(--ot-line-strong); color: var(--ot-ink-2); }
.sourced-content { display: flex; flex-direction: column; gap: 4px; }
.evidence-section { padding: 16px 0; border-bottom: 1px solid var(--ot-line); }
.evidence-label { display: flex; align-items: center; gap: 8px; margin: 0 0 8px; color: var(--ot-source); font-size: 13px; font-weight: 600; }
.evidence-dot { width: 7px; height: 7px; border-radius: 50%; background: currentColor; }
.evidence-section.personal_observation { margin: 12px 0; padding: 14px 18px; border: 0; border-left: 3px dotted var(--ot-journal); border-radius: 0 var(--ot-r-card) var(--ot-r-card) 0; background: var(--ot-journal-bg); }
.personal_observation .evidence-label { color: var(--ot-journal); }
.evidence-section.model_supplement { margin: 12px 0; padding: 14px 18px; border: 1.5px dashed var(--ot-model-line); border-radius: var(--ot-r-card); background: var(--ot-model-bg); }
.model_supplement .evidence-label { color: var(--ot-model); }
.markers { display: flex; flex-wrap: wrap; gap: 8px; margin: 8px 0 0; }
.marker { position: relative; display: inline-flex; align-items: center; justify-content: center; min-width: 34px; min-height: 28px; padding: 0 8px; border: 1px solid transparent; border-radius: 6px; background: var(--ot-source-bg); color: var(--ot-source); font: 600 12px/1 var(--ot-font-mono); }
.marker::after { content: ""; position: absolute; inset: -8px -4px; }
.marker.journal { background: var(--ot-journal-bg); color: var(--ot-journal); }
.marker[aria-pressed="true"] { background: var(--ot-source); color: var(--ot-surface); box-shadow: 0 0 0 3px color-mix(in srgb, var(--ot-source) 25%, transparent); }
.marker.journal[aria-pressed="true"] { background: var(--ot-journal); box-shadow: 0 0 0 3px color-mix(in srgb, var(--ot-journal) 25%, transparent); }
.citation-link { display: grid; grid-template-columns: auto 1fr auto auto; align-items: center; gap: 10px; min-height: 44px; margin-top: 8px; padding: 10px 12px; border: 1px solid var(--ot-line); border-radius: var(--ot-r-control); background: var(--ot-surface); font-size: 14px; }
.source-kind { color: var(--ot-source); font-size: 12px; font-weight: 600; }
.citation-title { overflow-wrap: anywhere; }
.citation-revision { max-width: 96px; overflow: hidden; color: var(--ot-ink-3); font: 12px var(--ot-font-mono); text-overflow: ellipsis; white-space: nowrap; }
.reader-workspace { display: grid; grid-template-columns: minmax(0, 1fr) minmax(300px, 380px); align-items: start; }
.reading-pane { min-width: 0; padding: 32px clamp(20px, 4vw, 56px) 80px; }
.reading-column { max-width: 36em; font-size: 17px; }
.back-link { display: inline-flex; align-items: center; gap: 4px; min-height: 44px; margin-bottom: 8px; color: var(--ot-ink-2); font-size: 14px; }
.page-meta { display: flex; flex-wrap: wrap; gap: 14px; margin: 12px 0; color: var(--ot-ink-2); font-size: 13px; }
.reader-aside { position: sticky; top: 60px; min-width: 0; max-height: calc(100dvh - 60px); overflow-y: auto; border-left: 1px solid var(--ot-line); background: var(--ot-surface); }
.panel-tabs { position: sticky; top: 0; z-index: 2; display: flex; gap: 20px; padding: 0 20px; border-bottom: 1px solid var(--ot-line); background: var(--ot-surface); }
.panel-tabs [role="tab"] { display: inline-flex; align-items: center; gap: 6px; min-height: 48px; padding: 0; border: 0; border-bottom: 2px solid transparent; background: none; color: var(--ot-ink-2); font-size: 15px; }
.panel-tabs [aria-selected="true"] { border-bottom-color: var(--ot-court); color: var(--ot-ink); font-weight: 600; }
.panel-tabs small { color: var(--ot-ink-3); font: 12px var(--ot-font-mono); }
.evidence-empty { padding: 16px 20px; font-size: 14px; }
.evidence-list { display: flex; flex-direction: column; gap: 10px; padding: 16px; }
.evidence-card { padding: 12px 14px; border: 1px solid var(--ot-line); border-radius: var(--ot-r-card); background: var(--ot-paper); scroll-margin: 64px; }
.evidence-card.journal { border-left: 3px dotted var(--ot-journal); }
.evidence-card.selected { border-color: var(--ot-source); background: var(--ot-surface); box-shadow: 0 0 0 3px color-mix(in srgb, var(--ot-source) 16%, transparent); }
.evidence-card.journal.selected { border-color: var(--ot-journal); box-shadow: 0 0 0 3px color-mix(in srgb, var(--ot-journal) 16%, transparent); }
.evidence-card header { display: flex; align-items: center; gap: 8px; color: var(--ot-ink-2); font-size: 12px; }
.evidence-card h3 { margin: 8px 0 2px; font-size: 15px; line-height: 1.45; }
.excerpt { margin: 10px 0 0; padding: 8px 12px; border-left: 2px solid var(--ot-source); border-radius: 0 var(--ot-r-control) var(--ot-r-control) 0; background: var(--ot-source-bg); font-size: 14px; line-height: 1.75; }
.evidence-card.journal .excerpt { border-left-color: var(--ot-journal); background: var(--ot-journal-bg); }
.journal-note { margin: 8px 0 0; color: var(--ot-journal); }
.card-actions { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; margin-top: 10px; }
.sheet-bar, .sheet-pager, .sheet-scrim { display: none; }
.agent-panel { min-width: 0; padding: 22px 20px 40px; }
.agent-panel h2 { margin-top: 0; font-size: 18px; line-height: 1.6; }
.agent-star { color: var(--ot-gold); font-size: 24px; }
.privacy-note { color: var(--ot-ink-2); font-size: 13px; line-height: 1.7; }
.agent-panel form { margin-top: 18px; }
.agent-panel textarea { margin-top: 8px; }
.agent-panel .button { width: 100%; }
.agent-panel .prose { font-size: 15px; }
.agent-panel .citation-link { grid-template-columns: 1fr auto; font-size: 13px; }
.check-label { display: flex; align-items: flex-start; gap: 12px; min-height: 44px; margin: 14px 0; font-size: 14px; }
.check-label input { flex: 0 0 22px; width: 22px; height: 22px; min-height: 22px; margin: 2px 0 0; accent-color: var(--ot-court); }

/* versions */
.version-panel { margin-top: 36px; padding-top: 24px; border-top: 1px solid var(--ot-line); }
.version-list { display: flex; flex-wrap: wrap; gap: 8px; margin: 18px 0; }
.version-chip { min-height: 56px; padding: 9px 13px; border: 1px solid var(--ot-line); border-radius: var(--ot-r-control); background: var(--ot-surface); color: var(--ot-ink-2); font-size: 13px; text-align: left; }
.version-chip small { display: block; margin-top: 4px; color: var(--ot-ink-3); font-size: 12px; }
.version-chip.chosen { border-color: var(--ot-court); background: var(--ot-court-soft); color: var(--ot-ink); font-weight: 600; }
.change-summary { color: var(--ot-ink-2); font-size: 14px; }
.version-diff { margin: 16px 0; }
.diff-summary { display: flex; flex-wrap: wrap; gap: 6px; margin: 0 0 10px; }
.diff-block { margin: 8px 0; padding: 10px 16px; border: 1px solid var(--ot-line); border-radius: var(--ot-r-card); }
.diff-block.added { border-color: color-mix(in srgb, var(--ot-ok) 35%, transparent); background: var(--ot-ok-bg); }
.diff-block.removed { border-color: color-mix(in srgb, var(--ot-danger) 35%, transparent); background: var(--ot-danger-bg); }
.diff-label { margin: 0 0 4px; font-size: 12px; font-weight: 600; }
.diff-block.added .diff-label { color: var(--ot-ok); }
.diff-block.removed .diff-label { color: var(--ot-danger); }
details { margin: 16px 0; padding: 6px 16px; border: 1px solid var(--ot-line); border-radius: var(--ot-r-control); background: var(--ot-surface); }
summary { display: list-item; align-content: center; min-height: 44px; color: var(--ot-ink); font-size: 14px; cursor: pointer; }
.proposal-form { margin-top: 26px; }
.proposal-form .button { margin-top: 12px; }
.revision-text { color: var(--ot-ink-3); font: 12px/1.8 var(--ot-font-mono); overflow-wrap: anywhere; }
.source-excerpt { margin: 24px 0; padding: 4px 0 4px 20px; border-left: 3px solid var(--ot-source); border-radius: 0 var(--ot-r-control) var(--ot-r-control) 0; background: var(--ot-source-bg); }

/* plans */
.form-stack > label { margin: 18px 0; }
.form-stack label input:not([type="checkbox"]), .form-stack label textarea, .form-stack label select { margin-top: 8px; }
.form-stack fieldset { margin: 20px 0; padding: 14px; border: 1px solid var(--ot-line); border-radius: var(--ot-r-control); }
.form-stack fieldset label { margin-top: 12px; }
.form-stack legend { padding: 0 8px; color: var(--ot-ink-2); font-size: 13px; }
.plan-preview { margin-top: 32px; padding-top: 24px; border-top: 1px solid var(--ot-line); }
.drill-list { padding: 0; list-style: none; }
.drill-list li { display: flex; align-items: flex-start; gap: 18px; padding: 20px 0; border-bottom: 1px solid var(--ot-line); }
.drill-number { min-width: 38px; color: var(--ot-ink-3); font: italic 30px/1.2 var(--ot-font-num); }
.drill-list h3 { margin: 0 0 8px; font-size: 16px; }
.drill-list p { margin: 0; color: var(--ot-ink-2); font-size: 14px; }
.practice-card { padding: 24px 0; border-top: 1px solid var(--ot-line); }
.practice-list { margin: 22px 0; }
.practice-step { display: flex; align-items: flex-start; gap: 14px; min-height: 72px; margin-bottom: 12px; padding: 18px 16px; border: 1px solid var(--ot-line); border-radius: var(--ot-r-card); background: var(--ot-surface); }
.practice-step:has(input:checked) { border-color: color-mix(in srgb, var(--ot-ok) 30%, transparent); background: var(--ot-ok-bg); }
.practice-step input { flex: 0 0 26px; width: 26px; height: 26px; min-height: 26px; margin-top: 4px; accent-color: var(--ot-court); }
.practice-step strong { font-size: 16px; font-weight: 600; }
.drill-description { display: block; margin-top: 6px; color: var(--ot-ink-2); font-size: 14px; line-height: 1.8; }
.owner-note { margin: 24px 0; padding: 20px; border-left: 3px dotted var(--ot-journal); border-radius: 0 var(--ot-r-card) var(--ot-r-card) 0; background: var(--ot-journal-bg); }
.edit-panel { padding: 20px; border: 1px solid var(--ot-line); border-radius: var(--ot-r-card); background: var(--ot-surface); }

/* journal and device */
.record-list { display: flex; flex-direction: column; gap: 14px; margin: 24px 0; }
.record-card { display: block; padding: 20px; border: 1px solid var(--ot-line); border-radius: var(--ot-r-card); background: var(--ot-surface); }
.record-card h2 { font-size: 17px; line-height: 1.7; }
.record-card p { font-size: 14px; }
.record-card time { color: var(--ot-ink-3); font-size: 12px; }
.owner-quote { padding-left: 16px; border-left: 3px dotted var(--ot-journal); font-size: 17px; line-height: 1.85; white-space: pre-wrap; }
.submit-panel { margin-top: 30px; padding-top: 24px; border-top: 1px solid var(--ot-line); }
.device-summary { display: flex; justify-content: space-between; gap: 20px; margin-top: 24px; padding: 22px; border: 1px solid var(--ot-line); border-radius: var(--ot-r-card); background: var(--ot-surface); }
.device-summary > span { color: var(--ot-ink-2); font-size: 13px; }
.device-summary strong { display: block; margin-bottom: 6px; color: var(--ot-ink); font: italic 36px/1.3 var(--ot-font-num); }
.saved-list .row { flex-wrap: wrap; align-items: flex-start; padding: 14px 0; border-bottom: 1px solid var(--ot-line); }

@media (max-width: 1100px) {
  .reader-workspace { grid-template-columns: minmax(0, 1fr); }
  .reader-aside { position: static; max-height: none; overflow: visible; border-top: 1px solid var(--ot-line); border-left: 0; }
}
@media (max-width: 950px) {
  .private-label { display: none; }
  .sidebar { flex-basis: 196px; }
  .app-header { gap: 14px; padding: 0 16px; }
}
@media (max-width: 700px) {
  .app-header { padding: env(safe-area-inset-top) 12px 0 16px; }
  .brand { font-size: 18px; }
  .brand svg { width: 30px; height: 30px; }
  .app-header nav, .sidebar, .review-chip { display: none; }
  .workspace-pane { padding: 24px 16px 110px; }
  h1 { font-size: 27px; line-height: 1.45; }
  .mobile-nav { position: fixed; z-index: 20; left: 0; right: 0; bottom: 0; display: flex; justify-content: space-around; padding: 6px 6px calc(6px + env(safe-area-inset-bottom)); border-top: 1px solid var(--ot-line); background: var(--ot-surface); }
  .mobile-nav a { position: relative; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 3px; min-width: 76px; min-height: 52px; color: var(--ot-ink-3); font-size: 12px; }
  .mobile-nav a[aria-current="page"] { color: var(--ot-court); font-weight: 600; }
  .nav-icon { position: relative; display: grid; place-items: center; }
  .nav-icon .nav-badge { position: absolute; top: -6px; left: 14px; }
  .button.small { min-height: 44px; }
  .reading-pane { padding: 18px 16px 28px; }
  .reader-aside { padding-bottom: 96px; }
  .evidence-list.open { position: fixed; z-index: 45; left: 0; right: 0; bottom: 0; max-height: 75dvh; overflow-y: auto; padding: 6px 16px calc(12px + env(safe-area-inset-bottom)); border-radius: var(--ot-r-sheet) var(--ot-r-sheet) 0 0; background: var(--ot-surface); box-shadow: var(--ot-shadow-sheet); }
  .evidence-list.open .evidence-card { display: none; }
  .evidence-list.open .evidence-card.selected { display: block; padding: 0 2px; border: 0; background: none; box-shadow: none; }
  .evidence-list.open .sheet-bar { position: relative; display: flex; justify-content: flex-end; min-height: 44px; }
  .sheet-bar::before { content: ""; position: absolute; top: 8px; left: 50%; width: 40px; height: 5px; border-radius: 3px; background: var(--ot-line-strong); transform: translateX(-50%); }
  .evidence-list.open .sheet-pager { display: flex; justify-content: space-between; align-items: center; margin-top: 6px; border-top: 1px solid var(--ot-line); }
  .sheet-pager button { min-height: 44px; padding: 0 12px; border: 0; background: none; color: var(--ot-court); font-size: 15px; font-weight: 600; }
  .sheet-pager span { color: var(--ot-ink-3); font: 13px var(--ot-font-mono); }
  .sheet-scrim { position: fixed; z-index: 44; inset: 0; display: block; background: var(--ot-scrim); }
  .agent-panel { padding: 20px 16px 100px; }
  .library-grid { grid-template-columns: 1fr; }
  .empty-state { margin: 20px 0; padding: 18px 0; }
  .connection-banner { padding: 10px 16px; }
  .citation-link { grid-template-columns: 1fr auto; }
  .device-summary { flex-wrap: wrap; }
  .stepper-label { font-size: 12px; }
}
@media (prefers-reduced-motion: reduce) { * { scroll-behavior: auto !important; transition: none !important; } }
```

- [x] **Step 5: 运行设计检查与全部测试**

Run: `npx vitest run`
Expected: design-tokens 4 项全部 PASS；共 19 passed。

- [x] **Step 6: 检查点** — `npm run typecheck` 通过。

---

### Task 3: 内联图标

**Files:**
- Create: `frontend/src/components/icons.tsx`

- [x] **Step 1: 写组件**（由 Task 4、5、6、8 的测试间接覆盖）

```tsx
const paths = {
  book: "M3 4.5h6c2 0 3 1 3 2 0-1 1-2 3-2h6v14h-6c-2 0-3 1-3 2 0-1-1-2-3-2H3ZM12 6.5v14",
  court: "M4 2.5h16v19H4ZM7 2.5v19M17 2.5v19M4 12h16M7 7h10M7 17h10M12 7v10",
  pen: "M4 20h4L19 9l-4-4L4 16ZM13.5 6.5l4 4M14 20h6",
  note: "M6 3h12a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2ZM8 8h8M8 12h8M8 16h5",
  sun: "M16 12a4 4 0 1 1-8 0 4 4 0 0 1 8 0ZM12 2.5v2M12 19.5v2M4.6 4.6 6 6M18 18l1.4 1.4M2.5 12h2M19.5 12h2M4.6 19.4 6 18M18 6l1.4-1.4",
  moon: "M20 14.5A8 8 0 1 1 9.5 4a6.5 6.5 0 0 0 10.5 10.5Z",
  check: "m5 12.5 4.5 4.5L19 7.5",
  lock: "M7 11h10a2 2 0 0 1 2 2v6a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2v-6a2 2 0 0 1 2-2ZM8 11V8a4 4 0 0 1 8 0v3",
  clock: "M20.5 12a8.5 8.5 0 1 1-17 0 8.5 8.5 0 0 1 17 0ZM12 7.5V12l3 2",
  alert: "M12 3.5 2.5 20h19ZM12 10v4.5M12 17.2v.3",
  offline: "M2.5 8.5a14 14 0 0 1 6-3M12 5a14 14 0 0 1 9.5 3.5M5.5 12a9.5 9.5 0 0 1 3.8-2.3M15.5 10.2A9.5 9.5 0 0 1 18.5 12M9 15.5a4.8 4.8 0 0 1 6 0M12 19h.01M3 3l18 18",
  online: "M2.5 8.5a14 14 0 0 1 19 0M5.5 12a9.5 9.5 0 0 1 13 0M9 15.5a4.8 4.8 0 0 1 6 0M12 19h.01",
  device: "M9 2.5h6a2 2 0 0 1 2 2v15a2 2 0 0 1-2 2H9a2 2 0 0 1-2-2v-15a2 2 0 0 1 2-2ZM11 18h2",
  close: "M6.5 6.5l11 11M17.5 6.5l-11 11",
  chevron: "m9 5 7 7-7 7",
  external: "M7 17 17 7M8.5 7H17v8.5",
} as const;

export type IconName = keyof typeof paths;

export function Icon({ name, size = 18 }: { name: IconName; size?: number }) {
  return <svg className="icon" width={size} height={size} viewBox="0 0 24 24" aria-hidden="true"
    focusable="false" fill="none" stroke="currentColor" strokeWidth={1.7} strokeLinecap="round" strokeLinejoin="round">
    <path d={paths[name]} />
  </svg>;
}
```

- [x] **Step 2: 检查点** — `npm run typecheck` 通过。

---

### Task 4: 状态词汇与四段流程

**Files:**
- Create: `frontend/src/lib/status.ts`, `frontend/src/components/status.tsx`
- Test: `frontend/tests/status.test.tsx`

- [x] **Step 1: 写失败的测试**

```tsx
import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { PipelineStepper, StatusChip } from "../src/components/status";
import { connectionStatus, draftStatus, pageStatuses, pipeline, runStatus } from "../src/lib/status";

const notes = (input: Parameters<typeof pipeline>[0]) =>
  pipeline(input).map((stage) => `${stage.state}:${stage.note}`);

describe("status vocabulary", () => {
  it("names connection, draft and run states in words", () => {
    expect(connectionStatus(false)).toMatchObject({ label: "离线 · 只读已保存", tone: "warn" });
    expect(draftStatus("editable", true).label).toBe("有未保存输入");
    expect(draftStatus("locked").label).toBe("已锁定 · 等待回执");
    expect(runStatus("failed")).toMatchObject({ label: "整理失败 · 原话仍在", tone: "danger" });
  });

  it("does not present unpublished technical pages as published", () => {
    expect(pageStatuses({ space: "technical", version: 0, has_draft: true, index_status: "pending" })
      .map((status) => status.label)).toEqual(["草稿 · 未发布"]);
    expect(pageStatuses({ space: "technical", version: 3, has_draft: true, index_status: "failed" })
      .map((status) => status.label)).toEqual(["已发布 v3", "有待审阅改动", "检索索引失败"]);
    expect(pageStatuses({ space: "personal", version: 4, has_draft: false, index_status: "ready" })[0].label)
      .toBe("已更新 v4");
  });

  it("keeps saving, submitting, organising and wiki updates as separate stages", () => {
    expect(notes({ dirty: false, locked: false, receipt: false, online: false, run: null }))
      .toEqual(["done:已存本机", "waiting:需联网，由你确认", "waiting:提交后开始", "waiting:尚未更新"]);
    expect(notes({ dirty: true, locked: true, receipt: false, online: true, run: null }).slice(0, 2))
      .toEqual(["current:有未保存输入", "current:已锁定 · 等待回执"]);
    expect(notes({ dirty: false, locked: false, receipt: true, online: true, run: "failed" }))
      .toEqual(["done:已存本机", "done:已提交 · 有回执", "failed:失败 · 原话仍在", "waiting:未更新"]);
  });

  it("claims a wiki update only when the run produced a version", () => {
    expect(notes({ dirty: false, locked: false, receipt: true, online: true, run: "succeeded", updated: true })[3])
      .toBe("done:派生页已更新");
    expect(notes({ dirty: false, locked: false, receipt: true, online: true, run: "succeeded", updated: false })[3])
      .toBe("done:未生成新版本");
  });

  it("renders chips and stages as readable text", () => {
    render(<>
      <StatusChip status={runStatus("needs_input")} />
      <PipelineStepper stages={pipeline({ dirty: false, locked: false, receipt: true, online: true, run: "running" })} />
    </>);
    expect(screen.getByText("需要你确认")).toBeVisible();
    const steps = screen.getByRole("list", { name: "记录进度" });
    expect(within(steps).getAllByRole("listitem")).toHaveLength(4);
    expect(within(steps).getByText("整理中")).toBeVisible();
  });
});
```

- [x] **Step 2: 运行，确认失败**

Run: `npx vitest run tests/status.test.tsx`
Expected: FAIL — `Failed to resolve import "../src/components/status"`

- [x] **Step 3: 实现 `frontend/src/lib/status.ts`**

```ts
import type { Run, Space } from "./contracts";

export type Tone = "neutral" | "ok" | "warn" | "danger" | "pending" | "journal";
export type StatusIcon = "check" | "lock" | "clock" | "alert" | "offline" | "online" | "device";
export type Status = { label: string; tone: Tone; icon?: StatusIcon };

export function connectionStatus(online: boolean): Status {
  return online ? { label: "在线", tone: "ok", icon: "online" }
    : { label: "离线 · 只读已保存", tone: "warn", icon: "offline" };
}

export function pageStatuses(page: {
  space: Space; version: number; has_draft: boolean; index_status: "pending" | "ready" | "failed";
}): Status[] {
  const statuses: Status[] = [page.version > 0
    ? { label: `${page.space === "technical" ? "已发布" : "已更新"} v${page.version}`, tone: "ok", icon: "check" }
    : page.space === "technical" ? { label: "草稿 · 未发布", tone: "pending" }
    : { label: "尚未整理", tone: "neutral" }];
  if (page.has_draft && page.version > 0) statuses.push({ label: "有待审阅改动", tone: "warn", icon: "clock" });
  if (page.index_status === "failed") statuses.push({ label: "检索索引失败", tone: "danger", icon: "alert" });
  return statuses;
}

export function draftStatus(state: "editable" | "locked", dirty = false): Status {
  if (dirty) return { label: "有未保存输入", tone: "warn" };
  return state === "locked" ? { label: "已锁定 · 等待回执", tone: "warn", icon: "lock" }
    : { label: "已存本机 · 未提交", tone: "neutral", icon: "device" };
}

const runStatuses: Record<Run["status"], Status> = {
  queued: { label: "整理排队中", tone: "neutral", icon: "clock" },
  running: { label: "Agent 正在整理", tone: "neutral", icon: "clock" },
  succeeded: { label: "整理完成", tone: "ok", icon: "check" },
  failed: { label: "整理失败 · 原话仍在", tone: "danger", icon: "alert" },
  needs_input: { label: "需要你确认", tone: "warn", icon: "alert" },
};

export function runStatus(status: Run["status"]): Status {
  return runStatuses[status];
}

export type StageState = "done" | "current" | "waiting" | "failed";
export type Stage = { key: "local" | "submitted" | "organize" | "wiki"; label: string; state: StageState; note: string };
export type PipelineInput = {
  dirty: boolean; locked: boolean; receipt: boolean; online: boolean;
  run: Run["status"] | "unknown" | null; updated?: boolean;
};

function stage(key: Stage["key"], label: string, state: StageState, note: string): Stage {
  return { key, label, state, note };
}

function organizeStage(receipt: boolean, run: PipelineInput["run"]): Stage {
  const label = "Agent 整理";
  if (!receipt) return stage("organize", label, "waiting", "提交后开始");
  if (run === null) return stage("organize", label, "waiting", "未登记整理任务");
  if (run === "unknown") return stage("organize", label, "current", "查看整理状态");
  if (run === "succeeded") return stage("organize", label, "done", "整理完成");
  if (run === "failed") return stage("organize", label, "failed", "失败 · 原话仍在");
  if (run === "needs_input") return stage("organize", label, "current", "需要你确认");
  return stage("organize", label, "current", run === "queued" ? "排队中" : "整理中");
}

export function pipeline({ dirty, locked, receipt, online, run, updated = false }: PipelineInput): Stage[] {
  const local = dirty ? stage("local", "本机草稿", "current", "有未保存输入")
    : stage("local", "本机草稿", "done", "已存本机");
  const submitted = receipt ? stage("submitted", "提交", "done", "已提交 · 有回执")
    : locked ? stage("submitted", "提交", "current", "已锁定 · 等待回执")
    : stage("submitted", "提交", "waiting", online ? "等你确认提交" : "需联网，由你确认");
  const wiki = receipt && run === "succeeded"
    ? stage("wiki", "Wiki 更新", "done", updated ? "派生页已更新" : "未生成新版本")
    : stage("wiki", "Wiki 更新", "waiting", run === "failed" ? "未更新" : "尚未更新");
  return [local, submitted, organizeStage(receipt, run), wiki];
}
```

- [x] **Step 4: 实现 `frontend/src/components/status.tsx`**

```tsx
import type { Stage, Status } from "../lib/status";
import { Icon } from "./icons";

export function StatusChip({ status }: { status: Status }) {
  return <span className={`status-chip ${status.tone}`}>
    {status.icon && <Icon name={status.icon} size={14} />}{status.label}
  </span>;
}

export function PipelineStepper({ stages }: { stages: Stage[] }) {
  return <ol className="stepper" aria-label="记录进度">{stages.map((stage) => (
    <li key={stage.key} className={stage.state}>
      <span className="stepper-dot" aria-hidden="true">
        {stage.state === "done" && <Icon name="check" size={13} />}
        {stage.state === "failed" && <Icon name="alert" size={13} />}
      </span>
      <span className="stepper-label">{stage.label}</span>
      <small>{stage.note}</small>
    </li>
  ))}</ol>;
}
```

- [x] **Step 5: 运行** — `npx vitest run tests/status.test.tsx` → 5 passed。

- [x] **Step 6: 检查点** — `npx vitest run && npm run typecheck`。

---

### Task 5: 四个导航入口、草稿角标、顶栏状态

**Files:**
- Modify: `frontend/src/components/app-shell.tsx`
- Test: `frontend/tests/nav.test.tsx`

- [x] **Step 1: 写失败的测试**

```tsx
import { render, screen } from "@testing-library/react";
import { expect, it } from "vitest";
import { AppShell } from "../src/components/app-shell";
import { ApiClient } from "../src/lib/api";
import { newDraft, OfflineClient } from "../src/lib/offline";

it("keeps unsent local drafts and pending reviews visible in the navigation", async () => {
  const api = new ApiClient(async (url) => String(url).includes("/status")
    ? Response.json({ ready: true, agent_enabled: true, model_configured: true, sources_count: 3, pending_reviews: 2 })
    : Response.json([]));
  const offline = new OfflineClient(api, `nav-${crypto.randomUUID()}`);
  await offline.saveDraft(newDraft({ content: "低球还是会飘" }));
  await offline.saveDraft(newDraft({ content: "慢下来往前送" }));

  render(<AppShell api={api} offline={offline} />);

  expect(await screen.findAllByRole("link", { name: /记录.*本机 2 条草稿未提交/ })).toHaveLength(2);
  expect(screen.getAllByRole("link", { name: "我的 Wiki" })).toHaveLength(2);
  expect(await screen.findByText("待审阅 2")).toBeVisible();
});
```

- [x] **Step 2: 运行，确认失败**

Run: `npx vitest run tests/nav.test.tsx`
Expected: FAIL — 找不到名为“记录…”的链接（现在只有“技术 Wiki / 训练卡 / 我的 Wiki”）

- [x] **Step 3: 修改 `app-shell.tsx`**

3a. 导入：

```tsx
import { connectionStatus, pageStatuses } from "../lib/status";
import { Icon, type IconName } from "./icons";
import { StatusChip } from "./status";
import { ThemeToggle } from "./theme-toggle";
```

（`ThemeToggle` 由 Task 6 新建；Task 5 与 Task 6 连续执行，Task 6 完成前不单独跑 typecheck。）

3b. 在 `ViewContext` 定义之后加入：

```tsx
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

function DraftCount({ count }: { count: number }) {
  if (!count) return null;
  return <><span className="nav-badge" aria-hidden="true">{count}</span>
    <span className="sr-only">，本机 {count} 条草稿未提交</span></>;
}

function NavLinks({ section, drafts, icons }: { section: Section | null; drafts: number; icons: boolean }) {
  return <>{navItems.map((item) => (
    <a key={item.key} href={item.href} aria-current={section === item.key ? "page" : undefined}>
      {icons ? <span className="nav-icon"><Icon name={item.icon} size={22} />
        {item.key === "records" && <DraftCount count={drafts} />}</span> : null}
      {item.label}
      {!icons && item.key === "records" && <DraftCount count={drafts} />}
    </a>
  ))}</>;
}
```

3c. `LibraryView` 的卡片改为状态词汇（删掉 `court-lines` 装饰）：

```tsx
      <div className="library-grid">{state.data.pages.map((page) => <a className="topic-card" href={linkTo("wiki", page.id)} key={page.id}>
        <div className="chip-row">{pageStatuses(page).map((status) => <StatusChip key={status.label} status={status} />)}</div>
        <h2>{page.title}</h2><p>{page.topic}</p>
        <footer><span>{space === "personal" ? `${page.record_count} 条原始记录` : "阅读与来源"}</span><Icon name="chevron" size={16} /></footer>
        <small>{formatDate(page.updated_at)}</small>
      </a>)}</div>
```

3d. `AppShell` 签名、离线客户端注入与草稿计数：

```tsx
export function AppShell({ api = defaultApi, offline: injected }: { api?: ApiClient; offline?: OfflineClient }) {
  const offline = useMemo(() => injected ?? new OfflineClient(api), [api, injected]);
```

在 `const status = useLoad(statusLoader);` 之前加入：

```tsx
  const [drafts, setDrafts] = useState(0);
  useEffect(() => {
    let cancelled = false;
    offline.listDrafts().then(
      (items) => { if (!cancelled) setDrafts(items.length); },
      () => { if (!cancelled) setDrafts(0); },
    );
    return () => { cancelled = true; };
  }, [offline, route]);
```

3e. 删除 `isPersonal` 与旧的 `section` 计算，改为 `const section = sectionOf(route, wikiSpace);`，并把返回的外壳替换为：

```tsx
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
      <a className={["drafts", "draft"].includes(route.kind) ? "active" : ""} href="#/drafts">本机草稿<DraftCount count={drafts} /></a>
      <a className={route.kind === "device" ? "active" : ""} href="#/device">离线保存与导出</a>
      <div className="sidebar-bottom"><strong>资料、记录、推测，分开放。</strong><p>原文不被 Agent 覆盖。每次理解，都能找到来处。</p>
        {status.data && <span>{status.data.sources_count} 份技术资料 · {status.data.pending_reviews} 项待审阅</span>}</div>
    </aside>
```

`<main>…</main>` 保持不变；结尾的手机导航替换为：

```tsx
    <nav className="mobile-nav" aria-label="手机导航"><NavLinks section={section} drafts={drafts} icons /></nav>
  </div>;
```

同时删除 `Brand` 之外不再使用的 `.connection-dot` 相关 JSX。

- [x] **Step 4: 跑到 Task 6 完成后再验证**（见 Task 6 Step 5）。

---

### Task 6: 深色阅读模式开关

**Files:**
- Create: `frontend/src/components/theme-toggle.tsx`
- Test: `frontend/tests/theme.test.tsx`

- [x] **Step 1: 写失败的测试**

```tsx
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it } from "vitest";
import { ThemeToggle } from "../src/components/theme-toggle";
import { THEME_KEY, themeScript } from "../src/lib/theme";

afterEach(() => {
  localStorage.clear();
  delete document.documentElement.dataset.theme;
});

it("switches to the dark reading mode and remembers the choice", async () => {
  render(<ThemeToggle />);
  await userEvent.click(screen.getByRole("button", { name: "切换到深色阅读" }));
  expect(document.documentElement.dataset.theme).toBe("dark");
  expect(localStorage.getItem(THEME_KEY)).toBe("dark");
  await userEvent.click(screen.getByRole("button", { name: "切换到浅色" }));
  expect(document.documentElement.dataset.theme).toBe("light");
});

it("restores a saved dark preference before the page paints", () => {
  localStorage.setItem(THEME_KEY, "dark");
  new Function(themeScript)();
  expect(document.documentElement.dataset.theme).toBe("dark");
});
```

- [x] **Step 2: 运行，确认失败** — `npx vitest run tests/theme.test.tsx` → FAIL（模块不存在）。

- [x] **Step 3: 实现 `frontend/src/components/theme-toggle.tsx`**

```tsx
"use client";

import { useEffect, useState } from "react";
import { THEME_KEY } from "../lib/theme";
import { Icon } from "./icons";

type Theme = "light" | "dark";

function storedTheme(): Theme {
  try {
    return localStorage.getItem(THEME_KEY) === "dark" ? "dark" : "light";
  } catch {
    return "light";
  }
}

export function ThemeToggle() {
  const [theme, setTheme] = useState<Theme>("light");
  useEffect(() => setTheme(storedTheme()), []);
  const next: Theme = theme === "dark" ? "light" : "dark";
  return <button type="button" className="icon-button" aria-label={next === "dark" ? "切换到深色阅读" : "切换到浅色"}
    onClick={() => {
      document.documentElement.dataset.theme = next;
      try {
        localStorage.setItem(THEME_KEY, next);
      } catch {
        console.warn("theme_preference_not_saved");
      }
      setTheme(next);
    }}>
    <Icon name={next === "dark" ? "moon" : "sun"} />
  </button>;
}
```

- [x] **Step 4: 运行** — `npx vitest run tests/theme.test.tsx` → 2 passed。

- [x] **Step 5: 验证 Task 5** — `npx vitest run && npm run typecheck`
Expected: nav.test 通过；app.test 三项仍通过；typecheck 通过。

---

### Task 7: 阅读页的状态标签

**Files:**
- Modify: `frontend/src/components/wiki-views.tsx`（`WikiView` 头部）

- [x] **Step 1: 把 `WikiView` 里的眉题与版本号替换为状态标签**

原来：

```tsx
      <p className="eyebrow">WIKI / VERSION {page.version}</p>
```

改为：

```tsx
      <p className="eyebrow">{page.space === "personal" ? "PERSONAL WIKI" : "TECHNICAL WIKI"}</p>
      <div className="chip-row">{pageStatuses(page).map((status) => <StatusChip key={status.label} status={status} />)}</div>
```

并导入 `import { pageStatuses } from "../lib/status";`、`import { StatusChip } from "./status";`。

- [x] **Step 2: 检查点** — `npx vitest run tests/app.test.tsx` → 3 passed（草稿提示与“确认发布此版本”按钮仍在）。

---

### Task 8: 来源标记、证据栏与手机底部抽屉

**Files:**
- Create: `frontend/src/lib/evidence.ts`, `frontend/src/components/evidence-panel.tsx`
- Modify: `frontend/src/components/content.tsx`, `frontend/src/components/wiki-views.tsx`
- Test: `frontend/tests/evidence.test.tsx`

- [x] **Step 1: 写失败的测试**

```tsx
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, it } from "vitest";
import { WikiView } from "../src/components/wiki-views";
import { ApiClient } from "../src/lib/api";
import type { Evidence } from "../src/lib/contracts";
import { citationLabels } from "../src/lib/evidence";
import { OfflineClient } from "../src/lib/offline";

const source = (id: string, kind: Evidence["kind"] = "technical"): Evidence => ({
  id, kind, title: `标题 ${id}`, excerpt: `摘录 ${id}`, source_url: null, revision: "r1",
});

it("numbers sources by kind in reading order", () => {
  const labels = citationLabels([
    { kind: "source_supported", text: "a", citation_ids: ["t2", "missing"] },
    { kind: "personal_observation", text: "b", citation_ids: ["j1", "t2"] },
    { kind: "source_supported", text: "c", citation_ids: ["t1"] },
  ], [source("t1"), source("t2"), source("j1", "journal"), source("t3")]);
  expect(Object.fromEntries(labels)).toEqual({ t2: "S1", j1: "J1", t1: "S2", t3: "S3" });
});

it("opens the cited source beside the text when its marker is chosen", async () => {
  const page = {
    id: "slice", space: "technical", title: "反手切削", topic: "切削", version: 3,
    updated_at: "2026-09-21T08:00:00Z", has_draft: false, index_status: "ready", record_count: 0,
    version_id: "v3", status: "published", content: "", change_summary: "",
    sections: [
      { kind: "source_supported", text: "拍面略微打开。", citation_ids: ["s-a"] },
      { kind: "personal_observation", text: "低球总是飘。", citation_ids: ["j-a"] },
    ],
    citations: [
      { ...source("s-a"), title: "测试切削教程", excerpt: "拍头先高一点" },
      { ...source("j-a", "journal"), title: "测试训练记录" },
    ],
  };
  const api = new ApiClient(async () => Response.json(page));
  const offline = new OfflineClient(api, `reader-${crypto.randomUUID()}`);
  render(<WikiView id="slice" context={{ api, offline, online: true }} />);

  await userEvent.click(await screen.findByRole("button", { name: "来源 S1：测试切削教程" }));

  const card = screen.getByRole("article", { name: "S1 测试切削教程" });
  expect(card).toHaveAttribute("aria-current", "true");
  expect(within(card).getByText("拍头先高一点")).toBeVisible();
  expect(within(card).getByRole("link", { name: "打开原文" })).toHaveAttribute("href", "#/evidence/s-a");
  expect(within(card).getByText("原始链接缺失")).toBeVisible();
  expect(screen.getByRole("button", { name: "来源 S1：测试切削教程" })).toHaveAttribute("aria-pressed", "true");
  expect(screen.getByRole("article", { name: "J1 测试训练记录" })).not.toHaveAttribute("aria-current");
});
```

- [x] **Step 2: 运行，确认失败** — `npx vitest run tests/evidence.test.tsx` → FAIL（`../src/lib/evidence` 不存在）。

- [x] **Step 3: 实现 `frontend/src/lib/evidence.ts`**

```ts
import type { Evidence, Section } from "./contracts";

export function citationLabels(sections: Section[], citations: Evidence[]): Map<string, string> {
  const byId = new Map(citations.map((item) => [item.id, item]));
  const labels = new Map<string, string>();
  const counts = { technical: 0, journal: 0 };
  const label = (evidence: Evidence) => {
    if (labels.has(evidence.id)) return;
    counts[evidence.kind] += 1;
    labels.set(evidence.id, `${evidence.kind === "technical" ? "S" : "J"}${counts[evidence.kind]}`);
  };
  for (const section of sections) {
    for (const id of section.citation_ids) {
      const evidence = byId.get(id);
      if (evidence) label(evidence);
    }
  }
  citations.forEach(label);
  return labels;
}
```

- [x] **Step 4: `content.tsx` 增加标记模式**（默认模式保持原样，`tests/reader.test.tsx` 不变）

把 `const labels: Record<Section["kind"], string>` 改名为 `kindLabels`（两处引用一起改），在 `SourcedContent` 之前加入：

```tsx
function Markers({ ids, citations, labels, selectedId, onSelect }: {
  ids: string[]; citations: Evidence[]; labels: Map<string, string>;
  selectedId: string | null; onSelect: (id: string) => void;
}) {
  if (!ids.length) return null;
  return <p className="markers">{ids.map((id) => {
    const citation = citations.find((item) => item.id === id);
    const label = labels.get(id);
    if (!citation || !label) return <span key={id} className="status-chip warn">引用缺失，暂时无法核对原文</span>;
    return <button key={id} type="button" className={`marker ${citation.kind}`} aria-pressed={selectedId === id}
      aria-label={`来源 ${label}：${citation.title || "未命名来源"}`} onClick={() => onSelect(id)}>{label}</button>;
  })}</p>;
}
```

`SourcedContent` 改为：

```tsx
export function SourcedContent({ sections, citations, labels, selectedId = null, onSelect }: {
  sections: Section[]; citations: Evidence[];
  labels?: Map<string, string>; selectedId?: string | null; onSelect?: (id: string) => void;
}) {
  return <div className="sourced-content">
    {sections.map((section, index) => (
      <section key={index} className={`evidence-section ${section.kind}`} aria-label={kindLabels[section.kind]}>
        <h3 className="evidence-label"><span className="evidence-dot" aria-hidden="true" />{kindLabels[section.kind]}</h3>
        <SafeMarkdown text={section.text} />
        {section.kind !== "model_supplement" && section.citation_ids.length === 0 &&
          <p className="notice warning">这段内容没有附带引用，不能据此确认来源支持。</p>}
        {labels && onSelect
          ? <Markers ids={section.citation_ids} citations={citations} labels={labels} selectedId={selectedId} onSelect={onSelect} />
          : section.citation_ids.map((id) => {
            const citation = citations.find((item) => item.id === id);
            return citation
              ? <EvidenceLink key={id} evidence={citation} />
              : <p key={id} className="notice warning">引用缺失，暂时无法核对原文。</p>;
          })}
      </section>
    ))}
  </div>;
}
```

- [x] **Step 5: 新建 `frontend/src/components/evidence-panel.tsx`**

```tsx
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
```

- [x] **Step 6: `wiki-views.tsx` 接入**

6a. 导入：

```tsx
import { useCallback, useEffect, useMemo, useState } from "react";
import { citationLabels } from "../lib/evidence";
import { EvidencePanel } from "./evidence-panel";
```

6b. `AgentPanel` 最外层 `<aside className="agent-panel">…</aside>` 改为 `<div className="agent-panel">…</div>`。

6c. `WikiView`：在 `const [review, setReview] = useState(false);` 之后加入

```tsx
  const [selected, setSelected] = useState<string | null>(null);
  const [tab, setTab] = useState<"sources" | "agent">("sources");
  const labels = useMemo(() => state.data ? citationLabels(state.data.sections, state.data.citations)
    : new Map<string, string>(), [state.data]);
```

在 `const page = state.data;` 之后加入

```tsx
  const select = (evidenceId: string) => {
    setSelected((current) => current === evidenceId ? null : evidenceId);
    setTab("sources");
  };
```

6d. `WikiView` 的返回改为（正文包进 `.reading-column`，删除“全部原始来源”折叠块，右栏改为标签页）：

```tsx
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
```

- [x] **Step 7: 运行** — `npx vitest run tests/evidence.test.tsx tests/reader.test.tsx tests/app.test.tsx` → 全部通过。

- [x] **Step 8: 检查点** — `npx vitest run && npm run typecheck`。

---

### Task 9: 草稿与整理页显示四段流程

**Files:**
- Modify: `frontend/src/components/journal-views.tsx`
- Test: `frontend/tests/draft-view.test.tsx`（追加一项）

- [x] **Step 1: 追加失败的测试**

```tsx
it("shows each stage of an offline draft instead of a single saved flag", async () => {
  const api = new ApiClient(async () => Response.json([]));
  const offline = new OfflineClient(api, `stages-${crypto.randomUUID()}`);
  const draft = await offline.saveDraft(newDraft());
  render(<DraftView id={draft.client_id} context={{ api, offline, online: false }} />);
  const steps = await screen.findByRole("list", { name: "记录进度" });
  expect(within(steps).getByText("需联网，由你确认")).toBeVisible();
  expect(within(steps).getByText("提交后开始")).toBeVisible();
  expect(screen.getByText("已存本机 · 未提交")).toBeVisible();
});
```

（在文件顶部把 `within` 加入 `@testing-library/react` 的导入。）

- [x] **Step 2: 运行，确认失败** — `npx vitest run tests/draft-view.test.tsx` → 新测试 FAIL（没有“记录进度”列表）。

- [x] **Step 3: 修改 `journal-views.tsx`**

3a. 导入：

```tsx
import { draftStatus, pipeline, runStatus } from "../lib/status";
import { PipelineStepper, StatusChip } from "./status";
```

3b. 文件底部的 `const runStatus = {…}` 改名为 `const runHeadings = {…}`，`RunView` 里 `{runStatus[run.status]}` 改为 `{runHeadings[run.status]}`。

3c. `DraftsView` 列表里的标签：

```tsx
        <StatusChip status={draftStatus(draft.state)} />
```

替换原来的 `<span className="tag">{draft.state === "locked" ? "已尝试提交 · 等待回执" : "本机草稿 · 未提交"}</span>`。

3d. `DraftEditor` 编辑态：把

```tsx
    <span className={`tag ${dirty || locked ? "amber" : ""}`}>{dirty ? "当前输入尚未保存" : locked ? "提交内容已锁定，等待核对" : "已存本机，尚未提交"}</span>
```

替换为

```tsx
    <StatusChip status={draftStatus(draft.state, dirty)} />
    <PipelineStepper stages={pipeline({ dirty, locked, receipt: false, online: context.online, run: null })} />
```

3e. `DraftEditor` 回执态：在 `<Notice>服务端回执与本机回执都已保存…</Notice>` 之后加入

```tsx
    <PipelineStepper stages={pipeline({ dirty: false, locked: false, receipt: true, online: context.online,
      run: receipt.run_id ? "unknown" : null })} />
```

3f. `RunView`：在 `<h1>{runHeadings[run.status]}</h1>` 之后加入

```tsx
    <StatusChip status={runStatus(run.status)} />
    {run.entry_id && <PipelineStepper stages={pipeline({ dirty: false, locked: false, receipt: true, online: context.online,
      run: run.status, updated: Boolean(run.result_version_id) })} />}
```

- [x] **Step 4: 运行** — `npx vitest run tests/draft-view.test.tsx` → 2 passed。

- [x] **Step 5: 检查点** — `npx vitest run && npm run typecheck`。

---

### Task 10: 版本段落差异

**Files:**
- Create: `frontend/src/lib/diff.ts`, `frontend/src/components/version-diff.tsx`
- Modify: `frontend/src/components/wiki-views.tsx`（`VersionReview`）
- Test: `frontend/tests/diff.test.tsx`

- [x] **Step 1: 写失败的测试**

```tsx
import { render, screen, within } from "@testing-library/react";
import { expect, it } from "vitest";
import { VersionDiff } from "../src/components/version-diff";
import { diffParagraphs } from "../src/lib/diff";

it("reports removed and added paragraphs between versions", () => {
  expect(diffParagraphs("开头\n\n旧说法\n\n结尾", "开头\n\n新说法\n\n结尾\n\n补充")).toEqual([
    { kind: "same", text: "开头" },
    { kind: "removed", text: "旧说法" },
    { kind: "added", text: "新说法" },
    { kind: "same", text: "结尾" },
    { kind: "added", text: "补充" },
  ]);
});

it("ignores blank-line differences", () => {
  expect(diffParagraphs("a\n\nb", "a\n\n\n  \nb")).toEqual([{ kind: "same", text: "a" }, { kind: "same", text: "b" }]);
});

it("shows only the paragraphs that changed", () => {
  render(<VersionDiff before={"开头\n\n旧说法"} after={"开头\n\n新说法"} fromLabel="v3" toLabel="v4" />);
  const region = screen.getByRole("region", { name: "v3 → v4 的差异" });
  expect(within(region).getByText("新增 1 段")).toBeVisible();
  expect(within(region).getByText("旧说法").closest(".diff-block")).toHaveClass("removed");
  expect(within(region).getByText("新说法").closest(".diff-block")).toHaveClass("added");
  expect(within(region).queryByText("开头")).toBeNull();
});
```

- [x] **Step 2: 运行，确认失败** — `npx vitest run tests/diff.test.tsx` → FAIL（模块不存在）。

- [x] **Step 3: 实现 `frontend/src/lib/diff.ts`**

```ts
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
```

- [x] **Step 4: 实现 `frontend/src/components/version-diff.tsx`**

```tsx
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
```

- [x] **Step 5: `VersionReview` 使用差异视图**

导入 `import { VersionDiff } from "./version-diff";`，把

```tsx
        {page.version_id !== current.id && <details><summary>对照当前已发布内容</summary><SafeMarkdown text={page.content} /></details>}
```

替换为

```tsx
        {page.version_id !== current.id && <VersionDiff before={page.content} after={current.content}
          fromLabel={page.version ? `当前 v${page.version}` : "当前"} toLabel={`v${current.number}`} />}
```

- [x] **Step 6: 运行** — `npx vitest run tests/diff.test.tsx tests/app.test.tsx` → 全部通过。

- [x] **Step 7: 检查点** — `npx vitest run && npm run typecheck`。

---

### Task 11: 设计稿与代码共用一份 token

**Files:**
- Modify: `docs/design/visual-v2/index.html`, `docs/design/visual-v2/design-philosophy-v2.md`

- [x] **Step 1:** `index.html` 的 `<link rel="stylesheet" href="tokens.css">` 改为 `href="../../../frontend/src/app/tokens.css"`；00 板页脚的 “token 源文件：docs/design/visual-v2/tokens.css” 改为 “token 源文件：frontend/src/app/tokens.css”。
- [x] **Step 2:** `design-philosophy-v2.md` 里 `tokens.css` 的位置说明同步改为 `frontend/src/app/tokens.css`，“待你决定”一节标注已按确认的方向实现（4 个标签、浅色默认 + 深色可选）。
- [x] **Step 3:** `docs/design/visual-v2/render.sh` 重新导出五张 PNG，确认画面与之前一致。

---

### Task 12: 完整验证

- [x] **Step 1: 自动检查**

```bash
cd frontend
npm test
npm run typecheck
NEXT_TELEMETRY_DISABLED=1 npm run build
```

Expected: 全部测试通过（原 15 项 + 新增 17 项）；typecheck 通过；生产构建成功。

- [x] **Step 2: 用假数据看真实界面**（不连真实后端，不碰个人数据）

在临时目录放两个脚本：

`mock-backend.mjs`：在 `127.0.0.1:8799` 上按 `src/lib/contracts.ts` 的形状返回固定 JSON（状态、技术 / 个人 Wiki 列表、一篇带 2 份技术来源和 1 份本人记录的“反手切削”页、它的 v3 / v4 版本、空的训练卡与记录），写请求一律返回 501。

`auth-proxy.mjs`：在 `127.0.0.1:3100` 转发到 `127.0.0.1:3000`，为每个请求加上本次会话随机生成的测试凭据（只存在临时目录，不写进仓库、不出现在对话里），保留原 Host 头。

启动：

```bash
OWNER_USERNAME=owner OWNER_PASSWORD="$PREVIEW_PASSWORD" BACKEND_ORIGIN=http://127.0.0.1:8799 \
  PUBLIC_ORIGIN=http://127.0.0.1:3100 NEXT_TELEMETRY_DISABLED=1 npx next dev -p 3000
node mock-backend.mjs & node auth-proxy.mjs &
```

- [x] **Step 3: 截图核对**（桌面 1440 宽、手机 390 宽、深色）

- 知识首页：四个导航、状态标签、草稿角标
- 阅读页：36 字行宽、来源标记、点 S1 后右栏定位卡高亮
- 手机阅读页：点标记后底部抽屉、上一个 / 下一个
- 版本审阅：v3 → v4 段落差异
- 深色模式：切换后整页换色，文字可读

- [x] **Step 4: 收尾** — 停掉预览进程，删除临时脚本；汇报测试与截图结果，询问是否提交。

---

## 执行记录（2026-10-01）

全部任务已完成：33 个测试通过（原 15 个 + 新增 18 个），`npm run typecheck` 与生产构建通过。未提交。与计划的出入：

1. **测试环境**：本机 Node 25 自带的全局 `localStorage` 会盖住 jsdom 的实现，导致主题测试无法读写存储。已在 `tests/setup.ts` 里换回 jsdom 的实现（Node 22 不受影响）。
2. **手机导航读屏名称**：角标的读屏文字原本排在“记录”之前，已拆成 `DraftBadge`（视觉角标）和 `DraftNote`（读屏文字，放在标签之后）。
3. **来源标记**：点击同一标记原本会切换选中 / 取消；手机触控模拟下一次点击被触发两次，状态又被切回去。已改为只选中，取消用抽屉的关闭按钮或点遮罩。
4. **样式补丁**：系统提示（`main > .notice`）加左右边距；阅读页右栏补 `min-height`，内容较短时背景铺到底部。
5. **真实界面验证**：`next dev` 的热更新 websocket 无法经过临时鉴权代理，改用生产构建的 standalone 服务器预览。`next dev` 在 `frontend/` 自动生成了 `AGENTS.md`、`CLAUDE.md`，已删除；以后运行 `npm run dev` 会再次生成，可在 `next.config` 设 `agentRules: false` 关闭，或选择提交。
6. **Service worker**：内置浏览器面板无法注册 service worker（`sw.js` 本身返回 200），应用按预期显示“离线页面暂时不可用”。headless Chrome 中无此提示。真机 PWA 仍需单独验收。

截图（假数据）：`docs/design/visual-v2/app-screens/`，共 9 张：桌面知识页、阅读页选中来源、版本差异、深色阅读，手机阅读、来源抽屉、离线草稿四段流程、草稿角标、深色个人 Wiki。
