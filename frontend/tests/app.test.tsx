import { render, screen } from "@testing-library/react";
import { expect, it } from "vitest";
import { AppShell } from "../src/components/app-shell";
import { ApiClient } from "../src/lib/api";
import { WikiView } from "../src/components/wiki-views";
import { OfflineClient } from "../src/lib/offline";

it("opens an empty private library without inventing tutorials or training history", async () => {
  const api = new ApiClient(async (url) => {
    if (String(url).includes("/status")) return Response.json({
      ready: true, agent_enabled: false, model_configured: false,
      sources_count: 0, pending_reviews: 0,
    });

    return Response.json([]);
  });
  render(<AppShell api={api} />);
  expect(await screen.findByRole("button", { name: "导入现有教程" })).toBeVisible();
  expect(screen.getByText("你的知识库还没有资料")).toBeVisible();
  expect(screen.queryByText("15 份教程")).toBeNull();
});

it("marks unpublished technical content and exposes explicit approval rather than auto-publishing", async () => {
  const page = {
    id: "page-1", space: "technical", title: "Imported source", topic: "Forehand",
    version: 0, updated_at: "2026-09-25T08:00:00Z", has_draft: true,
    index_status: "pending", record_count: 0, version_id: "v1", status: "draft",
    content: "# Imported source", sections: [], citations: [], change_summary: "New source",
  };
  const api = new ApiClient(async (url) => {
    if (String(url).endsWith("/versions")) return Response.json([{
      ...page, id: "v1", page_id: "page-1", number: 1, created_at: page.updated_at,
    }]);
    return Response.json(page);
  });
  const offline = new OfflineClient(api, `wiki-ui-${crypto.randomUUID()}`);
  render(<WikiView id="page-1" context={{ api, offline, online: true }} />);
  expect(await screen.findByText(/草稿尚未成为正式技术依据/)).toBeVisible();
  expect(await screen.findByRole("button", { name: "确认发布此版本" })).toBeVisible();
});

it("switches to explicit local mode when fetch fails even if navigator reports online", async () => {
  const api = new ApiClient(async () => { throw new TypeError("Network unreachable"); });
  render(<AppShell api={api} />);
  expect(await screen.findByText("连接不可用 · 只读已保存内容，草稿不会自动上传")).toBeVisible();
  expect(screen.getByRole("button", { name: "检测连接" })).toBeVisible();
  expect(screen.queryByRole("button", { name: "导入现有教程" })).toBeNull();
});
