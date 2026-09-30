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
