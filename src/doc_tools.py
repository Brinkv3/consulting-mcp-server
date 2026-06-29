"""MCP tool wrappers for the Document Intelligence pipeline."""

from __future__ import annotations


def register_doc_tools(mcp, doc_fns: dict, config: dict) -> None:

    @mcp.tool()
    def doc_classify(file_path: str) -> dict:
        """Classify a single document by type (SOW, Contract, Project Plan, etc.).

        Returns the detected document type, confidence score (0-100), and
        reasoning. Supported formats: PDF, DOCX, Markdown, TXT, CSV.
        Uses one API call. For full extraction, use doc_extract instead.
        """
        if "_error" in doc_fns:
            return {"error": f"Doc intelligence unavailable: {doc_fns['_error']}"}

        try:
            from utils import validate_path

            validated = validate_path(file_path)
            doc = doc_fns["parse_file"](str(validated))
            result = doc_fns["classify_document"](doc)
            return result.to_dict()
        except Exception as exc:
            from utils import error_response

            return error_response(exc)

    @mcp.tool()
    def doc_extract(file_path: str) -> dict:
        """Classify, extract structured fields, and validate a single document.

        Full single-document pipeline: classifies the document type, extracts
        typed fields with confidence scores and source locations, then validates
        completeness. Returns classification, extraction (fields with values
        and confidence), and validation summary. Uses 2 API calls.
        """
        if "_error" in doc_fns:
            return {"error": f"Doc intelligence unavailable: {doc_fns['_error']}"}

        try:
            from utils import validate_path

            validated = validate_path(file_path)
            result = doc_fns["process_document"](str(validated))
            return result.to_dict()
        except Exception as exc:
            from utils import error_response

            return error_response(exc)

    @mcp.tool()
    def doc_assess(directory_path: str) -> dict:
        """Full multi-document assessment with cross-document analysis.

        Processes all supported documents in a directory through classification,
        extraction, and validation, then performs cross-document analysis to find
        inconsistencies, gaps, and cross-references. Generates a narrative summary.
        Requires a directory with at least 2 documents for cross-document findings.
        Uses 2N + 2 API calls (N = number of documents).
        """
        if "_error" in doc_fns:
            return {"error": f"Doc intelligence unavailable: {doc_fns['_error']}"}

        try:
            from utils import validate_path

            validated = validate_path(directory_path)
            if not validated.is_dir():
                return {
                    "error": f"directory_path must be a directory: {directory_path}"
                }

            result = doc_fns["process_and_assess"](str(validated))
            return result.to_dict()
        except Exception as exc:
            from utils import error_response

            return error_response(exc)

    @mcp.tool()
    def doc_types() -> dict:
        """List all available document types and their schemas.

        Returns the document types the system can classify and extract, with
        display names, descriptions, and distinguishing characteristics.
        No API call — reads from local schema files.
        """
        if "_error" in doc_fns:
            return {"error": f"Doc intelligence unavailable: {doc_fns['_error']}"}

        try:
            types = doc_fns["get_available_types"]()
            return {"document_types": types, "count": len(types)}
        except Exception as exc:
            from utils import error_response

            return error_response(exc)
