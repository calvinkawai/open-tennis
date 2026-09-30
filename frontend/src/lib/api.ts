import { z } from "zod";
import {
  type JournalInput, type PlanEdit, type Question, type Space,
  answerSchema, evidenceDetailSchema, journalInputSchema, journalSchema,
  planSchema, previewSchema, runSchema, statusSchema, wikiDetailSchema,
  wikiSummarySchema, wikiVersionSchema,
} from "./contracts";

const messages: Record<number, string> = {
  0: "无法连接服务。请检查网络；本机草稿不会自动上传。",
  401: "访问验证已失效。请重新验证本人身份。",
  403: "当前身份没有此操作权限。",
  404: "未找到这项内容。它可能已变更，请返回列表刷新。",
  409: "内容版本发生冲突。请刷新并核对最新内容，不要重复新建记录。",
  413: "内容过长，服务器未接受这次请求。",
  422: "提交内容未通过校验。请核对必填内容与关联项目。",
  429: "请求过于频繁，请稍后手动重试。",
  502: "上游服务暂时不可用。本次操作没有得到成功确认。",
  503: "服务尚未就绪或配置不完整。本次操作没有得到成功确认。",
  504: "服务响应超时。本次操作没有得到成功确认。",
};

export class ApiError extends Error {
  readonly name = "ApiError";
  constructor(
    readonly status: number,
    readonly code: string | null = null,
    readonly requestId: string | null = null,
    message = messages[status] ?? "服务请求失败。本次操作没有得到成功确认。",
  ) {
    super(message);
  }
}

const errorSchema = z.object({
  code: z.string().regex(/^[a-zA-Z0-9_-]{1,64}$/).optional(),
  request_id: z.string().regex(/^[a-zA-Z0-9_:.-]{1,120}$/).optional(),
});

export class ApiClient {
  constructor(private readonly transport: typeof fetch = (...args) => fetch(...args)) {}

  private async request<T>(path: string, schema: z.ZodType<T>, init: RequestInit = {}): Promise<T> {
    let response: Response;
    try {
      response = await this.transport(`/api/v1${path}`, {
        ...init,
        credentials: "include",
        cache: "no-store",
        headers: {
          Accept: "application/json",
          ...(init.body ? { "Content-Type": "application/json" } : {}),
        },
        signal: AbortSignal.timeout(120_000),
      });
    } catch {
      if (typeof window !== "undefined") window.dispatchEvent(new Event("open-tennis:connection-lost"));
      throw new ApiError(0);
    }

    let data: unknown;
    try {
      data = await response.json();
    } catch {
      throw new ApiError(
        response.ok ? 502 : response.status,
        response.ok ? "invalid_response" : null,
      );
    }
    if (!response.ok) {
      const error = errorSchema.safeParse(data);
      throw new ApiError(
        response.status,
        error.success ? error.data.code ?? null : null,
        error.success ? error.data.request_id ?? null : null,
      );
    }
    const parsed = schema.safeParse(data);
    if (!parsed.success) {
      throw new ApiError(502, "invalid_response", null, "服务返回的数据不完整，不能确认操作成功。");
    }
    return parsed.data;
  }

  listWiki(space: Space, query = "") {
    const params = new URLSearchParams({ space, q: query });
    return this.request(`/wiki?${params}`, wikiSummarySchema.array());
  }

  status() {
    return this.request("/status", statusSchema);
  }

  importWiki() {
    return this.request("/wiki/import", z.object({
      imported: z.number().int().nonnegative(),
      unchanged: z.number().int().nonnegative(),
    }), { method: "POST", body: "{}" });
  }

  wiki(id: string) {
    return this.request(`/wiki/${encodeURIComponent(id)}`, wikiDetailSchema);
  }

  versions(id: string) {
    return this.request(`/wiki/${encodeURIComponent(id)}/versions`, wikiVersionSchema.array());
  }

  approve(id: string, versionId: string, expectedVersion: number) {
    return this.request(`/wiki/${encodeURIComponent(id)}/approve`, wikiDetailSchema, {
      method: "POST", body: JSON.stringify({ version_id: versionId, expected_version: expectedVersion }),
    });
  }

  rollback(id: string, versionId: string, expectedVersion: number) {
    return this.request(`/wiki/${encodeURIComponent(id)}/rollback`, wikiDetailSchema, {
      method: "POST", body: JSON.stringify({ version_id: versionId, expected_version: expectedVersion }),
    });
  }

  propose(id: string, instructions: string) {
    return this.request(`/wiki/${encodeURIComponent(id)}/propose`, runSchema, {
      method: "POST", body: JSON.stringify({ instructions }),
    });
  }

  evidence(id: string) {
    return this.request(`/evidence/${encodeURIComponent(id)}`, evidenceDetailSchema);
  }

  ask(question: Question) {
    return this.request("/agent/ask", answerSchema, {
      method: "POST", body: JSON.stringify(question),
    });
  }

  run(id: string) {
    return this.request(`/agent/runs/${encodeURIComponent(id)}`, runSchema);
  }

  runs(entryId: string) {
    return this.request(`/agent/runs?${new URLSearchParams({ entry_id: entryId })}`, runSchema.array());
  }

  retryRun(id: string) {
    return this.request(`/agent/runs/${encodeURIComponent(id)}/retry`, runSchema, {
      method: "POST", body: "{}",
    });
  }

  journals() {
    return this.request("/journal", journalSchema.array());
  }

  submitJournal(input: JournalInput) {
    return this.request("/journal", journalSchema, {
      method: "POST",
      body: JSON.stringify(journalInputSchema.parse(input)),
    });
  }

  preview(question: Question) {
    return this.request("/plans/preview", previewSchema, {
      method: "POST", body: JSON.stringify(question),
    });
  }

  adopt(previewId: string, editedContent: string | null) {
    return this.request("/plans/adopt", planSchema, {
      method: "POST", body: JSON.stringify({ preview_id: previewId, edited_content: editedContent }),
    });
  }

  plans() {
    return this.request("/plans", planSchema.array());
  }

  plan(id: number) {
    return this.request(`/plans/${encodeURIComponent(id)}`, planSchema);
  }

  editPlan(id: number, edits: PlanEdit) {
    return this.request(`/plans/${encodeURIComponent(id)}`, planSchema, {
      method: "PATCH",
      body: JSON.stringify({
        ...(edits.title !== undefined ? { title: edits.title } : {}),
        ...(edits.edited_content !== undefined ? { edited_content: edits.edited_content } : {}),
        ...(edits.drills !== undefined ? {
          drills: edits.drills.map(({ id: drillId, name, description }) => ({
            id: drillId,
            ...(name !== undefined ? { name } : {}),
            ...(description !== undefined ? { description } : {}),
          })),
        } : {}),
      }),
    });
  }
}
