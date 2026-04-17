# Wiki Image Management System Design

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Provide content-hash dedup for images, an annotation editor, and admin-only image management — all designed for 100K+ document scale.

**Architecture:** Three independent subsystems that share a single Image Registry (in-memory hash index + ref count). Backend changes in `files.py` and a new `image_registry.py`; frontend adds fabric.js canvas editor and admin gallery page.

**Tech Stack:** Python (FastAPI), fabric.js (canvas annotation), React, SHA-256 content hashing, Intersection Observer (lazy load)

---

## 1. Content-Hash Dedup & Image Copy/Paste

### 1.1 Image Registry (`backend/application/image/image_registry.py`)

Single source of truth for all image metadata in `wiki/assets/`.

```
ImageEntry:
  filename: str           # e.g. "f8f8873a4c18.png"
  sha256: str             # full SHA-256 hex of file content
  size_bytes: int         # file size
  width: int              # pixel width (from PIL)
  height: int             # pixel height
  ref_count: int          # number of markdown documents referencing this image
  referenced_by: set[str] # set of document paths, e.g. {"인프라/장애대응.md"}
  source: str | None      # parent filename if this is an annotation derivative
  created_at: datetime
```

**Initialization (server startup):**
1. Scan all files in `wiki/assets/` with image extensions
2. Compute SHA-256 for each, build `hash_to_filename: dict[str, str]`
3. Scan all `*.md` files in wiki dir, extract `![...](assets/...)` references
4. Populate `ref_count` and `referenced_by` for each entry
5. Read `.meta.json` sidecars for `source` field (annotation derivatives)

**Event-driven updates (runtime):**
- `file_saved` event → parse new content for image refs, diff against previous refs, update ref_count (+1/-1)
- `file_deleted` event → decrement ref_count for all images referenced by deleted doc
- `image_uploaded` event → add new entry to registry
- `image_deleted` event → remove entry from registry

Hook into existing `backend/infrastructure/events/event_bus.py`.

### 1.2 Upload Dedup (`backend/api/files.py:upload_image`)

Modified upload flow:

```
POST /api/files/upload/image
  1. Read file bytes, compute SHA-256
  2. Check image_registry.hash_to_filename[sha256]
     → exists: return {"path": f"assets/{existing_filename}", "deduplicated": true}
     → not exists:
        a. filename = f"{sha256[:12]}.{ext}"
        b. Write to wiki/assets/{filename}
        c. Register in image_registry
        d. Trigger image processing (OCR/Vision via existing pipeline)
        e. Return {"path": f"assets/{filename}", "deduplicated": false}
```

No changes to existing file serving (`GET /api/files/{path}`).

### 1.3 Editor Image Copy (`frontend/src/lib/tiptap/`)

**Context menu** (Tiptap extension):
- Right-click on image node → custom context menu with "이미지 복사" option
- Click handler: fetch the image blob from `/api/files/{src}`, write to clipboard via `navigator.clipboard.write([new ClipboardItem({"image/png": blob})])`

**Keyboard shortcut**:
- When an image node is selected (Tiptap `NodeSelection`), Ctrl+C / Cmd+C copies the image blob to clipboard (same mechanism as context menu)

**Paste behavior** (existing `pasteHandler.ts`):
- No change needed. Pasting the blob calls `uploadImage()` → server returns existing path via hash dedup → editor inserts `![](assets/{same_file})`.

### 1.4 Image Reference Tracking on Document Save

In `backend/application/wiki/wiki_service.py`, within the existing save flow:

```python
# After writing file to disk, before background indexing:
old_refs = image_registry.get_refs_for_doc(file_path)
new_refs = _extract_image_refs(new_content)  # regex: ![...](assets/...)

added = new_refs - old_refs
removed = old_refs - new_refs

for img in added:
    image_registry.increment_ref(img, file_path)
for img in removed:
    image_registry.decrement_ref(img, file_path)
```

On file delete: `image_registry.remove_all_refs_for_doc(file_path)`.

---

## 2. Image Viewer & Annotation Editor

### 2.1 Viewer Modal (`frontend/src/components/editors/ImageViewerModal.tsx`)

**Trigger:** Click on any image in the Tiptap editor → opens fullscreen overlay modal.

**Layout:** Three-panel fullscreen overlay
- **Left toolbar** (44px wide): Tool selection — rectangle, ellipse, arrow, text label, color picker, zoom in/out
- **Center canvas**: fabric.js canvas rendering the original image with annotation objects on top
- **Right info panel** (200px wide): Image metadata display
  - Filename, dimensions, file size
  - Reference count and list of referencing documents
  - OCR text preview (from sidecar `.meta.json`)
  - "원본 보기" link if this is an annotation derivative

**View-only mode (default):** Canvas shows the image at fit-to-screen size. Mouse wheel zooms, drag pans. No annotation tools active.

**Edit mode:** Click "편집" button → toolbar tools become active. User draws annotations on the canvas.

### 2.2 Annotation Save Flow

When user clicks "새 이미지로 저장":

1. **Client-side:** fabric.js exports canvas as PNG blob (original + annotations flattened)
2. **Upload:** `POST /api/files/upload/image` with the blob — server computes hash, stores as new file
3. **OCR choice dialog** appears with two options:
   - "원본 OCR 상속" → server copies `ocr_text` from source sidecar, sets `source: "{original_filename}"` in new sidecar
   - "새로 OCR 처리" → server runs Tesseract/Vision pipeline on the new image, sets `source: "{original_filename}"` in new sidecar
4. **Insert:** Editor replaces the current image node's `src` with the new annotated image path
5. **Ref count update:** Original image ref_count -1 (if replaced in this doc), new image ref_count +1. Happens automatically on document save.

### 2.3 Sidecar Extension (`backend/application/image/models.py`)

Add `source` field to `ImageAnalysis`:

```python
@dataclass
class ImageAnalysis:
    ocr_text: str
    description: str
    provider: str
    ocr_engine: str
    processed_at: datetime
    source: str = ""  # parent image filename if annotation derivative
```

New endpoint for OCR inheritance:

```
POST /api/files/assets/{filename}/inherit-ocr
Body: {"source_filename": "abc123.png"}
→ Copies ocr_text + description from source sidecar to target sidecar
→ Sets source field
```

### 2.4 Canvas Library

**fabric.js** (MIT license, ~300KB gzipped):
- Built-in shape primitives: Rect, Ellipse, Line (for arrows), IText
- Canvas zoom/pan support
- Export to PNG/SVG
- No additional dependencies needed

Install: `npm install fabric`

---

## 3. Admin Image Management Page

### 3.1 Backend API Extensions (`backend/api/files.py`)

**New endpoints (all `require_admin`):**

```
GET /api/files/assets/stats
→ {"total": 47, "unused": 5, "total_bytes": 13020160, "derivative_count": 3}

GET /api/files/assets?page=1&size=50&filter=all|used|unused|derivative&search=filename
→ {
    "items": [ImageAssetDTO, ...],  # 50 items max
    "total": 47,
    "page": 1,
    "pages": 1
  }

ImageAssetDTO:
  filename: str
  size_bytes: int
  width: int
  height: int
  ref_count: int
  referenced_by: list[str]  # document paths
  source: str | None         # parent filename
  derivatives: list[str]     # child filenames
  has_ocr: bool
  created_at: str

DELETE /api/files/assets/{filename}
→ Only if ref_count == 0. Returns 409 if still referenced.
→ Also deletes .meta.json sidecar.
→ Removes from image_registry.

POST /api/files/assets/bulk-delete
Body: {"filter": "unused"}  # deletes ALL ref_count==0 images
→ {"deleted": 5, "freed_bytes": 234567}
→ Returns count + freed space.
```

**Existing endpoint changes:**
- `DELETE /api/files/assets/unused` → add `require_admin` dependency
- `GET /api/files/assets/unused` → add `require_admin` dependency

### 3.2 Frontend Page (`frontend/src/components/editors/ImageManagementPage.tsx`)

**Route:** Accessible from sidebar navigation, visible only to admin users (`useAuth().isAdmin`).

**Layout:**
- **Top bar:** Stats badges (total, unused, total size) + search input + filter dropdown
- **Gallery grid:** 4-column responsive grid with thumbnail cards
  - Each card: thumbnail (lazy-loaded via Intersection Observer), filename, size, ref_count badge
  - Color-coded borders: green (used), orange (unused), purple (derivative)
  - Checkbox on unused images for selection
- **Bottom action bar:** Selection count + "전체 미사용 선택" + "선택 삭제" buttons
- **Server-side pagination:** Page navigation at bottom, 50 items per page

**Thumbnail lazy loading:**
- Cards render a placeholder until they enter the viewport
- Intersection Observer triggers `<img src="/api/files/assets/{filename}">` load
- Prevents loading hundreds of images at once

**Bulk delete flow:**
1. "미사용 전체 삭제" button → confirmation dialog: "미사용 이미지 N개 (X MB) 를 삭제하시겠습니까?"
2. Confirm → `POST /api/files/assets/bulk-delete {filter: "unused"}`
3. Server deletes all ref_count==0 images, returns count
4. Gallery refreshes

**Individual image detail:**
- Click a card → detail modal showing: full-size preview, all referencing documents (clickable links), OCR text, derivative chain (source → derivatives), created date
- If unused: delete button in modal

### 3.3 Access Control

**Backend:**
- All `/api/files/assets/*` management endpoints: `Depends(require_admin)`
- `GET /api/files/{path}` (serving images): no change, all users can view
- `POST /api/files/upload/image`: no change, all users can upload

**Frontend:**
- Image Management page: only rendered in navigation when `user.roles.includes("admin")`
- Existing TreeNav `UnusedImagesPanel`: add admin check, hide for non-admin users

---

## 4. Data Flow Summary

```
User pastes image in editor
  → uploadImage() → POST /api/files/upload/image
  → Server: SHA-256 check → dedup or store new
  → Response: {path, deduplicated}
  → Editor inserts ![](assets/{path})

User saves document
  → wiki_service.save_file()
  → Extract image refs from content
  → Diff against previous refs
  → Update image_registry ref_counts
  → Trigger background indexing (existing)

User clicks image in editor
  → ImageViewerModal opens (fullscreen)
  → View mode: zoom/pan, see info
  → Edit mode: annotate with fabric.js
  → Save: export PNG → upload as new file → OCR choice → insert

Admin opens Image Management
  → GET /api/files/assets/stats (top bar)
  → GET /api/files/assets?page=1&size=50 (gallery)
  → Filter/search → server-side query
  → Delete unused → bulk-delete endpoint
```

---

## 5. File Changes Summary

### Backend (new files)
- `backend/application/image/image_registry.py` — ImageEntry, ImageRegistry class

### Backend (modified files)
- `backend/api/files.py` — hash dedup on upload, new admin endpoints, pagination
- `backend/application/image/models.py` — add `source` field to ImageAnalysis
- `backend/application/wiki/wiki_service.py` — ref tracking on save/delete
- `backend/main.py` — initialize ImageRegistry, register event handlers

### Frontend (new files)
- `frontend/src/components/editors/ImageViewerModal.tsx` — fullscreen viewer + annotation editor
- `frontend/src/components/editors/ImageManagementPage.tsx` — admin gallery page

### Frontend (modified files)
- `frontend/src/lib/tiptap/pasteHandler.ts` — image copy context menu + keyboard shortcut
- `frontend/src/components/editors/MarkdownEditor.tsx` — click-to-open viewer modal
- `frontend/src/app/page.tsx` — add Image Management route (admin only)
- `frontend/src/components/TreeNav.tsx` — admin gate on UnusedImagesPanel
- `frontend/package.json` — add `fabric` dependency
