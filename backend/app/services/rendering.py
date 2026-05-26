import re
from collections.abc import Iterable
from typing import Any


def render_training_plan(
    title: str,
    focus_area: str,
    raw_ai_content: str,
    drills: Iterable[Any],
) -> str:
    """Render a generated plan into clean human-readable text."""

    lines = [
        f"# {title.strip()}",
        "",
        f"Focus area: {focus_area.strip()}",
        "",
        "## Training Plan",
    ]
    lines.extend(_normalize_plan_lines(raw_ai_content))

    drill_items = list(drills)
    if drill_items:
        lines.extend(["", "## Drills"])
        for index, drill in enumerate(drill_items, start=1):
            name = _get_value(drill, "name")
            description = _get_value(drill, "description")
            video_url = _get_value(drill, "video_url")
            lines.extend(["", f"{index}. {name}", f"   {description}"])
            if video_url:
                lines.append(f"   Video: {video_url}")

    return "\n".join(lines).strip()


def _normalize_plan_lines(raw_ai_content: str) -> list[str]:
    content = _remove_code_fences(raw_ai_content).strip()
    content = _remove_drills_section(content)
    normalized_lines = []

    for line in content.splitlines():
        stripped = line.strip()
        if not stripped or _is_redundant_heading(stripped):
            continue
        normalized_lines.append(_normalize_bullet(stripped))

    return normalized_lines


def _remove_code_fences(content: str) -> str:
    return re.sub(r"(?im)^```(?:markdown|json)?\s*|\s*```$", "", content).strip()


def _remove_drills_section(content: str) -> str:
    return re.split(r"(?im)^#{0,6}\s*drills\s*:?\s*$", content, maxsplit=1)[0].strip()


def _is_redundant_heading(line: str) -> bool:
    lowered = line.lstrip("#").strip().lower()
    return lowered in {"training plan", "plan", "drills"}


def _normalize_bullet(line: str) -> str:
    if re.match(r"^[-*]\s+", line):
        return "- " + re.sub(r"^[-*]\s+", "", line)
    if re.match(r"^\d+[.)]\s+", line):
        return "- " + re.sub(r"^\d+[.)]\s+", "", line)
    return "- " + line


def _get_value(item: Any, field: str) -> Any:
    if isinstance(item, dict):
        return item.get(field)
    return getattr(item, field, None)
