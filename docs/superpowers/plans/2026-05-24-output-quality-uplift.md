# Output Quality Uplift Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade both LLM calls to `gemini-2.5-flash` and add tooling that lets the user (a) prove the upgrade is better, and (b) extend the tutorial corpus beyond forehand by extracting structured tutorial markdown from YouTube transcripts.

**Architecture:** Two independent workstreams, both pure-backend, plus a manual validation hop. Workstream A is a one-line default change in `app/core/config.py` plus a one-shot comparison utility script. Workstream B is a new extractor script (`scripts/extract_tutorial.py`) that mirrors the pattern already used in `app/services/reflection.py`: an `Invoker = Callable[[str, str], str]` indirection so the LLM call is trivially stubbable in tests. Both Workstreams reuse the existing `ConversationService` / `embed_markdowns.py` without modification.

**Tech Stack:** Python 3.12, FastAPI/Pydantic, LangChain + `langchain-google-genai` (Gemini), ChromaDB, pytest, conda env `opentennis` (interpreter: `/Users/gluo/miniconda3/envs/opentennis/bin/python`).

**Spec:** `docs/superpowers/specs/2026-05-24-output-quality-uplift-design.md`

**Working directory for all commands:** `/Users/gluo/Desktop/open-tennis/backend`

---

## Workstream A — Model Upgrade

### Task A1: Switch default Gemini model to `gemini-2.5-flash`

**Goal:** Make the stronger model the new production default for both the reflection call and the plan-generation call, while leaving the env-var override intact so any user can roll back instantly by setting `GEMINI_MODEL=gemini-2.5-flash-lite`.

**Files:**
- Modify: `backend/app/core/config.py:16-18`
- Modify: `backend/.env.example` (line containing `GEMINI_MODEL=`)

- [ ] **Step 1: Update the default in `config.py`**

  In `backend/app/core/config.py`, change:

  ```python
  gemini_model: str = Field(
      default="gemini-2.5-flash-lite", validation_alias="GEMINI_MODEL"
  )
  ```

  to:

  ```python
  gemini_model: str = Field(
      default="gemini-2.5-flash", validation_alias="GEMINI_MODEL"
  )
  ```

- [ ] **Step 2: Update `.env.example`**

  In `backend/.env.example`, change:

  ```
  GEMINI_MODEL=gemini-2.5-flash-lite
  ```

  to:

  ```
  GEMINI_MODEL=gemini-2.5-flash
  ```

- [ ] **Step 3: Run the existing test suite to confirm nothing regressed**

  Run from `/Users/gluo/Desktop/open-tennis/backend`:

  ```
  /Users/gluo/miniconda3/envs/opentennis/bin/python -m pytest -q
  ```

  Expected: all 12 existing tests pass. (They stub the invoker, so the model default change should not affect them.)

- [ ] **Step 4: Commit**

  ```
  git add backend/app/core/config.py backend/.env.example
  git commit -m "Default GEMINI_MODEL to gemini-2.5-flash"
  ```

---

### Task A2: Add `scripts/compare_models.py`

**Goal:** Produce a reproducible side-by-side markdown artifact comparing two Gemini models on a fixed bench of five representative queries, so the user can see (not guess) whether the upgrade improved clarifying questions and final plan quality.

**Files:**
- Create: `backend/scripts/compare_models.py`

- [ ] **Step 1: Create the comparison script**

  Create `backend/scripts/compare_models.py` with this exact content:

  ```python
  import argparse
  import os
  import sys
  from datetime import datetime, timezone
  from pathlib import Path

  from app.core.config import BACKEND_DIR, get_settings
  from app.services.conversation import ConversationService


  QUERIES = [
      "My forehand sails long under pressure",
      "I have trouble with my serve toss height",
      "My two-handed backhand feels weak crosscourt",
      "I'm a 3.0 beginner, what should I focus on?",
      "My slice backhand floats too high",
  ]

  AUTO_REPLY = "3.5 NTRP, plays twice a week, partner-based practice"

  DEFAULT_MODELS = ["gemini-2.5-flash-lite", "gemini-2.5-flash"]


  def run_one(model_name: str, query: str) -> dict:
      os.environ["GEMINI_MODEL"] = model_name
      get_settings.cache_clear()
      settings = get_settings()
      service = ConversationService(
          max_turns=settings.conversation_max_turns,
          light_k=settings.reflection_light_retrieval_k,
      )
      questions: list[str] = []
      try:
          state, turn = service.start(query)
          while turn.status == "needs_answer":
              questions.append(turn.question or "")
              state, turn = service.reply(state, AUTO_REPLY)
          if turn.status != "plan_ready" or turn.plan is None:
              return {
                  "error": f"unexpected terminal status {turn.status}",
                  "questions": questions,
              }
          plan = turn.plan
          return {
              "questions": questions,
              "plan_title": plan.title,
              "focus_area": plan.focus_area,
              "raw_ai_content": plan.raw_ai_content,
              "drills": [
                  {"name": d.name, "description": d.description}
                  for d in plan.drills
              ],
          }
      except Exception as exc:
          return {
              "error": f"{type(exc).__name__}: {exc}",
              "questions": questions,
          }


  def render_markdown(comparisons: dict) -> str:
      lines: list[str] = ["# Model Comparison Run", ""]
      for query, by_model in comparisons.items():
          lines.append(f'## Query: "{query}"')
          for model_name, result in by_model.items():
              lines.append("")
              lines.append(f"### {model_name}")
              if "error" in result:
                  lines.append(f"- ERROR: {result['error']}")
                  for i, q in enumerate(result.get("questions", []), start=1):
                      lines.append(f"- Q{i}: {q}")
                  continue
              for i, q in enumerate(result["questions"], start=1):
                  lines.append(f"- Q{i}: {q}")
              lines.append(f"- Plan title: {result['plan_title']}")
              lines.append(f"- Focus area: {result['focus_area']}")
              lines.append("- raw_ai_content:")
              for line in (result["raw_ai_content"] or "").splitlines():
                  lines.append(f"  {line}")
              lines.append("- Drills:")
              for j, d in enumerate(result["drills"], start=1):
                  lines.append(f"  {j}. {d['name']}: {d['description']}")
          lines.append("")
      return "\n".join(lines)


  def main(argv: list[str] | None = None) -> int:
      parser = argparse.ArgumentParser(
          description=(
              "Run a fixed bench of tennis queries against two Gemini models "
              "and emit a side-by-side markdown report."
          )
      )
      parser.add_argument(
          "--models",
          default=",".join(DEFAULT_MODELS),
          help="Comma-separated list of model names to compare.",
      )
      parser.add_argument(
          "--out",
          default="tmp",
          help="Directory for the output markdown (relative paths resolve under backend/).",
      )
      args = parser.parse_args(argv)

      models = [m.strip() for m in args.models.split(",") if m.strip()]
      out_dir = Path(args.out)
      if not out_dir.is_absolute():
          out_dir = BACKEND_DIR / out_dir
      out_dir.mkdir(parents=True, exist_ok=True)

      comparisons: dict[str, dict[str, dict]] = {}
      for query in QUERIES:
          comparisons[query] = {}
          for model_name in models:
              print(f"[{model_name}] {query!r}", file=sys.stderr)
              comparisons[query][model_name] = run_one(model_name, query)

      markdown = render_markdown(comparisons)
      stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
      out_path = out_dir / f"model_comparison_{stamp}.md"
      out_path.write_text(markdown, encoding="utf-8")
      print(f"\nWrote {out_path}", file=sys.stderr)
      return 0


  if __name__ == "__main__":
      raise SystemExit(main())
  ```

- [ ] **Step 2: Smoke-test with a single query and a single model**

  Run from `/Users/gluo/Desktop/open-tennis/backend`:

  ```
  /Users/gluo/miniconda3/envs/opentennis/bin/python -c "from scripts.compare_models import run_one; import json; print(json.dumps(run_one('gemini-2.5-flash-lite', 'My forehand sails long'), indent=2))"
  ```

  Expected: prints a JSON object with non-empty `plan_title`, `focus_area`, `raw_ai_content`, and `drills`. If there is an `error` field instead, fix it before continuing — usually a missing `GOOGLE_API_KEY` in `backend/.env`.

- [ ] **Step 3: Run the full bench**

  ```
  /Users/gluo/miniconda3/envs/opentennis/bin/python -m scripts.compare_models
  ```

  Expected: ~30 seconds to a few minutes (10 LLM-driven conversations total). Stderr shows progress lines per `(model, query)`. Final stderr line: `Wrote <path>/tmp/model_comparison_<YYYYMMDD-HHMMSS>.md`.

- [ ] **Step 4: Open the output and skim**

  Open `backend/tmp/model_comparison_<timestamp>.md`. Confirm: for at least one query, the `gemini-2.5-flash` block reads more specific or better-structured than the `gemini-2.5-flash-lite` block. If not, the upgrade may not be worth landing — pause and discuss with the user.

- [ ] **Step 5: Commit**

  ```
  git add backend/scripts/compare_models.py
  git commit -m "Add scripts/compare_models.py for side-by-side model bench"
  ```

  Do not commit the generated `backend/tmp/` artifacts. Add `backend/tmp/` to `.gitignore` if not already ignored.

- [ ] **Step 6: Ensure `tmp/` is gitignored**

  Check `.gitignore` for `backend/tmp/` or a matching pattern. If not present, append:

  ```
  backend/tmp/
  ```

  Then:

  ```
  git add .gitignore
  git commit -m "Ignore backend/tmp output dir"
  ```

  (Skip this commit if `tmp/` was already covered.)

---

## Workstream B — Tutorial Extractor

### Task B1: Add `youtube-transcript-api` dependency

**Goal:** Make the YouTube URL input path of the extractor possible without adding a giant scraping dependency. `youtube-transcript-api` is a small library that hits YouTube's transcript endpoints directly.

**Files:**
- Modify: `backend/pyproject.toml` (the `[project] dependencies` array)

- [ ] **Step 1: Add the dependency**

  In `backend/pyproject.toml`, inside the `dependencies = [...]` list (under `[project]`), add a new line:

  ```toml
      "youtube-transcript-api>=0.6",
  ```

  Place it in alphabetical position (after `unstructured>=0.22.28`).

- [ ] **Step 2: Sync the env**

  ```
  cd /Users/gluo/Desktop/open-tennis/backend && /Users/gluo/miniconda3/envs/opentennis/bin/python -m pip install "youtube-transcript-api>=0.6"
  ```

  (`uv sync` is the project's preferred installer per `uv.lock`; if `uv` is available, use it instead: `uv sync`.)

- [ ] **Step 3: Verify import works**

  ```
  /Users/gluo/miniconda3/envs/opentennis/bin/python -c "from youtube_transcript_api import YouTubeTranscriptApi; print('ok')"
  ```

  Expected: prints `ok`.

- [ ] **Step 4: Commit**

  ```
  git add backend/pyproject.toml backend/uv.lock
  git commit -m "Add youtube-transcript-api dependency"
  ```

  (If `uv.lock` did not update because you used `pip` directly, omit it from the commit.)

---

### Task B2: TDD — pure helper tests for the extractor

**Goal:** Lock in the shape of the extractor's pure helper functions (prompt assembly, sanity check, video-id parsing, filename sanitization, and a stubbed-invoker integration test) before the script exists. This ensures the LLM-free portions are correct and that extractor output is parseable by `embed_markdowns.py`.

**Files:**
- Create: `backend/tests/test_extract_tutorial.py`

- [ ] **Step 1: Write the failing test file**

  Create `backend/tests/test_extract_tutorial.py` with this exact content:

  ```python
  import pytest

  from scripts.extract_tutorial import (
      _extract_video_id,
      build_extractor_prompt,
      extract_to_markdown,
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
  ```

- [ ] **Step 2: Run the tests and confirm they fail**

  ```
  cd /Users/gluo/Desktop/open-tennis/backend && /Users/gluo/miniconda3/envs/opentennis/bin/python -m pytest tests/test_extract_tutorial.py -v
  ```

  Expected: every test errors at collection with `ModuleNotFoundError: No module named 'scripts.extract_tutorial'`. This is the failing state we want before writing the implementation.

---

### Task B3: Implement `scripts/extract_tutorial.py`

**Goal:** Create the extractor script. The script defines pure helpers (`build_extractor_prompt`, `sanity_check_markdown`, `extract_to_markdown`, `safe_filename`, `_extract_video_id`), a Gemini invoker builder (`build_gemini_invoker`), transcript resolvers (`fetch_transcript_from_youtube`, `read_transcript_file`), and a `main()` that wires the CLI. Mirrors the `Invoker` pattern from `app/services/reflection.py` so tests can stub the LLM call.

**Files:**
- Create: `backend/scripts/extract_tutorial.py`

- [ ] **Step 1: Create the script**

  Create `backend/scripts/extract_tutorial.py` with this exact content:

  ```python
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
      pieces = YouTubeTranscriptApi.get_transcript(video_id)
      return " ".join(piece["text"] for piece in pieces)


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
          help="Path to a local transcript .txt file (used if --youtube-url is omitted or fails).",
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
  ```

- [ ] **Step 2: Run the extractor test suite**

  ```
  cd /Users/gluo/Desktop/open-tennis/backend && /Users/gluo/miniconda3/envs/opentennis/bin/python -m pytest tests/test_extract_tutorial.py -v
  ```

  Expected: all 8 tests pass.

- [ ] **Step 3: Run the full test suite to confirm no regressions**

  ```
  /Users/gluo/miniconda3/envs/opentennis/bin/python -m pytest -q
  ```

  Expected: previous 12 tests + 8 new extractor tests = 20 passing.

- [ ] **Step 4: Commit**

  ```
  git add backend/scripts/extract_tutorial.py backend/tests/test_extract_tutorial.py
  git commit -m "Add scripts/extract_tutorial.py with pure-helper tests"
  ```

---

### Task B4: Smoke-test the extractor end-to-end with a real transcript

**Goal:** Verify the full pipeline (transcript file → Gemini call → written markdown → embed-script-parseable) works once against a real input. This is a manual confidence check, not an automated test.

**Files:**
- Create (temporary, not committed): `backend/tmp/sample_transcript.txt`

- [ ] **Step 1: Create a short sample transcript**

  Create `backend/tmp/sample_transcript.txt` with any plain-text tennis instruction transcript (paste from a YouTube caption, write 4-6 paragraphs of coaching prose, or grab a tutorial transcript online). Roughly 500-1500 words is enough.

- [ ] **Step 2: Run the extractor**

  ```
  cd /Users/gluo/Desktop/open-tennis/backend && /Users/gluo/miniconda3/envs/opentennis/bin/python -m scripts.extract_tutorial --transcript-file tmp/sample_transcript.txt --title "Sample Tutorial" --out-dir tmp/
  ```

  Expected stderr ends with:

  ```
  Wrote <abs-path>/tmp/Sample Tutorial.md
  Review the file before running embed_markdowns.py --reset.
  ```

  No `WARNING:` lines printed. (If warnings appear, the prompt is producing output the embed script cannot parse — iterate on the prompt or the model and re-run.)

- [ ] **Step 3: Confirm the embed script can ingest it**

  Run the embed script against ONLY the temporary output dir (so we do not pollute the real corpus):

  ```
  /Users/gluo/miniconda3/envs/opentennis/bin/python -m scripts.embed_markdowns --docs-path tmp --database-path tmp/chroma_db_smoke --reset
  ```

  Expected: stdout includes `Successfully indexed <N> section chunk(s) ...` where `N >= 2`.

- [ ] **Step 4: Clean up smoke artifacts**

  ```
  rm -rf backend/tmp/chroma_db_smoke "backend/tmp/Sample Tutorial.md" backend/tmp/sample_transcript.txt
  ```

  (Keep `backend/tmp/` itself for future comparison output.)

- [ ] **Step 5: No commit needed**

  This task produces no source changes. If `.gitignore` already covers `backend/tmp/`, nothing was staged.

---

### Task B5: (Optional, defer) Real YouTube URL smoke test

**Goal:** Verify the `--youtube-url` path actually fetches transcripts. Optional because most uses can fall back to `--transcript-file`; only run this once before you depend on URL fetching.

**Files:** none

- [ ] **Step 1: Pick a public, captioned YouTube tennis video**

  Any short instruction video that has English captions enabled.

- [ ] **Step 2: Run the extractor against the URL**

  ```
  cd /Users/gluo/Desktop/open-tennis/backend && /Users/gluo/miniconda3/envs/opentennis/bin/python -m scripts.extract_tutorial --youtube-url "<URL>" --title "URL Smoke Test" --out-dir tmp/
  ```

  Expected stderr: `Wrote ...`. If you instead see `Failed to fetch YouTube transcript`, either the video has no captions or `youtube-transcript-api` could not reach YouTube. Document the URL and fall back to `--transcript-file`.

- [ ] **Step 3: Clean up**

  ```
  rm -f "backend/tmp/URL Smoke Test.md"
  ```

---

## Content + Validation Hop (Manual — not engineering tasks)

These are NOT automated tasks. They are the user's responsibility once Workstreams A and B have landed. Listed here so the plan is complete.

### Task C1: Source and produce ~12 tutorials

**Goal:** Get the corpus to a state where serve and backhand queries retrieve relevant material.

- [ ] Find ~6 high-quality serve and ~6 high-quality backhand YouTube tutorials.
- [ ] For each: either pass the URL to `extract_tutorial.py` or save the transcript locally first.
- [ ] Run `scripts/extract_tutorial.py --title "..." --transcript-file ... --out-dir backend/data/tutorial/` (or `--youtube-url ...`).
- [ ] Open each generated `.md` file. Read it. Fix any awkward wording, missing details, or hallucinated claims. Keep the schema intact.
- [ ] Commit the reviewed markdowns in topic-batched groups (e.g., one commit per stroke).

### Task C2: Re-embed the expanded corpus

**Goal:** Rebuild Chroma so the new tutorials are retrievable.

- [ ] Run from `backend/`:

  ```
  /Users/gluo/miniconda3/envs/opentennis/bin/python -m scripts.embed_markdowns --reset
  ```

  Expected stdout: `Successfully indexed <N> section chunk(s) ...` where `N` is meaningfully larger than before (was ~60-90 for forehand-only; should jump by 50-100 chunks).

### Task C3: Interactive smoke-test against the new topics

**Goal:** Confirm the system actually produces usable plans for serve and backhand queries.

- [ ] Run `python -m app.cli.chat_plan "I have trouble with my serve toss height"` and walk through the conversation. Confirm: clarifying questions feel relevant, final plan cites serve-specific drills, no forehand content leaks in.
- [ ] Repeat with a backhand query (e.g., `"My two-handed backhand feels weak crosscourt"`).

### Task C4: Final model comparison on the expanded corpus

**Goal:** Capture the cumulative quality delta (model + corpus) in a single artifact for project records.

- [ ] Run from `backend/`:

  ```
  /Users/gluo/miniconda3/envs/opentennis/bin/python -m scripts.compare_models
  ```

  Expected: writes `backend/tmp/model_comparison_<timestamp>.md`. Skim it — the serve and backhand queries should produce on-topic plans for both models, with `gemini-2.5-flash` generally reading sharper.

---

## Self-Review Notes

- **Spec coverage:** Section 1 (scope) → Tasks A1, A2, B1-B5, C1-C4. Section 2 (file changes) → exact paths matched in every task. Section 3 (extractor prompt) → reproduced in Task B3 with the three additions inline. Section 4 (compare_models) → Task A2 contains the full script. Section 5 (testing + risks) → Task B2 covers required tests; Task A1 Step 3 confirms no regression; risks like rate limits and human review are noted in B3 and C1.
- **Out-of-scope items** from the spec (embedding model, `gemini-2.5-pro`, automated LLM eval, golden files, the `_extract_labeled_value` bug) are intentionally absent from the plan.
- **Type consistency:** `Invoker = Callable[[str, str], str]` used identically in `extract_tutorial.py` and the test file. `extract_to_markdown(transcript, title, invoker)` parameter order matches between Task B2 and Task B3.
- **No placeholders:** every code block is complete and runnable. Every shell command includes the absolute interpreter path and expected output.
