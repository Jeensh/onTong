"""Factory for creating storage providers based on configuration."""

from pathlib import Path

from backend.core.config import settings
from .base import StorageProvider
from .local_fs import LocalFSAdapter


def create_storage() -> StorageProvider:
    """Create a storage provider based on STORAGE_BACKEND setting.

    - "local": LocalFSAdapter using wiki_dir (default)
    - "nas": NASBackend using nas_wiki_dir (NFS/SMB mounted path)
    """
    backend = settings.storage_backend.lower()

    if backend == "nas":
        from .nas_backend import NASBackend
        nas_path = Path(settings.nas_wiki_dir)
        if not settings.nas_wiki_dir:
            raise ValueError("STORAGE_BACKEND=nas requires NAS_WIKI_DIR to be set")
        return NASBackend(wiki_dir=nas_path)

    # Default: local filesystem
    return LocalFSAdapter(wiki_dir=settings.wiki_dir)
