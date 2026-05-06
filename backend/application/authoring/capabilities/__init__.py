"""Authoring AI capabilities — one module per capability.

Capability map (Round 5 Step 13 §2 + §5):
  1  code_extractor   — Sonnet — JPO/Service/Action structure extraction
  2  hypothesis       — Opus   — first entity hypothesis from extracted code
  3  interview        — Sonnet — question generation with placeholders
  4  answer_absorber  — Sonnet — parse free-form domain answers into facets
  5  gap_detector     — Opus   — domain vs code structural mismatch
  6  option_proposer  — Opus   — A/B/C trade-off table with ★ recommendation
  7  pattern_checker  — Sonnet — consistency vs prior entities
  8  naming           — Sonnet — Korean display name + English PascalCase id
  9  archiver         — Sonnet (or templated) — auto archive table/diagram
 10  next_step        — Sonnet — dependency-aware next-step suggestion
"""
