import argparse
import re
import shutil
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_google_genai import GoogleGenerativeAIEmbeddings

from app.core.config import BACKEND_DIR, get_settings


COSINE_COLLECTION_METADATA = {"hnsw:space": "cosine"}


@dataclass(frozen=True)
class TutorialChunk:
    id: str
    content: str
    metadata: dict[str, str | int]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Embed tutorial markdown as section-level Chroma chunks."
    )
    parser.add_argument("--docs-path", default="data/tutorial")
    parser.add_argument("--database-path", default="data/chroma_db")
    parser.add_argument("--reset", action="store_true")
    args = parser.parse_args()

    load_dotenv(BACKEND_DIR / ".env")
    settings = get_settings()
    docs_path = _resolve_backend_path(args.docs_path)
    database_path = _resolve_backend_path(args.database_path)

    chunks = load_tutorial_chunks(docs_path)
    store_tutorial_chunks(chunks, database_path, reset=args.reset)
    return 0


def load_tutorial_chunks(docs_path: Path) -> list[TutorialChunk]:
    if not docs_path.exists():
        raise RuntimeError(f"Tutorial docs path does not exist: {docs_path}")

    chunks: list[TutorialChunk] = []
    for markdown_path in sorted(docs_path.glob("**/*.md")):
        markdown = markdown_path.read_text(encoding="utf-8")
        if not markdown.strip():
            continue
        chunks.extend(_parse_tutorial_file(markdown_path, markdown))
    return chunks


def store_tutorial_chunks(
    chunks: list[TutorialChunk],
    database_path: Path,
    *,
    reset: bool = False,
) -> Chroma:
    if reset and database_path.exists():
        shutil.rmtree(database_path)

    database_path.mkdir(parents=True, exist_ok=True)
    settings = get_settings()
    embeddings = GoogleGenerativeAIEmbeddings(
        model=settings.embedding_model,
        google_api_key=settings.google_genai_api_key,
    )
    vector_db = Chroma(
        collection_name=settings.chroma_collection_name,
        embedding_function=embeddings,
        persist_directory=str(database_path),
        collection_metadata=COSINE_COLLECTION_METADATA,
    )

    if not chunks:
        print("No tutorial chunks found.")
        return vector_db

    for chunk in chunks:
        vector_db.add_documents(
            [Document(page_content=chunk.content, metadata=chunk.metadata)],
            ids=[chunk.id],
        )
    print(
        f"Successfully indexed {len(chunks)} section chunk(s) "
        f"into {database_path} collection '{settings.chroma_collection_name}'."
    )
    return vector_db


def _parse_tutorial_file(markdown_path: Path, markdown: str) -> list[TutorialChunk]:
    title = _tutorial_title(markdown_path)
    clean_markdown = _remove_cartoon_card(markdown)
    chunk_index = 0
    chunks: list[TutorialChunk] = []

    technical_detail = _extract_technical_detail(clean_markdown)
    if technical_detail:
        chunks.append(
            TutorialChunk(
                id=_chunk_id(markdown_path, "technical_detail", chunk_index),
                content=(
                    f"Tutorial topic: {title}\n"
                    "Chunk type: technical detail\n\n"
                    f"{technical_detail}"
                ),
                metadata={
                    "source": _source_path(markdown_path),
                    "tutorial_title": title,
                    "chunk_type": "technical_detail",
                    "segment_title": "",
                    "key_coaching_cue": "",
                    "visual_focus": "",
                    "chunk_index": chunk_index,
                },
            )
        )
        chunk_index += 1

    for segment_title, segment_body in _extract_segments(clean_markdown):
        key_coaching_cue = _extract_labeled_value(segment_body, "Key coaching cue")
        visual_focus = _extract_labeled_value(segment_body, "Visual focus")
        segment_explanation = _remove_segment_labels(segment_body)
        segment_content = "\n".join(
            part
            for part in [
                f"Tutorial topic: {title}",
                "Chunk type: segment",
                f"Segment title: {segment_title}",
                "",
                segment_explanation,
                (
                    f"Key coaching cue: {key_coaching_cue}"
                    if key_coaching_cue
                    else ""
                ),
                f"Visual focus: {visual_focus}" if visual_focus else "",
            ]
            if part != ""
        )
        chunks.append(
            TutorialChunk(
                id=_chunk_id(markdown_path, "segment", chunk_index),
                content=segment_content,
                metadata={
                    "source": _source_path(markdown_path),
                    "tutorial_title": title,
                    "chunk_type": "segment",
                    "segment_title": segment_title,
                    "key_coaching_cue": key_coaching_cue,
                    "visual_focus": visual_focus,
                    "chunk_index": chunk_index,
                },
            )
        )
        chunk_index += 1

    return chunks


def _resolve_backend_path(path: str) -> Path:
    value = Path(path)
    if value.is_absolute():
        return value
    return BACKEND_DIR / value


def _source_path(markdown_path: Path) -> str:
    try:
        return str(markdown_path.resolve().relative_to(BACKEND_DIR))
    except ValueError:
        return str(markdown_path)


def _tutorial_title(markdown_path: Path) -> str:
    title = markdown_path.stem.strip().strip("_")
    title = title.replace(" _ ", " - ")
    title = title.replace("_s ", "'s ")
    title = title.replace("_", "")
    return re.sub(r"\s+", " ", title).strip()


def _remove_cartoon_card(markdown: str) -> str:
    return re.split(r"(?im)^##\s*3\.\s*Cartoon Card\b.*$", markdown, maxsplit=1)[
        0
    ].strip()


def _extract_technical_detail(markdown: str) -> str:
    match = re.search(
        r"(?is)\*\*Technical Detail:\*\*\s*(.*?)(?=^##\s*2\.\s*Segments\b|\Z)",
        markdown,
    )
    if match:
        return match.group(1).strip()
    summary_match = re.search(
        r"(?ims)^##\s*1\.\s*Video Summary\s*(.*?)(?=^##\s*2\.|\Z)",
        markdown,
    )
    return summary_match.group(1).strip() if summary_match else ""


def _extract_segments(markdown: str) -> list[tuple[str, str]]:
    section_match = re.search(
        r"(?ims)^##\s*2\.\s*Segments\s*(.*?)(?=^##\s*\d+\.|\Z)",
        markdown,
    )
    if not section_match:
        return []

    segment_section = section_match.group(1).strip()
    segment_matches = re.finditer(
        r"(?ms)^\*\*([^*\n]+)\*\*\s*\n(.*?)(?=^\*\*[^*\n]+\*\*\s*$|\Z)",
        segment_section,
    )
    return [
        (match.group(1).strip(), match.group(2).strip())
        for match in segment_matches
        if match.group(2).strip()
    ]


def _extract_labeled_value(text: str, label: str) -> str:
    match = re.search(
        rf"(?im)^\s*[-*]\s*\*\*{re.escape(label)}:\*\*\s*(.+)$",
        text,
    )
    return match.group(1).strip() if match else ""


def _remove_segment_labels(text: str) -> str:
    return re.sub(
        r"(?im)^\s*[-*]\s*\*\*(?:Key coaching cue|Visual focus):\*\*.*$",
        "",
        text,
    ).strip()


def _chunk_id(markdown_path: Path, chunk_type: str, chunk_index: int) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", markdown_path.stem.lower()).strip("-")
    return f"{slug}:{chunk_type}:{chunk_index}"


if __name__ == "__main__":
    raise SystemExit(main())
