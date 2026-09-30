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
