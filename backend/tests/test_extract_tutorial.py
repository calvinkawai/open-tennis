import pytest

from scripts.extract_tutorial import (
    _extract_video_id,
    build_extractor_prompt,
    extract_to_markdown,
    fetch_transcript_from_youtube,
    safe_filename,
    sanity_check_markdown,
)


FAKE_MARKDOWN = """## 1. Video Summary

**Technical Detail:**
*   Bullet one
*   Bullet two

## 2. Segments

**Segment 1: First Title**
First sentence summary.
*   Key coaching cue: "do the thing"
*   Visual focus: watch the racket head

## 3. Cartoon Card (4 Steps)

**Step 1: Grip**
Hold the grip firmly.
*   Visual: hand on handle. ✗ loose fingers.
"""


def test_build_extractor_prompt_includes_title_and_transcript():
    system, user = build_extractor_prompt("My Title", "the transcript text")
    assert "tennis" in system.lower()
    assert "My Title" in user
    assert "the transcript text" in user
    assert "## 1. Video Summary" in user
    assert "## 2. Segments" in user
    assert "## 3. Cartoon Card" in user


def test_sanity_check_markdown_passes_on_valid_input():
    assert sanity_check_markdown(FAKE_MARKDOWN) == []


def test_sanity_check_markdown_flags_missing_sections():
    bad = "## Random heading\nNo content"
    warnings = sanity_check_markdown(bad)
    assert any("Video Summary" in w for w in warnings)
    assert any("Segments" in w for w in warnings)
    assert any("Segment" in w for w in warnings)


def test_extract_to_markdown_uses_invoker_and_returns_its_output():
    captured: dict = {}

    def fake_invoker(system: str, user: str) -> str:
        captured["system"] = system
        captured["user"] = user
        return FAKE_MARKDOWN

    result = extract_to_markdown("transcript here", "Sample Title", fake_invoker)

    assert result == FAKE_MARKDOWN
    assert "Sample Title" in captured["user"]
    assert "transcript here" in captured["user"]


def test_safe_filename_strips_problematic_chars():
    assert safe_filename("Backhand: 5 Steps").startswith("Backhand")
    assert ":" not in safe_filename("Backhand: 5 Steps")
    assert "/" not in safe_filename("Hit Your Forehand / Topspin!")
    assert safe_filename("   spaces   ") == "spaces"


def test_extract_video_id_handles_common_url_shapes():
    assert (
        _extract_video_id("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        == "dQw4w9WgXcQ"
    )
    assert _extract_video_id("https://youtu.be/dQw4w9WgXcQ") == "dQw4w9WgXcQ"
    assert (
        _extract_video_id("https://youtube.com/embed/dQw4w9WgXcQ")
        == "dQw4w9WgXcQ"
    )


def test_extract_video_id_raises_on_bad_url():
    with pytest.raises(ValueError):
        _extract_video_id("https://example.com/no-id-here")


def test_fetch_transcript_from_youtube_supports_instance_api(monkeypatch):
    class FakeSnippet:
        def __init__(self, text: str) -> None:
            self.text = text

    class FakeApi:
        def fetch(self, video_id: str):
            assert video_id == "dQw4w9WgXcQ"
            return [FakeSnippet("first"), FakeSnippet("second")]

    monkeypatch.setattr("youtube_transcript_api.YouTubeTranscriptApi", FakeApi)

    assert (
        fetch_transcript_from_youtube("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        == "first second"
    )


def test_extracted_markdown_parses_via_embed_script(tmp_path):
    """End-to-end format compatibility: stubbed extractor output must be
    parseable by load_tutorial_chunks() with a technical_detail chunk and
    at least one segment chunk."""

    from scripts.embed_markdowns import load_tutorial_chunks

    (tmp_path / "Sample Tutorial.md").write_text(FAKE_MARKDOWN, encoding="utf-8")

    chunks = load_tutorial_chunks(tmp_path)

    assert len(chunks) >= 2
    chunk_types = {chunk.metadata["chunk_type"] for chunk in chunks}
    assert "technical_detail" in chunk_types
    assert "segment" in chunk_types
