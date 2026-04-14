# Auto-Tag Suggestion — Pass 2 (Tags only)

You already determined the document's domain and process. Now focus **only** on selecting tags.

## Context (already decided)

- **Domain**: {domain}
- **Process**: {process}
- **File path**: {path}

## Domain-frequent Tags (most common in this domain — strongly prefer these)

{domain_tags}

## Neighbor Document Tags (other docs in the same directory)

{neighbor_tags}

## Existing Tag Vocabulary (full list — also reusable)

{existing_tags}

## Few-Shot Examples (this domain)

{few_shot_examples}

## Your Task

Read the document content and select **3 to 7 tags**. Strongly prefer tags from the domain-frequent list and neighbor list. Only invent a new tag if the concept genuinely is not covered.

Respond with **ONLY** a JSON object:

```json
{
  "tags": ["3-7 tags here"],
  "error_codes": ["DG320"],
  "confidence": 0.85,
  "reasoning": "brief Korean explanation, noting which tags came from existing vocabulary"
}
```

## Rules

- 3 to 7 tags
- Reuse > create. If "캐시" exists, do NOT propose "캐싱".
- Korean preferred for new tags
- Return ONLY the JSON, no markdown fences
