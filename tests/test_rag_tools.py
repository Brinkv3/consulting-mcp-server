"""Tests for RAG pipeline MCP tool wrappers."""

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from mcp.server.fastmcp import FastMCP
from rag_tools import register_rag_tools


@pytest.fixture
def mcp_server():
    return FastMCP("test-server")


@pytest.fixture
def mock_rag_fns():
    return {
        "query_pipeline": MagicMock(return_value={
            "query": "test query",
            "retrieval": [{"rank": 1, "text": "chunk"}],
            "answer": "test answer",
            "cited_chunks": [1],
        }),
        "agent_query_pipeline": MagicMock(return_value={
            "query": "test query",
            "answer": "agent answer",
            "cited_chunks": [1],
            "searches_performed": 3,
            "trace": {"steps": 5},
            "_trace": object(),
            "_raw_tool_results": [],
        }),
        "index_corpus": MagicMock(return_value=42),
    }


@pytest.fixture
def config():
    return {"rag_chroma_dir": "/tmp/test-chroma"}


class TestRagToolRegistration:
    def test_registers_three_tools(self, mcp_server, mock_rag_fns, config):
        register_rag_tools(mcp_server, mock_rag_fns, config)
        tools = mcp_server._tool_manager._tools
        assert "rag_query" in tools
        assert "rag_agent_query" in tools
        assert "rag_index" in tools

    def test_unavailable_pipeline_returns_error(self, mcp_server, config):
        error_fns = {"_error": "not found"}
        register_rag_tools(mcp_server, error_fns, config)

        tool = mcp_server._tool_manager._tools["rag_query"]
        result = tool.fn(query="test")
        assert "error" in result
        assert "unavailable" in result["error"]


class TestRagQuery:
    def test_calls_query_pipeline(self, mcp_server, mock_rag_fns, config):
        register_rag_tools(mcp_server, mock_rag_fns, config)
        tool = mcp_server._tool_manager._tools["rag_query"]

        result = tool.fn(query="what is X?", n_results=3)
        mock_rag_fns["query_pipeline"].assert_called_once_with(
            query="what is X?",
            persist_dir="/tmp/test-chroma",
            n_results=3,
        )
        assert result["answer"] == "test answer"

    def test_default_n_results(self, mcp_server, mock_rag_fns, config):
        register_rag_tools(mcp_server, mock_rag_fns, config)
        tool = mcp_server._tool_manager._tools["rag_query"]

        tool.fn(query="test")
        call_kwargs = mock_rag_fns["query_pipeline"].call_args[1]
        assert call_kwargs["n_results"] == 5


class TestRagAgentQuery:
    def test_strips_non_serializable_keys(self, mcp_server, mock_rag_fns, config):
        register_rag_tools(mcp_server, mock_rag_fns, config)
        tool = mcp_server._tool_manager._tools["rag_agent_query"]

        result = tool.fn(query="complex question")
        assert "_trace" not in result
        assert "_raw_tool_results" not in result
        assert result["answer"] == "agent answer"
        assert result["trace"] == {"steps": 5}


class TestRagIndex:
    def test_validates_directory(self, mcp_server, mock_rag_fns, config, tmp_path):
        register_rag_tools(mcp_server, mock_rag_fns, config)
        tool = mcp_server._tool_manager._tools["rag_index"]

        test_file = tmp_path / "file.txt"
        test_file.write_text("not a directory")

        result = tool.fn(corpus_path=str(test_file))
        assert "error" in result
        assert "directory" in result["error"]

    def test_calls_index_corpus(self, mcp_server, mock_rag_fns, config, tmp_path):
        register_rag_tools(mcp_server, mock_rag_fns, config)
        tool = mcp_server._tool_manager._tools["rag_index"]

        result = tool.fn(corpus_path=str(tmp_path))
        assert result["status"] == "indexed"
        assert result["chunks"] == 42
        mock_rag_fns["index_corpus"].assert_called_once()
