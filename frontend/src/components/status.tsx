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
