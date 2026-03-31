# Agent Tools Schema (SSOT)

> PydanticAI `@agent.tool` 정의 문서. 프론트엔드/백엔드 인터페이스 불일치 방지를 위한 Single Source of Truth.
> 최종 갱신: 2026-03-26

---

## Tool Definitions

### Template

```
#### tool_name

- **Description**: (what the tool does)
- **Input Schema**:
  ```json
  {
    "param_name": "type — description"
  }
  ```
- **Output Schema**:
  ```json
  {
    "field_name": "type — description"
  }
  ```
- **Side Effects**: (file writes, DB changes, etc.)
- **Error Cases**: (expected failure modes)
```

---

### (Tools will be defined here as they are implemented)

<!-- Example:
#### wiki_search
- **Description**: Search wiki documents by query with optional metadata filter
- **Input Schema**:
  ```json
  {
    "query": "string — search query",
    "n_results": "int — max results (default 5)",
    "where": "object | null — ChromaDB where filter"
  }
  ```
- **Output Schema**:
  ```json
  {
    "results": [{"path": "string", "title": "string", "snippet": "string", "distance": "float"}]
  }
  ```
- **Side Effects**: None (read-only)
- **Error Cases**: ChromaDB disconnected → empty results
-->
