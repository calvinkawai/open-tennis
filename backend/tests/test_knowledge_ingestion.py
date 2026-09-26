from scripts.embed_markdowns import load_tutorial_chunks


def test_list_style_segments_preserve_their_cues_and_visual_focus(tmp_path):
    (tmp_path / "Space.md").write_text(
        """## 1. Video Summary

**Technical Detail:**
* Observe the available space.

## 2. Segments

- **Finding space**
- An explanation of the observation.
- Key coaching cue: Leave space
- Visual focus: Contact point

## 3. Cartoon Card
- This section is not retrieval evidence.
""",
        encoding="utf-8",
    )

    chunks = load_tutorial_chunks(tmp_path)

    assert [chunk.metadata["chunk_type"] for chunk in chunks] == [
        "technical_detail",
        "segment",
    ]
    assert chunks[1].metadata["segment_title"] == "Finding space"
    assert chunks[1].metadata["key_coaching_cue"] == "Leave space"
    assert chunks[1].metadata["visual_focus"] == "Contact point"
    assert "Cartoon" not in chunks[1].content
    assert "Finding space" not in chunks[0].content
