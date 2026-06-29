"""Tests for Document Intelligence MCP tool wrappers."""

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from mcp.server.fastmcp import FastMCP
from doc_tools import register_doc_tools


class MockClassificationResult:
    def to_dict(self):
        return {
            "document_id": "test.pdf",
            "document_type": "sow",
            "confidence": 95,
            "reasoning": "Contains deliverables and scope",
        }


class MockPipelineResult:
    def to_dict(self):
        return {
            "document_id": "test.pdf",
            "classification": {"document_type": "sow", "confidence": 95},
            "extraction": {"fields": [{"name": "title", "value": "Test SOW"}]},
            "validation": {"is_valid": True, "field_summary": {"total_fields": 14}},
        }


class MockAssessment:
    def to_dict(self):
        return {
            "documents": [{"document_id": "a.pdf"}, {"document_id": "b.pdf"}],
            "cross_document_analysis": {"findings": [], "summary": "no issues"},
            "narrative_summary": "All clear",
            "metadata": {"document_count": 2},
        }


@pytest.fixture
def mcp_server():
    return FastMCP("test-server")


@pytest.fixture
def mock_doc_fns():
    return {
        "parse_file": MagicMock(return_value=MagicMock(doc_id="test.pdf")),
        "classify_document": MagicMock(return_value=MockClassificationResult()),
        "process_document": MagicMock(return_value=MockPipelineResult()),
        "process_and_assess": MagicMock(return_value=MockAssessment()),
        "get_available_types": MagicMock(return_value=[
            {"document_type": "sow", "display_name": "Statement of Work"},
        ]),
        "Document": MagicMock,
    }


@pytest.fixture
def config():
    return {"doc_schemas_dir": "/tmp/test-schemas"}


class TestDocToolRegistration:
    def test_registers_four_tools(self, mcp_server, mock_doc_fns, config):
        register_doc_tools(mcp_server, mock_doc_fns, config)
        tools = mcp_server._tool_manager._tools
        assert "doc_classify" in tools
        assert "doc_extract" in tools
        assert "doc_assess" in tools
        assert "doc_types" in tools

    def test_unavailable_pipeline_returns_error(self, mcp_server, config):
        error_fns = {"_error": "not found"}
        register_doc_tools(mcp_server, error_fns, config)

        tool = mcp_server._tool_manager._tools["doc_classify"]
        result = tool.fn(file_path="/tmp/test.pdf")
        assert "error" in result
        assert "unavailable" in result["error"]


class TestDocClassify:
    def test_parses_and_classifies(self, mcp_server, mock_doc_fns, config, tmp_path):
        register_doc_tools(mcp_server, mock_doc_fns, config)
        tool = mcp_server._tool_manager._tools["doc_classify"]

        test_file = tmp_path / "test.pdf"
        test_file.write_text("fake pdf")

        result = tool.fn(file_path=str(test_file))
        assert result["document_type"] == "sow"
        assert result["confidence"] == 95
        mock_doc_fns["parse_file"].assert_called_once()
        mock_doc_fns["classify_document"].assert_called_once()

    def test_nonexistent_file_returns_error(self, mcp_server, mock_doc_fns, config):
        register_doc_tools(mcp_server, mock_doc_fns, config)
        tool = mcp_server._tool_manager._tools["doc_classify"]

        result = tool.fn(file_path="/nonexistent/file.pdf")
        assert "error" in result
        assert result["error_type"] == "FileNotFoundError"


class TestDocExtract:
    def test_calls_process_document(self, mcp_server, mock_doc_fns, config, tmp_path):
        register_doc_tools(mcp_server, mock_doc_fns, config)
        tool = mcp_server._tool_manager._tools["doc_extract"]

        test_file = tmp_path / "test.pdf"
        test_file.write_text("fake pdf")

        result = tool.fn(file_path=str(test_file))
        assert result["classification"]["document_type"] == "sow"
        assert result["validation"]["is_valid"] is True
        mock_doc_fns["process_document"].assert_called_once()


class TestDocAssess:
    def test_validates_directory(self, mcp_server, mock_doc_fns, config, tmp_path):
        register_doc_tools(mcp_server, mock_doc_fns, config)
        tool = mcp_server._tool_manager._tools["doc_assess"]

        test_file = tmp_path / "file.txt"
        test_file.write_text("not a dir")

        result = tool.fn(directory_path=str(test_file))
        assert "error" in result
        assert "directory" in result["error"]

    def test_calls_process_and_assess(self, mcp_server, mock_doc_fns, config, tmp_path):
        register_doc_tools(mcp_server, mock_doc_fns, config)
        tool = mcp_server._tool_manager._tools["doc_assess"]

        result = tool.fn(directory_path=str(tmp_path))
        assert result["metadata"]["document_count"] == 2
        mock_doc_fns["process_and_assess"].assert_called_once()


class TestDocTypes:
    def test_returns_types_with_count(self, mcp_server, mock_doc_fns, config):
        register_doc_tools(mcp_server, mock_doc_fns, config)
        tool = mcp_server._tool_manager._tools["doc_types"]

        result = tool.fn()
        assert result["count"] == 1
        assert result["document_types"][0]["document_type"] == "sow"
