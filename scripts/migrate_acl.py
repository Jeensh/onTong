"""One-time migration: set up initial ACLs for existing folders and reindex with access_scope.

Usage:
    cd /Users/donghae/workspace/ai/onTong
    python scripts/migrate_acl.py

After running, trigger full reindex to populate ChromaDB access_scope:
    curl -X POST http://localhost:8001/api/wiki/reindex
"""
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.core.auth.acl_store import ACLStore
from backend.core.auth.scope import format_scope_for_chroma


async def main():
    acl = ACLStore()
    wiki_dir = Path("wiki")

    if not wiki_dir.exists():
        print(f"Wiki directory not found: {wiki_dir}")
        return

    # 1. Set up top-level shared folder ACLs (readable/writable by all, admin-managed)
    top_folders = [d for d in wiki_dir.iterdir()
                   if d.is_dir() and not d.name.startswith((".", "_", "@"))]
    for folder in sorted(top_folders):
        rel = folder.name + "/"
        existing = acl.get_all().get(rel)
        if not existing:
            print(f"  ACL: {rel} → read=all, write=all, manage=admin")
            acl.set_acl(rel, read=["all"], write=["all"], manage=["admin"], owner="admin")

    # 2. Set up system folder ACLs (_skills, _personas)
    for system_folder in ["_skills/", "_personas/"]:
        existing = acl.get_all().get(system_folder)
        if not existing:
            if (wiki_dir / system_folder.rstrip("/")).exists():
                print(f"  ACL: {system_folder} → read=all, write=all, manage=admin")
                acl.set_acl(system_folder, read=["all"], write=["all"],
                            manage=["admin"], owner="admin")

    # 3. Create personal spaces for dev users
    users_file = Path("data/users.json")
    if users_file.exists():
        data = json.loads(users_file.read_text(encoding="utf-8"))
        for u in data.get("users", []):
            uid = u.get("id", "")
            if uid:
                personal_dir = wiki_dir / f"@{uid}"
                personal_dir.mkdir(exist_ok=True)
                print(f"  Personal space: @{uid}/")

    print("\nMigration complete.")
    print("ACL entries:", len(acl.get_all()))
    print("\nTo populate ChromaDB access_scope, run full reindex:")
    print("  curl -X POST http://localhost:8001/api/wiki/reindex")


if __name__ == "__main__":
    asyncio.run(main())
