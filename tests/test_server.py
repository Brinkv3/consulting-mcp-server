"""Tests for MCP server initialization and health tool."""

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from utils import load_config, setup_pipeline_imports, validate_path, error_response


class TestConfig:
    @patch.dict("os.environ", {
        "RAG_PIPELINE_PATH": "/tmp/fake-rag",
        "DOC_INTEL_PATH": "/tmp/fake-doc",
        "AUDIT_PATH": "/tmp/fake-audit",
        "LLM_PROVIDER": "anthropic",
        "LLM_API_KEY": "sk-test-key",
    })
    def test_load_config_reads_env(self):
        import utils
        utils._config = None
        config = load_config()
        assert config["rag_pipeline_path"] == "/tmp/fake-rag"
        assert config["doc_intel_path"] == "/tmp/fake-doc"
        assert config["audit_path"] == "/tmp/fake-audit"
        assert config["llm_provider"] == "anthropic"
        assert config["llm_api_key"] == "sk-test-key"
        assert config["rag_chroma_dir"] == "/tmp/fake-rag/chroma"
        assert config["doc_schemas_dir"] == "/tmp/fake-doc/schemas"
        utils._config = None

    @patch("utils.load_dotenv")
    @patch.dict("os.environ", {}, clear=True)
    def test_load_config_handles_missing_env(self, _mock_dotenv):
        import utils
        utils._config = None
        config = load_config()
        assert config["rag_pipeline_path"] is None
        assert config["llm_provider"] is None
        assert config["llm_api_key"] is None
        utils._config = None


class TestValidatePath:
    def test_valid_existing_path(self, tmp_path):
        test_file = tmp_path / "test.txt"
        test_file.write_text("hello")
        result = validate_path(str(test_file))
        assert result == test_file.resolve()

    def test_nonexistent_path_raises(self):
        with pytest.raises(FileNotFoundError):
            validate_path("/nonexistent/path/file.txt")

    def test_nonexistent_path_no_check(self):
        result = validate_path("/nonexistent/path/file.txt", must_exist=False)
        assert result == Path("/nonexistent/path/file.txt")


class TestErrorResponse:
    def test_wraps_exception(self):
        result = error_response(ValueError("bad input"))
        assert result == {"error": "bad input", "error_type": "ValueError"}

    def test_wraps_file_not_found(self):
        result = error_response(FileNotFoundError("missing"))
        assert result["error_type"] == "FileNotFoundError"


class TestPipelineImports:
    def test_missing_rag_path_returns_error(self):
        rag_fns, _, _ = setup_pipeline_imports({
            "rag_pipeline_path": "/nonexistent/rag",
            "doc_intel_path": None,
        })
        assert "_error" in rag_fns

    def test_missing_doc_path_returns_error(self):
        _, doc_fns, _ = setup_pipeline_imports({
            "rag_pipeline_path": None,
            "doc_intel_path": "/nonexistent/doc",
        })
        assert "_error" in doc_fns

    def test_missing_audit_path_returns_error(self):
        _, _, audit_fns = setup_pipeline_imports({
            "rag_pipeline_path": None,
            "doc_intel_path": None,
            "audit_path": "/nonexistent/audit",
        })
        assert "_error" in audit_fns

    def test_real_pipeline_imports(self):
        rag_path = str(Path(__file__).parent.parent.parent / "rag-pipeline")
        doc_path = str(Path(__file__).parent.parent.parent / "doc-intelligence")
        audit_path = str(Path(__file__).parent.parent.parent / "agentic-audit")

        if not Path(rag_path).is_dir() or not Path(doc_path).is_dir():
            pytest.skip("Pipeline repos not found at expected paths")

        rag_fns, doc_fns, audit_fns = setup_pipeline_imports({
            "rag_pipeline_path": rag_path,
            "doc_intel_path": doc_path,
            "audit_path": audit_path,
        })

        assert "_error" not in rag_fns, rag_fns.get("_error")
        assert "query_pipeline" in rag_fns
        assert "agent_query_pipeline" in rag_fns
        assert "index_corpus" in rag_fns

        assert "_error" not in doc_fns, doc_fns.get("_error")
        assert "process_document" in doc_fns
        assert "process_and_assess" in doc_fns
        assert "classify_document" in doc_fns
        assert "get_available_types" in doc_fns
        assert "parse_file" in doc_fns

        if Path(audit_path).is_dir():
            assert "_error" not in audit_fns, audit_fns.get("_error")
            assert "AuditOrchestrator" in audit_fns
            assert "AppResult" in audit_fns
