# Concise Plan + Drills Prompt Refinement

**Date:** 2026-05-24
**Status:** Approved — apply inline (no separate implementation plan)
**Parent context:** Follow-up refinement after the `gemini-2.5-flash` model upgrade (see `2026-05-24-output-quality-uplift-design.md`). Empirically, the stronger model produces more verbose plans and drills, so we tighten the prompt.

## Goal

Force the plan-generation LLM call to emit shorter, scannable bullets and drill descriptions that fit the "one practice session, amateur reader" framing.

## Change

Single edit in `backend/app/services/llm.py`, inside `_build_user_prompt`. Three things change:

1. Add a per-bullet word cap and filler-word ban.
2. Add a per-drill word cap.
3. Add a Style anchor block with one example bullet and one example drill at target length.

### Word caps

- **Bullet in `raw_ai_content`:** one sentence, ≤25 words.
- **Drill description:** one sentence, ≤30 words.
- Enforced in the prompt only (soft). Not added to the Pydantic schema, because a hard cap could fail Gemini's structured-output call rather than make it self-shorten.

### Concrete diff (in `_build_user_prompt`)

Replace the existing **Output rules** sub-block:

```
- raw_ai_content must be bullet-point text with 4-6 bullets.
- raw_ai_content must not contain a drills section.
- Put drills only in the drills array.
- raw_ai_content should cover: diagnosis, priority correction, feel cue, what to avoid, success check, and next progression.
- The drills array must include 3-5 progressive drills.
- Include a feel/shadow drill, a controlled ball drill, and a more realistic rally or point-play drill when supported by retrieved_technical_context.
- Each drill description must be one concise sentence with setup, action, dose, and success target.
- If video_url is unknown, use null.
```

with:

```
- raw_ai_content must be bullet-point text with 4-6 bullets.
- Each bullet must be ONE sentence, ≤25 words, no filler words ("really", "essentially", "basically", "in order to").
- raw_ai_content must not contain a drills section. Put drills only in the drills array.
- raw_ai_content should cover: diagnosis, priority correction, feel cue, what to avoid, success check, and next progression.
- The drills array must include 3-5 progressive drills.
- Include a feel/shadow drill, a controlled ball drill, and a more realistic rally or point-play drill when supported by retrieved_technical_context.
- Each drill description must be ONE sentence, ≤30 words, covering setup, action, dose, and success target.
- If video_url is unknown, use null.

Style anchor (match this tone and length):
- Example bullet: "Diagnosis: your forehand sails long because contact is flat and the racket finishes low."
- Example drill: "Stand 4 feet from a wall; brush up low-to-high with self-fed balls for 30 reps; success: 8/10 land inside the service line."
```

## Out of scope

- No change to `SYSTEM_PROMPT` (already says "Do not over-explain").
- No change to the reflection prompt — clarifying questions are unaffected.
- No Pydantic `max_length` constraints.
- No new automated tests — existing tests stub `LLMService`, so prompt text isn't exercised.

## Validation

After applying:

1. Run `chat_plan` CLI against a forehand query and one of the not-yet-covered topics. Skim the output.
2. Confirm: bullets each fit on roughly one terminal line, drill descriptions don't sprawl.
3. If still too long, iterate: add a good/bad example pair, or drop the cap to 20 / 25 words.
