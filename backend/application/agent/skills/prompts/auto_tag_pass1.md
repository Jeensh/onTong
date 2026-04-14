# Auto-Tag Suggestion — Pass 1 (Domain & Process only)

Determine ONLY the domain and process for this document. Tags are decided in a separate pass.

## Available Domains and Processes

{domains_info}

## Document Location Signals (strong hints)

- **File path**: {path}
- **Filename**: {filename}
- **Parent directory**: {parent_dir}

The directory structure encodes domain. A document in `wiki/인프라/` is almost certainly an 인프라-domain document. **Trust path strongly when content is ambiguous.**

## Neighbor Document Domains

These are the domain/process distributions of other documents in the same parent directory:

{neighbor_summary}

## Your Task

Respond with **ONLY** a JSON object (no markdown fences):

```json
{
  "domain": "exactly one domain from the list, or empty",
  "process": "exactly one process under the matched domain, or empty",
  "confidence": 0.85,
  "reasoning": "brief Korean explanation"
}
```

## Rules

- `domain` MUST match exactly or be empty
- `process` MUST be one of the processes under the chosen domain, or empty
- High confidence (0.9+) when path AND content agree
- Return ONLY the JSON
