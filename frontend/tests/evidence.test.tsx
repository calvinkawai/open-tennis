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
