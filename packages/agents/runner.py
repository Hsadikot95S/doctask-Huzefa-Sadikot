from collections.abc import Callable
from uuid import UUID

from packages.agents.graphs.adapter import invoke_workflow_graph
from packages.agents.workflow import build_stage_graph
from packages.core.checkpoint import WorkflowCheckpoint
from packages.core.state import WorkflowState
from packages.db.database import SessionLocal
from packages.db.repositories.runs import RunRepository


class WorkflowRunner:
    def __init__(
        self,
        repository: RunRepository | None = None,
        checkpoint: WorkflowCheckpoint | None = None,
        graph_factory: Callable[..., object] | None = None,
    ):
        self.repository = repository or RunRepository()
        self.checkpoint = checkpoint or WorkflowCheckpoint(
            self.repository
        )
        self.graph_factory = graph_factory or build_stage_graph

    def run(self, run_id: UUID) -> WorkflowState:
        try:
            with SessionLocal() as session:
                run = self.repository.get(session, run_id)

                if run is None:
                    raise ValueError(
                        f"Analysis run {run_id} not found"
                    )

                state = self.checkpoint.restore(run)

                # A completed run is already finished.
                if state["status"] == "completed":
                    return state

                state["status"] = "running"

                run = self.checkpoint.save(
                    session,
                    run,
                    state,
                )

                while True:
                    stage = state["current_stage"]

                    # -------------------------------------------------
                    # Extraction
                    # -------------------------------------------------
                    if stage == "extract_text":
                        graph_stage = (
                            "incremental_extract_text"
                            if state.get("update_id")
                            else "extract_text"
                        )

                        graph = self.graph_factory(
                            graph_stage,
                            session=session,
                        )

                        state = invoke_workflow_graph(
                            graph,
                            state,
                        )

                        state["current_stage"] = "analyze"

                        run = self.checkpoint.save(
                            session,
                            run,
                            state,
                        )

                        continue

                    # -------------------------------------------------
                    # Analysis
                    # -------------------------------------------------
                    if stage == "analyze":
                        graph_stage = (
                            "incremental_analyze"
                            if state.get("update_id")
                            else "analyze"
                        )

                        graph = self.graph_factory(
                            graph_stage,
                            session=session,
                        )

                        state = invoke_workflow_graph(
                            graph,
                            state,
                        )

                        # Analysis produces proposed findings.
                        # The workflow stops for human review.
                        state["current_stage"] = "review"
                        state["status"] = "awaiting_review"

                        run = self.checkpoint.save(
                            session,
                            run,
                            state,
                        )

                        return state

                    # -------------------------------------------------
                    # Human review boundary
                    # -------------------------------------------------
                    if stage == "review":
                        # Do not automatically approve anything.
                        # A human or machine must explicitly decide
                        # every finding through ReviewService.

                        pending_findings = [
                            finding
                            for finding in state["findings"]
                            if finding["status"] == "pending"
                        ]

                        if pending_findings:
                            state["status"] = "awaiting_review"

                            run = self.checkpoint.save(
                                session,
                                run,
                                state,
                            )

                            return state

                        # All findings have explicit decisions.
                        state["current_stage"] = "complete"
                        state["status"] = "completed"

                        run = self.checkpoint.save(
                            session,
                            run,
                            state,
                        )

                        return state

                    # -------------------------------------------------
                    # Completed
                    # -------------------------------------------------
                    if stage == "complete":
                        state["status"] = "completed"

                        run = self.checkpoint.save(
                            session,
                            run,
                            state,
                        )

                        return state

                    raise ValueError(
                        f"Cannot resume run {run_id}: "
                        f"unsupported stage '{stage}'"
                    )

        except Exception as exc:
            with SessionLocal() as session:
                run = self.repository.get(session, run_id)

                if run is not None:
                    run.status = "failed"
                    run.error = str(exc)

                    session.commit()

            raise