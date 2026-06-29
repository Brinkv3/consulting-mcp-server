"""MCP tool wrappers for the RAG pipeline."""

from __future__ import annotations


def register_rag_tools(mcp, rag_fns: dict, config: dict) -> None:

    chroma_dir = config.get("rag_chroma_dir", "chroma")

    @mcp.tool()
    def rag_query(query: str, n_results: int = 5) -> dict:
        """Single-pass RAG: retrieve relevant chunks and generate a grounded answer with citations.

        Use this for straightforward questions answerable from the indexed knowledge base.
        Returns ranked retrieval results with relevance scores, a generated answer
        with bracket citations, and token usage.
        """
        if "_error" in rag_fns:
            return {"error": f"RAG pipeline unavailable: {rag_fns['_error']}"}

        try:
            return rag_fns["query_pipeline"](
                query=query,
                persist_dir=chroma_dir,
                n_results=n_results,
            )
        except Exception as exc:
            from utils import error_response

            return error_response(exc)

    @mcp.tool()
    def rag_agent_query(query: str) -> dict:
        """Multi-agent RAG for complex or multi-part questions.

        A coordinator agent decomposes the query, performs multiple targeted
        searches, and synthesises a comprehensive answer. Slower and more
        expensive than rag_query but handles questions spanning multiple
        topics or documents. Hard-capped at 10 turns, 50K input tokens,
        10K output tokens, 8 API calls.
        """
        if "_error" in rag_fns:
            return {"error": f"RAG pipeline unavailable: {rag_fns['_error']}"}

        try:
            result = rag_fns["agent_query_pipeline"](query=query)
            result.pop("_trace", None)
            result.pop("_raw_tool_results", None)
            return result
        except Exception as exc:
            from utils import error_response

            return error_response(exc)

    @mcp.tool()
    def rag_index(corpus_path: str) -> dict:
        """Re-index a corpus directory into the vector store.

        WARNING: destructive — clears the existing vector store and rebuilds
        from scratch. Parses all documents, chunks them, computes embeddings,
        and stores in ChromaDB. Run once per corpus or when documents change.
        """
        if "_error" in rag_fns:
            return {"error": f"RAG pipeline unavailable: {rag_fns['_error']}"}

        try:
            from utils import validate_path

            validated = validate_path(corpus_path)
            if not validated.is_dir():
                return {"error": f"corpus_path must be a directory: {corpus_path}"}

            count = rag_fns["index_corpus"](
                corpus_path=str(validated),
                persist_dir=chroma_dir,
            )
            return {
                "status": "indexed",
                "chunks": count,
                "corpus_path": str(validated),
            }
        except Exception as exc:
            from utils import error_response

            return error_response(exc)
