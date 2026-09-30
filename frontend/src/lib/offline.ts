import { openDB, type DBSchema, type IDBPDatabase } from "idb";
import { z } from "zod";
import { ApiClient, ApiError } from "./api";
import {
  dateSchema, evidenceDetailSchema, journalInputSchema, journalSchema, planSchema,
  wikiDetailSchema, type Evidence, type EvidenceDetail, type Journal, type JournalInput,
  type Plan, type Space, type WikiDetail,
} from "./contracts";

export class LocalError extends Error {
  readonly name = "LocalError";
  constructor(readonly code: string, message: string) {
    super(message);
  }
}

function storageError(error: unknown): Error {
  if (error instanceof LocalError) return error;
  if (error instanceof DOMException && error.name === "QuotaExceededError") {
    return new LocalError("quota", "本机存储空间不足。内容尚未保存，请先导出草稿再释放空间。");
  }
  return new LocalError(
    "storage",
    "无法读写本机存储。请勿关闭未保存的记录，先复制或导出；隐私模式或系统限制可能导致此问题。",
  );
}

export const draftSchema = journalInputSchema.extend({
  created_at: dateSchema,
  updated_at: dateSchema,
  revision: z.number().int().nonnegative(),
  state: z.enum(["editable", "locked"]),
});
export type LocalDraft = z.infer<typeof draftSchema>;

const receiptSchema = z.object({
  client_id: z.uuid(),
  journal: journalSchema,
  acknowledged_at: dateSchema,
});
export type Receipt = z.infer<typeof receiptSchema>;

const savedBase = z.object({ key: z.string(), saved_at: dateSchema });
export const savedItemSchema = z.discriminatedUnion("kind", [
  savedBase.extend({ kind: z.literal("wiki"), value: wikiDetailSchema }),
  savedBase.extend({ kind: z.literal("plan"), value: planSchema }),
  savedBase.extend({ kind: z.literal("evidence"), value: evidenceDetailSchema }),
]);
export type SavedItem = z.infer<typeof savedItemSchema>;
export type Saved<K extends SavedItem["kind"]> = Extract<SavedItem, { kind: K }>;

function submissionId(): string {
  if (typeof crypto.randomUUID === "function") return crypto.randomUUID();
  // LAN HTTP previews lack randomUUID, but still expose cryptographic random bytes.
  const bytes = crypto.getRandomValues(new Uint8Array(16));
  bytes[6] = (bytes[6] & 0x0f) | 0x40;
  bytes[8] = (bytes[8] & 0x3f) | 0x80;
  const hex = Array.from(bytes, (byte) => byte.toString(16).padStart(2, "0")).join("");
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
}

export function newDraft(seed: Partial<Omit<JournalInput, "client_id">> = {}): LocalDraft {
  const now = new Date().toISOString();
  return draftSchema.parse({
    client_id: submissionId(),
    plan_id: null,
    page_id: null,
    content: "",
    context: null,
    feeling: null,
    completed_drill_ids: [],
    ...seed,
    created_at: now,
    updated_at: now,
    revision: 0,
    state: "editable",
  });
}

interface LocalDatabase extends DBSchema {
  drafts: { key: string; value: LocalDraft };
  receipts: { key: string; value: Receipt };
  saved: { key: string; value: SavedItem };
}

export class OfflineClient {
  private connection: Promise<IDBPDatabase<LocalDatabase>> | null = null;
  private submissions = new Map<string, Promise<Journal>>();

  constructor(
    private readonly api: ApiClient,
    private readonly databaseName = "open-tennis-local-v1",
  ) {}

  private db() {
    if (!this.connection) {
      this.connection = openDB<LocalDatabase>(this.databaseName, 1, {
        upgrade(database) {
          database.createObjectStore("drafts", { keyPath: "client_id" });
          database.createObjectStore("receipts", { keyPath: "client_id" });
          database.createObjectStore("saved", { keyPath: "key" });
        },
        blocking: () => {
          void this.close();
        },
        terminated: () => {
          this.connection = null;
        },
      }).catch((error: unknown) => {
        this.connection = null;
        throw storageError(error);
      });
    }
    return this.connection;
  }

  async close() {
    if (this.connection) (await this.connection).close();
    this.connection = null;
  }

  async getDraft(id: string): Promise<LocalDraft | undefined> {
    try {
      const value = await (await this.db()).get("drafts", id);
      if (!value) return undefined;
      return draftSchema.parse(value);
    } catch (error) {
      throw storageError(error);
    }
  }

  async listDrafts(): Promise<LocalDraft[]> {
    try {
      return draftSchema.array().parse(await (await this.db()).getAll("drafts"))
        .sort((a, b) => b.updated_at.localeCompare(a.updated_at));
    } catch (error) {
      throw storageError(error);
    }
  }

  async saveDraft(input: LocalDraft): Promise<LocalDraft> {
    const draft = draftSchema.parse(input);
    try {
      const transaction = (await this.db()).transaction(["drafts", "receipts"], "readwrite");
      const existing = await transaction.objectStore("drafts").get(draft.client_id);
      if (await transaction.objectStore("receipts").get(draft.client_id)) {
        throw new LocalError("acknowledged", "此记录已有服务端回执，不能再覆盖原始内容。");
      }
      if (existing?.state === "locked") {
        throw new LocalError("locked", "这份草稿已尝试提交，内容已锁定。请用原编号确认重试，避免重复记录。");
      }
      if ((existing?.revision ?? 0) !== draft.revision) {
        throw new LocalError("conflict", "草稿已在另一个页面更改。请重新打开并核对，不要覆盖新内容。");
      }
      const saved: LocalDraft = {
        ...draft,
        state: "editable",
        revision: draft.revision + 1,
        updated_at: new Date().toISOString(),
      };
      await transaction.objectStore("drafts").put(saved);
      await transaction.done;
      return saved;
    } catch (error) {
      throw storageError(error);
    }
  }

  async getReceipt(id: string): Promise<Receipt | undefined> {
    try {
      const receipt = await (await this.db()).get("receipts", id);
      return receipt ? receiptSchema.parse(receipt) : undefined;
    } catch (error) {
      throw storageError(error);
    }
  }

  async listReceipts(): Promise<Receipt[]> {
    try {
      return receiptSchema.array().parse(await (await this.db()).getAll("receipts"));
    } catch (error) {
      throw storageError(error);
    }
  }

  confirmAndSubmit(id: string, confirmation: { confirmed: boolean; revision: number }): Promise<Journal> {
    if (!confirmation.confirmed) {
      return Promise.reject(new LocalError("confirmation", "只有本人再次确认后才能上传草稿。"));
    }
    const pending = this.submissions.get(id);
    if (pending) return pending;
    const submission = this.submitConfirmed(id, confirmation.revision)
      .finally(() => this.submissions.delete(id));
    this.submissions.set(id, submission);
    return submission;
  }

  private async submitConfirmed(id: string, revision: number): Promise<Journal> {
    const previousReceipt = await this.getReceipt(id);
    if (previousReceipt) {
      await this.removeAcknowledgedDraft(id);
      return previousReceipt.journal;
    }
    const draft = await this.lockDraft(id, revision);
    const payload = journalInputSchema.parse(draft);
    const journal = await this.api.submitJournal(payload);
    const acknowledgement = journalInputSchema.parse(journal);
    if (JSON.stringify(acknowledgement) !== JSON.stringify(payload)) {
      throw new ApiError(502, "ack_mismatch", null, "回执与原始草稿不一致。草稿已保留，请勿新建重复记录。");
    }
    try {
      await (await this.db()).put("receipts", {
        client_id: id, journal, acknowledged_at: new Date().toISOString(),
      });
    } catch {
      throw new LocalError(
        "receipt",
        "服务器已接收，但回执未能存入本机。原草稿仍保留；请稍后用同一草稿核对或重试，不要新建重复记录。",
      );
    }
    await this.removeAcknowledgedDraft(id);
    return journal;
  }

  private async lockDraft(id: string, revision: number): Promise<LocalDraft> {
    try {
      const transaction = (await this.db()).transaction("drafts", "readwrite");
      const value = await transaction.store.get(id);
      if (!value) throw new LocalError("missing", "本机没有这份草稿。请检查原设备或已导出的文件。");
      const draft = draftSchema.parse(value);
      if (draft.revision !== revision) {
        throw new LocalError("conflict", "草稿已经变更。请重新打开，核对内容后再次确认提交。");
      }
      if (!draft.content.trim() && draft.completed_drill_ids.length === 0) {
        throw new LocalError("empty", "请留下一句记录或至少确认完成一项练习。");
      }
      const locked: LocalDraft = draft.state === "locked" ? draft : {
        ...draft, state: "locked", revision: draft.revision + 1,
      };
      await transaction.store.put(locked);
      await transaction.done;
      return locked;
    } catch (error) {
      throw storageError(error);
    }
  }

  private async removeAcknowledgedDraft(id: string) {
    try {
      const transaction = (await this.db()).transaction(["receipts", "drafts"], "readwrite");
      if (!(await transaction.objectStore("receipts").get(id))) {
        throw new LocalError("receipt", "没有持久回执，不能移除草稿。");
      }
      await transaction.objectStore("drafts").delete(id);
      await transaction.done;
    } catch {
      throw new LocalError(
        "cleanup",
        "服务端记录和本机回执均已保存，但草稿清理失败。原编号可安全核对，请勿新建重复记录。",
      );
    }
  }

  private async getSaved(key: string): Promise<SavedItem | undefined> {
    try {
      const saved = await (await this.db()).get("saved", key);
      return saved ? savedItemSchema.parse(saved) : undefined;
    } catch (error) {
      throw storageError(error);
    }
  }

  async getSavedWiki(id: string) {
    const saved = await this.getSaved(`wiki:${id}`);
    return saved?.kind === "wiki" ? saved : undefined;
  }

  async getSavedPlan(id: number) {
    const saved = await this.getSaved(`plan:${id}`);
    return saved?.kind === "plan" ? saved : undefined;
  }

  async getSavedEvidence(id: string) {
    const saved = await this.getSaved(`evidence:${id}`);
    return saved?.kind === "evidence" ? saved : undefined;
  }

  async listSaved(): Promise<SavedItem[]> {
    try {
      return savedItemSchema.array().parse(await (await this.db()).getAll("saved"))
        .sort((a, b) => b.saved_at.localeCompare(a.saved_at));
    } catch (error) {
      throw storageError(error);
    }
  }

  async listSavedWiki(space: Space, query = "") {
    const items = await this.listSaved();
    return items.filter((item): item is Saved<"wiki"> => item.kind === "wiki")
      .filter(({ value }) => value.space === space &&
        `${value.title} ${value.topic}`.toLocaleLowerCase().includes(query.toLocaleLowerCase()));
  }

  async listSavedPlans() {
    return (await this.listSaved()).filter((item): item is Saved<"plan"> => item.kind === "plan");
  }

  private async sources(citations: Evidence[]): Promise<Saved<"evidence">[]> {
    return Promise.all(citations.map(async (citation) => {
      const evidence = await this.api.evidence(citation.id);
      if (evidence.id !== citation.id || evidence.revision !== citation.revision) {
        throw new ApiError(409, "source_changed", null, "来源版本已变化。本次离线保存未完成，请刷新页面后重新核对。");
      }
      return {
        key: `evidence:${evidence.id}`, kind: "evidence", value: evidence,
        saved_at: new Date().toISOString(),
      };
    }));
  }

  private async saveBundle(items: SavedItem[]) {
    try {
      const parsed = savedItemSchema.array().parse(items);
      const transaction = (await this.db()).transaction("saved", "readwrite");
      await Promise.all([...parsed.map((item) => transaction.store.put(item)), transaction.done]);
    } catch (error) {
      throw storageError(error);
    }
  }

  async saveWiki(page: WikiDetail) {
    const value = wikiDetailSchema.parse(page);
    const sources = await this.sources(value.citations);
    const saved: Saved<"wiki"> = {
      key: `wiki:${value.id}`, kind: "wiki", value, saved_at: new Date().toISOString(),
    };
    await this.saveBundle([saved, ...sources]);
    return saved;
  }

  async savePlan(plan: Plan) {
    const value = planSchema.parse(plan);
    const sources = await this.sources(value.citations);
    const saved: Saved<"plan"> = {
      key: `plan:${value.id}`, kind: "plan", value, saved_at: new Date().toISOString(),
    };
    await this.saveBundle([saved, ...sources]);
    return saved;
  }

  async saveEvidence(evidence: EvidenceDetail) {
    const value = evidenceDetailSchema.parse(evidence);
    const saved: Saved<"evidence"> = {
      key: `evidence:${value.id}`, kind: "evidence", value, saved_at: new Date().toISOString(),
    };
    await this.saveBundle([saved]);
    return saved;
  }

  async exportData() {
    try {
      const transaction = (await this.db()).transaction(["drafts", "receipts", "saved"], "readonly");
      const [drafts, receipts, saved] = await Promise.all([
        transaction.objectStore("drafts").getAll(),
        transaction.objectStore("receipts").getAll(),
        transaction.objectStore("saved").getAll(),
      ]);
      await transaction.done;
      return {
        format: "open-tennis-local-export-v1" as const,
        exported_at: new Date().toISOString(),
        drafts: draftSchema.array().parse(drafts),
        receipts: receiptSchema.array().parse(receipts),
        saved: savedItemSchema.array().parse(saved),
      };
    } catch (error) {
      throw storageError(error);
    }
  }

  async removeSaved(key: string) {
    try {
      await (await this.db()).delete("saved", key);
    } catch (error) {
      throw storageError(error);
    }
  }

  async discardDraft(id: string) {
    try {
      const transaction = (await this.db()).transaction("drafts", "readwrite");
      const draft = await transaction.store.get(id);
      if (draft?.state === "locked") {
        throw new LocalError("locked", "提交结果未核对前不能移除这份草稿。请使用同一编号确认重试。");
      }
      await transaction.store.delete(id);
      await transaction.done;
    } catch (error) {
      throw storageError(error);
    }
  }

  async clearDeviceData() {
    try {
      const transaction = (await this.db()).transaction(["drafts", "receipts", "saved"], "readwrite");
      await Promise.all([
        transaction.objectStore("drafts").clear(),
        transaction.objectStore("receipts").clear(),
        transaction.objectStore("saved").clear(),
        transaction.done,
      ]);
    } catch (error) {
      throw storageError(error);
    }
  }
}
