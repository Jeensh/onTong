"""Factory for vector database."""

from .chroma import ChromaWrapper, chroma


def get_chroma() -> ChromaWrapper:
    return chroma
