"""NAS-mounted storage adapter for wiki files.

Uses the same LocalFSAdapter implementation since NAS volumes are
typically mounted via NFS/SMB and appear as local filesystem paths.
The only difference is the base path (configurable via NAS_WIKI_DIR).
"""

from pathlib import Path
from .local_fs import LocalFSAdapter


class NASBackend(LocalFSAdapter):
    """NAS storage backend — LocalFSAdapter with a different base path.

    NAS drives mounted via NFS/SMB behave identically to local filesystems.
    This subclass exists to make the intent explicit and allow future
    NAS-specific optimizations (e.g., connection health checks, retry logic).
    """

    def __init__(self, wiki_dir: Path) -> None:
        if not wiki_dir.exists():
            raise FileNotFoundError(
                f"NAS mount path does not exist: {wiki_dir}. "
                f"Ensure the NAS volume is mounted before starting the application."
            )
        super().__init__(wiki_dir=wiki_dir)
