import argparse
import re
import sys
from collections.abc import Callable
from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from app.core.config import BACKEND_DIR, Settings, get_settings


Invoker = Callable[[str, str], str]


SYSTEM_PROMPT = (
    "You are a tennis-coaching content analyst. "
    "You convert tennis instruction video transcripts into a structured "
    "markdown tutorial in our exact schema. "
    "Coaching voice. No filler. No unsupported claims."
)


USER_PROMPT_TEMPLATE = """Analyze this tennis instruction video. Focus only on the core technique taught. Ignore intro, ads, jokes, and filler. Do not invent details.

Tutorial title: {title}

Transcript:
\"\"\"
{transcript}
\"\"\"

Produce THREE markdown sections.

## 1. Video Summary

**Technical Detail:** Summarize the technique in concise bullet points using `*   ` (asterisk + three spaces) markers.

## 2. Segments

For each topic-based segment use the EXACT format below. Number the segments starting at 1.

**Segment N: <Title>**
1-2 sentence technical summary.
*   Key coaching cue: "<quote if exact, paraphrase only if not>"
*   Visual focus: what to watch in body, racket, or ball.

## 3. Cartoon Card (4 Steps)

For each step use this exact format. Always produce exactly 4 steps.

**Step N: <Title>**
One imperative sentence, 15 words or fewer.
*   Visual: body position, racket, ball, motion arrows, with one common-error ✗ mark.

---
Output only the three sections. No preamble, no closing summary.
Markdown only. Coaching voice. No filler. No unsupported claims."""


_SECTION_1_RE = re.compile(r"(?im)^##\s*1\.\s*Video Summary\b")
_SECTION_2_RE = re.compile(r"(?im)^##\s*2\.\s*Segments\b")
_SEGMENT_RE = re.compile(r"(?im)^\*\*Segment\s+\d+:")
_YOUTUBE_ID_RE = re.compile(r"(?:v=|youtu\.be/|/embed/|/v/)([A-Za-z0-9_-]{11})")
_FILENAME_STRIP_RE = re.compile(r"[^A-Za-z0-9 .\-_]+")
_MULTI_SPACE_RE = re.compile(r" {2,}")


def build_extractor_prompt(title: str, transcript: str) -> tuple[str, str]:
    """Return (system_prompt, user_prompt) for the extractor LLM call."""

    user_prompt = USER_PROMPT_TEMPLATE.format(title=title, transcript=transcript)
    return SYSTEM_PROMPT, user_prompt


def sanity_check_markdown(markdown: str) -> list[str]:
    """Return a list of warnings (empty if everything looks parseable)."""

    warnings: list[str] = []
    if not _SECTION_1_RE.search(markdown):
        warnings.append("missing '## 1. Video Summary' header")
    if not _SECTION_2_RE.search(markdown):
        warnings.append("missing '## 2. Segments' header")
    if not _SEGMENT_RE.search(markdown):
        warnings.append("no '**Segment N: ...**' lines found")
    return warnings


def extract_to_markdown(
    transcript: str,
    title: str,
    invoker: Invoker,
) -> str:
    """Pure dispatch: assemble prompt, call invoker, return raw markdown."""

    system_prompt, user_prompt = build_extractor_prompt(title, transcript)
    return invoker(system_prompt, user_prompt)


def fetch_transcript_from_youtube(url: str) -> str:
    """Resolve a YouTube URL to a flat-text transcript."""

    from youtube_transcript_api import YouTubeTranscriptApi  # local import keeps the dep optional for tests

    video_id = _extract_video_id(url)
    if hasattr(YouTubeTranscriptApi, "get_transcript"):
        pieces = YouTubeTranscriptApi.get_transcript(video_id)
    else:
        pieces = YouTubeTranscriptApi().fetch(video_id)
    return " ".join(_transcript_piece_text(piece) for piece in pieces)


def _transcript_piece_text(piece: object) -> str:
    if isinstance(piece, dict):
        return str(piece["text"])
    return str(getattr(piece, "text"))


def read_transcript_file(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def build_gemini_invoker(settings: Settings | None = None) -> Invoker:
    """Wire a real Gemini call as an extractor Invoker."""

    settings = settings or get_settings()
    model = ChatGoogleGenerativeAI(
        model=settings.gemini_model,
        google_api_key=settings.google_genai_api_key,
        temperature=0.3,
    )

    def _invoke(system_prompt: str, user_prompt: str) -> str:
        response = model.invoke(
            [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt),
            ]
        )
        content = response.content
        if isinstance(content, list):
            return "\n".join(str(part) for part in content)
        return str(content)

    return _invoke


def safe_filename(title: str) -> str:
    cleaned = _FILENAME_STRIP_RE.sub("", title).strip()
    return _MULTI_SPACE_RE.sub(" ", cleaned)


def _extract_video_id(url: str) -> str:
    match = _YOUTUBE_ID_RE.search(url)
    if not match:
        raise ValueError(f"Could not extract YouTube video id from URL: {url}")
    return match.group(1)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Extract a structured tennis tutorial markdown from a YouTube "
            "URL or a local transcript file."
        )
    )
    parser.add_argument("--youtube-url", help="YouTube video URL to fetch transcript from.")
    parser.add_argument(
        "--transcript-file",
        type=Path,
        help="Path to a local transcript .txt file (used when --youtube-url is omitted).",
    )
    parser.add_argument("--title", required=True, help="Tutorial title; also the output filename stem.")
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=BACKEND_DIR / "data" / "tutorial",
        help="Output directory (default: backend/data/tutorial/).",
    )
    args = parser.parse_args(argv)

    if not args.youtube_url and not args.transcript_file:
        parser.error("Provide either --youtube-url or --transcript-file")

    if args.youtube_url:
        try:
            transcript = fetch_transcript_from_youtube(args.youtube_url)
        except Exception as exc:
            print(
                f"Failed to fetch YouTube transcript ({type(exc).__name__}: {exc}).\n"
                f"Fall back to --transcript-file with a local copy.",
                file=sys.stderr,
            )
            return 2
    else:
        transcript = read_transcript_file(args.transcript_file)

    invoker = build_gemini_invoker()
    markdown = extract_to_markdown(transcript, args.title, invoker)

    for warning in sanity_check_markdown(markdown):
        print(f"WARNING: {warning}", file=sys.stderr)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    out_path = args.out_dir / f"{safe_filename(args.title)}.md"
    out_path.write_text(markdown, encoding="utf-8")
    print(f"Wrote {out_path}", file=sys.stderr)
    print("Review the file before running embed_markdowns.py --reset.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
