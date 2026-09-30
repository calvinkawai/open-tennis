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
