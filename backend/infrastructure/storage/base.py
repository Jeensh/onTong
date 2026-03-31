"""Abstract base class for wiki storage providers."""

from abc import ABC, abstractmethod
from dataclasses import dataclass

from backend.core.schemas import DocumentMetadata, WikiFile, WikiTreeNode


@dataclass
class FileMetadataEntry:
    """Lightweight struct: path + parsed frontmatter only (no body content)."""
    path: str
    metadata: DocumentMetadata


class StorageProvider(ABC):
    @abstractmethod
    async def read(self, path: str) -> WikiFile | None:
        ...

    @abstractmethod
    async def write(self, path: str, content: str, user_name: str = "") -> WikiFile:
        ...

    @abstractmethod
    async def delete(self, path: str) -> bool:
        ...

    @abstractmethod
    async def list_tree(self) -> list[WikiTreeNode]:
        ...

    @abstractmethod
    async def list_all_files(self) -> list[WikiFile]:
        ...

    @abstractmethod
    async def exists(self, path: str) -> bool:
        ...

    @abstractmethod
    async def create_folder(self, path: str) -> bool:
        ...

    @abstractmethod
    async def delete_folder(self, path: str) -> bool:
        ...

    @abstractmethod
    async def list_subtree(self, prefix: str) -> list[WikiTreeNode]:
        """List immediate children of a directory (one level only, no recursion)."""
        ...

    async def list_file_paths(self) -> list[str]:
        """List all file paths without reading content (lightweight). Optional override."""
        files = await self.list_all_files()
        return [f.path for f in files]

    async def list_all_metadata(self) -> list[FileMetadataEntry]:
        """List all files with only frontmatter metadata (no body content).

        Much faster than list_all_files() for tag/metadata aggregation.
        Default implementation falls back to list_all_files().
        """
        files = await self.list_all_files()
        return [FileMetadataEntry(path=f.path, metadata=f.metadata) for f in files]

    @abstractmethod
    async def move(self, old_path: str, new_path: str) -> bool:
        """Move or rename a file or folder."""
        ...
