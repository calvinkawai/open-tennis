import { describe, expect, it, vi } from "vitest";
import { ApiClient } from "../src/lib/api";
import { journalInputSchema } from "../src/lib/contracts";
import type { WikiDetail } from "../src/lib/contracts";
import { OfflineClient, newDraft } from "../src/lib/offline";

describe("owner-controlled offline client", () => {
  it("can create valid draft identifiers in a LAN HTTP preview without randomUUID", () => {
    const getRandomValues = crypto.getRandomValues.bind(crypto);
    vi.stubGlobal("crypto", { getRandomValues });
    try {
      const first = newDraft({ content: "LAN preview only" });
      const second = newDraft({ content: "A second preview draft" });
      expect(() => journalInputSchema.parse(first)).not.toThrow();
      expect(first.client_id).toMatch(/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/);
      expect(first.client_id).not.toBe(second.client_id);
    } finally {
      vi.unstubAllGlobals();
    }
  });
  it("does not report a saved draft when local storage is full", async () => {
    const client = new OfflineClient(new ApiClient(), `quota-test-${crypto.randomUUID()}`);
    const draft = newDraft({ content: "Preserve this observation before leaving." });
    const put = vi.spyOn(IDBObjectStore.prototype, "put").mockImplementationOnce(() => {
      throw new DOMException("Synthetic storage quota", "QuotaExceededError");
    });
    try {
      await expect(client.saveDraft(draft)).rejects.toMatchObject({ code: "quota" });
      expect(await client.getDraft(draft.client_id)).toBeUndefined();
    } finally {
      put.mockRestore();
      await client.close();
    }
  });
  it("restores the exact local draft after reopening and does not upload on reconnect", async () => {
    const transport = vi.fn<typeof fetch>();
    const api = new ApiClient(transport);
    const database = `draft-test-${crypto.randomUUID()}`;
    const first = new OfflineClient(api, database);
    const saved = await first.saveDraft(newDraft({
      content: "测试记录：快球时来不及准备。",
      feeling: "只保留本人感受，不作为动作诊断。",
      completed_drill_ids: [12],
      plan_id: 3,
    }));
    await first.close();

    const reopened = new OfflineClient(api, database);
    expect(await reopened.getDraft(saved.client_id)).toEqual(saved);
    window.dispatchEvent(new Event("online"));
    await Promise.resolve();
    expect(transport).not.toHaveBeenCalled();
    await reopened.close();
  });

  it("retries a lost acknowledgement with the same locked payload and retains a durable receipt", async () => {
    const received: unknown[] = [];
    const transport: typeof fetch = async (_url, init) => {
      const payload = journalInputSchema.parse(JSON.parse(String(init?.body)));
      received.push(payload);
      if (received.length === 1) throw new TypeError("connection lost after server commit");
      return Response.json({
        ...payload, id: "journal-1", created_at: "2026-09-25T08:00:00Z", run_id: "run-1",
      });
    };
    const database = `retry-test-${crypto.randomUUID()}`;
    const client = new OfflineClient(new ApiClient(transport), database);
    const saved = await client.saveDraft(newDraft({ content: "测试：保留这句原话。" }));
    await expect(client.confirmAndSubmit(saved.client_id, {
      confirmed: true, revision: saved.revision,
    })).rejects.toMatchObject({ status: 0 });

    const pending = await client.getDraft(saved.client_id);
    expect(pending?.state).toBe("locked");
    await expect(client.saveDraft({ ...saved, content: "不可悄悄更换内容" }))
      .rejects.toMatchObject({ code: "locked" });
    if (!pending) throw new Error("the unacknowledged draft must survive");

    const result = await client.confirmAndSubmit(pending.client_id, {
      confirmed: true, revision: pending.revision,
    });
    expect(received).toHaveLength(2);
    expect(received[1]).toEqual(received[0]);
    expect(result.id).toBe("journal-1");
    expect(await client.getDraft(saved.client_id)).toBeUndefined();
    await client.close();

    const reopened = new OfflineClient(new ApiClient(transport), database);
    expect((await reopened.getReceipt(saved.client_id))?.journal.id).toBe("journal-1");
    expect(await reopened.confirmAndSubmit(saved.client_id, { confirmed: true, revision: 0 }))
      .toMatchObject({ id: "journal-1" });
    expect(received).toHaveLength(2);
    await reopened.close();
  });

  it("saves a page and its original sources only after an explicit offline-save action", async () => {
    const evidence = {
      id: "source-1", kind: "technical" as const, title: "测试来源", excerpt: "摘录",
      revision: "r1", source_url: null,
    };
    const page: WikiDetail = {
      id: "wiki-1", space: "technical", title: "测试页", topic: "测试主题", version: 2,
      updated_at: "2026-09-25T08:00:00Z", has_draft: false, index_status: "ready",
      record_count: 0, version_id: "version-2", status: "published", content: "测试正文",
      sections: [{ kind: "source_supported", text: "测试正文", citation_ids: ["source-1"] }],
      citations: [evidence], change_summary: "测试变更",
    };
    const transport = vi.fn<typeof fetch>().mockResolvedValue(Response.json({
      ...evidence, content: "测试来源的完整原文",
    }));
    const client = new OfflineClient(new ApiClient(transport), `cache-test-${crypto.randomUUID()}`);
    expect(await client.getSavedWiki("wiki-1")).toBeUndefined();
    expect(transport).not.toHaveBeenCalled();
    await client.saveWiki(page);
    expect((await client.getSavedWiki("wiki-1"))?.value).toEqual(page);
    expect((await client.getSavedEvidence("source-1"))?.value.content).toBe("测试来源的完整原文");
    expect((await client.exportData()).saved).toHaveLength(2);
    await client.close();
  });
});
