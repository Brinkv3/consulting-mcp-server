"""MCP tool wrappers for the Agentic Audit pipeline."""

from __future__ import annotations

import json
from pathlib import Path


def register_audit_tools(mcp, audit_fns: dict, config: dict) -> None:

    audit_path = config.get("audit_path", "")
    output_dir = Path(audit_path) / "output" if audit_path else Path("output")

    @mcp.tool()
    def audit_generate_questions(
        engagement_docs_dir: str,
        engagement_name: str,
    ) -> dict:
        """Generate interview questions from engagement documents.

        Analyzes documents in the directory (SOWs, project plans, etc.) and
        generates a structured question framework for data audit interviews.
        Saves the framework as JSON for use with audit_process_interview.
        Returns the questions and the saved file path.
        """
        if "_error" in audit_fns:
            return {"error": f"Agentic audit unavailable: {audit_fns['_error']}"}

        try:
            from utils import validate_path

            validated = validate_path(engagement_docs_dir)
            if not validated.is_dir():
                return {"error": f"engagement_docs_dir must be a directory: {engagement_docs_dir}"}

            docs = [p for p in validated.iterdir() if p.is_file()]
            if not docs:
                return {"error": f"No files found in {engagement_docs_dir}"}

            Orchestrator = audit_fns["AuditOrchestrator"]
            o = Orchestrator(engagement_name)
            framework = o.generate_questions([str(d) for d in docs])

            output_dir.mkdir(parents=True, exist_ok=True)
            export_path = output_dir / f"{engagement_name}_questions.json"
            audit_fns["export_framework_json"](framework, export_path)

            return {
                "status": "generated",
                "engagement_name": engagement_name,
                "questions_count": len(framework.questions),
                "questions_path": str(export_path),
                "questions": [
                    {"id": q.id, "text": q.text, "category": q.category}
                    for q in framework.questions
                ],
            }
        except Exception as exc:
            from utils import error_response

            return error_response(exc)

    @mcp.tool()
    def audit_process_interview(
        questions_path: str,
        interview_dir: str,
        engagement_name: str,
        application_name: str | None = None,
    ) -> dict:
        """Process interview artifacts against a question framework.

        Takes a previously generated question framework (JSON) and a directory
        of interview artifacts (transcripts, notes, documents). Runs the full
        pipeline: intake, answer synthesis, principle-based analysis, and
        validation. Saves the result as JSON for use with audit_synthesize.

        Call once per application/interview. Results accumulate — run
        audit_synthesize after all interviews are processed.
        """
        if "_error" in audit_fns:
            return {"error": f"Agentic audit unavailable: {audit_fns['_error']}"}

        try:
            from utils import validate_path

            q_path = validate_path(questions_path)
            i_dir = validate_path(interview_dir)
            if not i_dir.is_dir():
                return {"error": f"interview_dir must be a directory: {interview_dir}"}

            Orchestrator = audit_fns["AuditOrchestrator"]
            o = Orchestrator(engagement_name)
            o.load_questions(str(q_path))
            o.lock_questions()
            result = o.process_interview(directory=str(i_dir), application_name=application_name)

            output_dir.mkdir(parents=True, exist_ok=True)
            results_dir = output_dir / f"{engagement_name}_results"
            results_dir.mkdir(parents=True, exist_ok=True)
            result_path = results_dir / f"{result.application_name}.json"
            result_path.write_text(result.model_dump_json(indent=2))

            trace = o.get_trace()

            return {
                "status": "processed",
                "application_name": result.application_name,
                "answers_count": len(result.answered_questions),
                "findings_count": len(result.findings),
                "result_path": str(result_path),
                "results_dir": str(results_dir),
                "tokens_used": trace.get("total_tokens", 0),
            }
        except Exception as exc:
            from utils import error_response

            return error_response(exc)

    @mcp.tool()
    def audit_synthesize(
        questions_path: str,
        results_dir: str,
        engagement_name: str,
        output_path: str | None = None,
    ) -> dict:
        """Synthesize all interview results into a client-ready deliverable.

        Takes a question framework and a directory of saved interview results
        (from audit_process_interview). Generates an executive summary, AI
        observations, coverage matrix, and Excel workbook.

        Call after all interviews have been processed.
        """
        if "_error" in audit_fns:
            return {"error": f"Agentic audit unavailable: {audit_fns['_error']}"}

        try:
            from utils import validate_path

            q_path = validate_path(questions_path)
            r_dir = validate_path(results_dir)
            if not r_dir.is_dir():
                return {"error": f"results_dir must be a directory: {results_dir}"}

            AppResult = audit_fns["AppResult"]
            result_files = sorted(r_dir.glob("*.json"))
            if not result_files:
                return {"error": f"No result files found in {results_dir}"}

            Orchestrator = audit_fns["AuditOrchestrator"]
            o = Orchestrator(engagement_name)
            o.load_questions(str(q_path))
            o.lock_questions()

            for f in result_files:
                o.app_results.append(AppResult.model_validate_json(f.read_text()))

            out = output_path or str(output_dir / f"{engagement_name}_audit.xlsx")
            workbook_path = o.generate_deliverable(out)
            trace = o.get_trace()

            return {
                "status": "complete",
                "applications_count": len(o.app_results),
                "deliverable_path": str(workbook_path),
                "tokens_used": trace.get("total_tokens", 0),
            }
        except Exception as exc:
            from utils import error_response

            return error_response(exc)
