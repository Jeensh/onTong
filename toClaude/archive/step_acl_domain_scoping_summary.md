# ACL Domain Scoping — Step Summary

**Branch:** `feat/acl-domain-scoping`  
**Date:** 2026-04-13~14  
**Status:** 15 tasks complete, 16 commits, 100 tests passing

## What Was Built

Enterprise-grade ACL (Access Control List) domain-scoping system that transforms the single-pool personal wiki into an enterprise ECM.

### Backend (12 new/modified files)
- **ACL Store v2** (`auth/acl_store.py`) — Default-deny, owner/manage/read/write permissions, folder inheritance, personal space, thread-safe with RLock, file watcher for hot-reload, lazy singleton
- **Group Store** (`auth/group_store.py`) — Department/custom groups, member management, JSON persistence
- **NoOpProvider** (`auth/noop_provider.py`) — Multi-user dev auth via X-User-Id header, users.json, group resolution
- **Access Scope** (`auth/scope.py`) — Materialized access_scope for ChromaDB pre-filtering (`$or` + `$contains`)
- **ChromaDB Integration** — `access_read`/`access_write` pipe-delimited strings in chunk metadata
- **Search Scoping** — wiki_search, RAG agent, conflict detection all filter by user scope
- **Group API** (`api/group.py`) — Full CRUD + ACL reference cleanup on rename/delete
- **ACL API** (`api/acl.py`) — Get/set/delete with manage permission check, acl_changed event
- **Tree API** — Recursive ACL filtering, permission hints, personal space endpoint
- **Event Bus** — Async callback support via `inspect.iscoroutinefunction()`

### Frontend (7 new/modified files)
- **Auth types** (`types/auth.ts`) — User, Group, ACLEntry, AccessInfo, Permission
- **API clients** — `lib/api/acl.ts`, `lib/api/groups.ts`, `lib/api/auth.ts`
- **useAuth hook** — Cached current user + `checkAccess()` helper
- **ContextMenu** — Reusable with viewport position correction
- **ShareDialog** — ACL sharing with group suggestions
- **PropertiesPanel** — Document properties with permission info
- **TreeNav** — Collapsible sections (내 문서/위키/스킬), permission-based menu items, lock/share icons

### Tests (100 total)
- test_acl_v2: 33 (including directory path resolution)
- test_noop_provider: 17
- test_scope: 10
- test_group_api: 25
- test_group_store: 15

### Migration
- `scripts/migrate_acl.py` — Sets up initial ACLs for existing wiki folders + personal spaces

## Key Decisions
- Default-deny (not allow) — safer for enterprise
- Materialized access_scope in ChromaDB — avoids runtime permission checks during vector search
- Group names in scope (not user IDs) — group membership changes don't require ChromaDB re-indexing
- Lazy singleton for ACLStore — no import-time I/O

## Bug Found & Fixed During Verification
- Directory path resolution: Tree nodes pass "ERP" but ACL entries use "ERP/". Added directory form lookup in `_resolve_entry()`.

## E2E Verification Results
- `/api/auth/me` ✓ (returns user with roles/groups)
- `/api/groups` ✓ (CRUD works)
- `/api/acl` ✓ (get all, per-path, set with manage check)
- `/api/wiki/tree` ✓ (ACL-filtered, admin sees all, non-admin sees only permitted)
- `/api/wiki/tree/personal` ✓ (returns @username space)
- Migration script ✓ (sets up 10 ACL entries + personal spaces)
- TypeScript ✓ (0 errors)
