import argparse
import sys

from app.core.config import get_settings
from app.services.conversation import ConversationService, TurnResult
from app.services.rendering import render_training_plan


def _read_user_reply() -> str:
    while True:
        try:
            line = input("> ").strip()
        except EOFError:
            print("\n(EOF — aborting)", file=sys.stderr)
            raise SystemExit(2)
        if line:
            return line
        print("(empty reply — please type something)")


def _print_question(turn: TurnResult) -> None:
    label = f"Q{turn.question_number} of {turn.max_questions}"
    print(f"\n[{label}] {turn.question}")


def _print_plan(turn: TurnResult) -> None:
    plan = turn.plan
    if plan is None:
        print("(error: plan_ready turn returned no plan)", file=sys.stderr)
        return
    print("\n=== Plan ===")
    print(
        render_training_plan(
            title=plan.title,
            focus_area=plan.focus_area,
            raw_ai_content=plan.raw_ai_content,
            drills=plan.drills,
        )
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run an interactive clarifying-conversation tennis-plan generation "
            "session against the real Gemini + Chroma backend."
        )
    )
    parser.add_argument(
        "initial_query",
        nargs="?",
        help=(
            "Optional initial query. If omitted, you'll be prompted for one. "
            "Example: 'My forehand is weak'."
        ),
    )
    args = parser.parse_args(argv)

    initial_query = args.initial_query
    if initial_query is None:
        print("Describe what you want help with:")
        initial_query = _read_user_reply()

    settings = get_settings()
    service = ConversationService(
        max_turns=settings.conversation_max_turns,
        light_k=settings.reflection_light_retrieval_k,
    )

    try:
        state, turn = service.start(initial_query)
    except Exception as exc:
        print(f"Failed to start conversation: {exc}", file=sys.stderr)
        return 1

    while turn.status == "needs_answer":
        _print_question(turn)
        reply = _read_user_reply()
        try:
            state, turn = service.reply(state, reply)
        except Exception as exc:
            print(f"Failed to continue conversation: {exc}", file=sys.stderr)
            return 1

    if turn.status == "plan_ready":
        _print_plan(turn)
        return 0

    print(f"Unexpected turn status: {turn.status}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
