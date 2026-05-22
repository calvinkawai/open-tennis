import argparse
import sys

from app.services.generation import PlanGenerationService
from app.services.rendering import render_training_plan
from app.services.vector import RetrievedContext


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Preview a Gemini-generated tennis training plan."
    )
    parser.add_argument("query", help="User training goal, e.g. 'My forehand is weak'")
    parser.add_argument(
        "--show-context",
        action="store_true",
        help="Print retrieved Chroma chunks before the generated plan.",
    )
    args = parser.parse_args(argv)

    try:
        preview = PlanGenerationService().preview_plan_with_context(args.query)
    except Exception as exc:
        print(f"Failed to generate training plan: {exc}", file=sys.stderr)
        return 1

    if args.show_context:
        print(_render_contexts(preview.contexts))

    print(
        render_training_plan(
            title=preview.plan.title,
            focus_area=preview.plan.focus_area,
            raw_ai_content=preview.plan.raw_ai_content,
            drills=preview.plan.drills,
        )
    )
    return 0


def _render_contexts(contexts: list[RetrievedContext]) -> str:
    lines = ["## Retrieved Context", ""]
    for index, context in enumerate(contexts, start=1):
        title = context.segment_title or context.tutorial_title or "Untitled chunk"
        chunk_type = context.chunk_type or "unknown"
        score = _format_score(context.score)
        rerank_score = _format_score(context.rerank_score)
        lines.append(
            f"{index}. [{chunk_type}] {title} "
            f"(distance={score}, rerank={rerank_score})"
        )
        if context.key_coaching_cue:
            lines.append(f"   cue: {context.key_coaching_cue}")
        if context.visual_focus:
            lines.append(f"   visual: {context.visual_focus}")
    lines.append("")
    return "\n".join(lines)


def _format_score(score: float | None) -> str:
    return "n/a" if score is None else f"{score:.4f}"


if __name__ == "__main__":
    raise SystemExit(main())
