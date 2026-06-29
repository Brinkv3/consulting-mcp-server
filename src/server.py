"""Consulting MCP Server — unified tool surface for RAG and Document Intelligence.

Start via stdio:  python src/server.py
"""

from __future__ import annotations

from pathlib import Path

from mcp.server.fastmcp import FastMCP

from utils import error_response, load_config, setup_pipeline_imports
from rag_tools import register_rag_tools
from doc_tools import register_doc_tools

mcp = FastMCP(
    "consulting-mcp-server",
    instructions=(
        "AI-powered document analysis and knowledge base tools. "
        "Use rag_* tools to search and ask questions across an indexed corpus. "
        "Use doc_* tools to classify, extract fields from, and compare documents. "
        "Call health first to verify the server is properly configured."
    ),
)

config = load_config()
rag_fns, doc_fns = setup_pipeline_imports(config)

register_rag_tools(mcp, rag_fns, config)
register_doc_tools(mcp, doc_fns, config)


@mcp.tool()
def health() -> dict:
    """Server health check: verify API key, vector store, schemas, and pipeline availability.

    Returns the status of each component. Call this to confirm the server
    is properly configured before using other tools.
    """
    status: dict = {
        "server": "running",
        "rag_pipeline": "unavailable" if "_error" in rag_fns else "available",
        "doc_intelligence": "unavailable" if "_error" in doc_fns else "available",
        "anthropic_api_key": "set" if config.get("anthropic_api_key") else "missing",
    }

    chroma_dir = config.get("rag_chroma_dir")
    if chroma_dir:
        status["vector_store"] = "found" if Path(chroma_dir).is_dir() else "not found"
    else:
        status["vector_store"] = "not configured"

    schemas_dir = config.get("doc_schemas_dir")
    if schemas_dir:
        schemas_path = Path(schemas_dir)
        if schemas_path.is_dir():
            schema_count = len(list(schemas_path.glob("*.json")))
            status["schemas"] = f"found ({schema_count} types)"
        else:
            status["schemas"] = "directory not found"
    else:
        status["schemas"] = "not configured"

    if "_error" in rag_fns:
        status["rag_error"] = rag_fns["_error"]
    if "_error" in doc_fns:
        status["doc_error"] = doc_fns["_error"]

    return status


if __name__ == "__main__":
    mcp.run(transport="stdio")
