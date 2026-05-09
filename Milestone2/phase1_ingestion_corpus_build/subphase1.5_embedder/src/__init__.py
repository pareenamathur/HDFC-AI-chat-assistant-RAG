"""
Sub-phase 1.5 - Embedder
Vector embedding generation using BAAI/bge-small-en-v1.5 via ChromaDB ONNX runtime.
"""

from .embedder import Embedder, EmbeddedChunk

__all__ = ["Embedder", "EmbeddedChunk"]
