"""Configuration, path validation, and pipeline import management."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

_config: dict | None = None


def load_config() -> dict:
    global _config
    if _config is not None:
        return _config

    load_dotenv()

    _config = {
        "rag_pipeline_path": os.getenv("RAG_PIPELINE_PATH"),
        "doc_intel_path": os.getenv("DOC_INTEL_PATH"),
        "audit_path": os.getenv("AUDIT_PATH"),
        "llm_provider": os.getenv("LLM_PROVIDER"),
        "llm_api_key": os.getenv("LLM_API_KEY"),
        "rag_chroma_dir": None,
        "doc_schemas_dir": None,
    }

    if _config["rag_pipeline_path"]:
        _config["rag_chroma_dir"] = os.path.join(
            _config["rag_pipeline_path"], "chroma"
        )
    if _config["doc_intel_path"]:
        _config["doc_schemas_dir"] = os.path.join(
            _config["doc_intel_path"], "schemas"
        )

    return _config


def setup_pipeline_imports(config: dict) -> tuple[dict, dict, dict]:
    """Import pipeline modules, handling the src namespace conflict between repos.

    All three pipelines use ``src/`` as their package directory. We import one
    at a time, capture function references, then flush ``sys.modules['src.*']``
    before the next import so the packages never collide.
    """
    rag_fns = _import_rag_modules(config.get("rag_pipeline_path"))
    doc_fns = _import_doc_modules(config.get("doc_intel_path"))
    audit_fns = _import_audit_modules(config.get("audit_path"))
    return rag_fns, doc_fns, audit_fns


def _import_rag_modules(rag_path: str | None) -> dict:
    if not rag_path or not Path(rag_path).is_dir():
        return {"_error": f"RAG pipeline path not found: {rag_path}"}

    # AuditLogger creates a logs/ dir relative to CWD at import time
    prev_cwd = os.getcwd()
    os.chdir(rag_path)
    sys.path.insert(0, rag_path)
    try:
        from src.pipeline import (
            agent_query_pipeline,
            index_corpus,
            query_pipeline,
        )

        return {
            "query_pipeline": query_pipeline,
            "agent_query_pipeline": agent_query_pipeline,
            "index_corpus": index_corpus,
        }
    except Exception as exc:
        return {"_error": f"Failed to import RAG pipeline: {exc}"}
    finally:
        os.chdir(prev_cwd)
        if rag_path in sys.path:
            sys.path.remove(rag_path)
        _clear_src_modules()


def _import_doc_modules(doc_path: str | None) -> dict:
    if not doc_path or not Path(doc_path).is_dir():
        return {"_error": f"Doc intelligence path not found: {doc_path}"}

    sys.path.insert(0, doc_path)
    try:
        from src.classifier import classify_document
        from src.ingest import Document, parse_file
        from src.pipeline import process_and_assess, process_document
        from src.schema_loader import get_available_types

        return {
            "process_document": process_document,
            "process_and_assess": process_and_assess,
            "classify_document": classify_document,
            "get_available_types": get_available_types,
            "parse_file": parse_file,
            "Document": Document,
        }
    except Exception as exc:
        return {"_error": f"Failed to import doc intelligence: {exc}"}
    finally:
        if doc_path in sys.path:
            sys.path.remove(doc_path)
        _clear_src_modules()


def _import_audit_modules(audit_path: str | None) -> dict:
    if not audit_path or not Path(audit_path).is_dir():
        return {"_error": f"Agentic audit path not found: {audit_path}"}

    prev_cwd = os.getcwd()
    os.chdir(audit_path)
    sys.path.insert(0, audit_path)
    try:
        from src.orchestrator import AuditOrchestrator
        from src.question_gen import export_framework_json
        from src.models import AppResult

        return {
            "AuditOrchestrator": AuditOrchestrator,
            "export_framework_json": export_framework_json,
            "AppResult": AppResult,
        }
    except Exception as exc:
        return {"_error": f"Failed to import agentic audit: {exc}"}
    finally:
        os.chdir(prev_cwd)
        if audit_path in sys.path:
            sys.path.remove(audit_path)
        _clear_src_modules()


def _clear_src_modules() -> None:
    to_remove = [k for k in sys.modules if k == "src" or k.startswith("src.")]
    for k in to_remove:
        del sys.modules[k]


def validate_path(path_str: str, must_exist: bool = True) -> Path:
    path = Path(path_str).resolve()
    if must_exist and not path.exists():
        raise FileNotFoundError(f"Path not found: {path}")
    return path


def error_response(exc: Exception) -> dict:
    return {"error": str(exc), "error_type": type(exc).__name__}
