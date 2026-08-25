from collections.abc import Callable
from time import perf_counter
from uuid import UUID

from packages.agents.graphs.adapter import (
    invoke_workflow_graph,
)
from packages.agents.workflow import (
    build_stage_graph,
)
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
        self.repository = (
            repository or RunRepository()
        )

        self.checkpoint = (
            checkpoint
            or WorkflowCheckpoint(self.repository)
        )

        self.graph_factory = (
            graph_factory
            or build_stage_graph
        )

    def run(
        self,
        run_id: UUID,
    ) -> WorkflowState:

        try:
            with SessionLocal() as session:

                run = self.repository.get(
                    session,
                    run_id,
                )

                if run is None:
                    raise ValueError(
                        f"Analysis run {run_id} not found"
                    )

                state = self.checkpoint.restore(
                    run
                )

                # A completed run is already terminal.
                if state["status"] == "completed":
                    return state

                state["status"] = "running"

                run = self.checkpoint.save(
                    session,
                    run,
                    state,
                )

                while True:

                    stage = state[
                        "current_stage"
                    ]

                    if stage == "extract_text":

                        started = perf_counter()

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

                        duration_ms = (
                            perf_counter()
                            - started
                        ) * 1000

                        stage_result = state[
                            "stages"
                        ].get(
                            "extract_text",
                            {},
                        )

                        stage_result[
                            "metrics"
                        ] = { # pyright: ignore[reportGeneralTypeIssues]
                            "duration_ms": duration_ms,
                            "input_tokens": None,
                            "output_tokens": None,
                            "estimated_cost": None,
                        }

                        state[
                            "stages"
                        ][
                            "extract_text"
                        ] = stage_result # pyright: ignore[reportArgumentType]

                        state[
                            "current_stage"
                        ] = "analyze"

                        run = self.checkpoint.save(
                            session,
                            run,
                            state,
                        )

                        continue

                    if stage == "analyze":

                        started = perf_counter()

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

                        duration_ms = (
                            perf_counter()
                            - started
                        ) * 1000

                        stage_result = state[
                            "stages"
                        ].get(
                            "analyze",
                            {},
                        )

                        usage = state.get(
                            "analysis_usage"
                        )

                        stage_result[
                            "metrics"
                        ] = { # pyright: ignore[reportGeneralTypeIssues]
                            "duration_ms": duration_ms,
                            "input_tokens": (
                                usage.get(
                                    "input_tokens"
                                )
                                if usage
                                else None
                            ),
                            "output_tokens": (
                                usage.get(
                                    "output_tokens"
                                )
                                if usage
                                else None
                            ),
                            "estimated_cost": (
                                usage.get(
                                    "estimated_cost"
                                )
                                if usage
                                else None
                            ),
                        }

                        state[
                            "stages"
                        ][
                            "analyze"
                        ] = stage_result # pyright: ignore[reportArgumentType]

                        state[
                            "current_stage"
                        ] = "review"

                        state[
                            "status"
                        ] = "awaiting_review"

                        run = self.checkpoint.save(
                            session,
                            run,
                            state,
                        )

                        return state

                    if stage == "review":

                        if not all(
                            finding["status"]
                            in {
                                "approved",
                                "rejected",
                            }
                            for finding
                            in state["findings"]
                        ):
                            state[
                                "status"
                            ] = "awaiting_review"

                            self.checkpoint.save(
                                session,
                                run,
                                state,
                            )

                            return state

                        state[
                            "current_stage"
                        ] = "complete"

                        continue

                    if stage == "incremental_extract_text":

                        started = perf_counter()

                        graph = self.graph_factory(
                            "incremental_extract_text",
                            session=session,
                        )

                        state = invoke_workflow_graph(
                            graph,
                            state,
                        )

                        duration_ms = (
                            perf_counter()
                            - started
                        ) * 1000

                        stage_result = state[
                            "stages"
                        ].get(
                            "incremental_extract_text",
                            {},
                        )

                        stage_result[
                            "metrics"
                        ] = { # pyright: ignore[reportGeneralTypeIssues]
                            "duration_ms": duration_ms,
                            "input_tokens": None,
                            "output_tokens": None,
                            "estimated_cost": None,
                        }

                        state[
                            "stages"
                        ][
                            "incremental_extract_text"
                        ] = stage_result # pyright: ignore[reportArgumentType]

                        state[
                            "current_stage"
                        ] = "incremental_analyze"

                        run = self.checkpoint.save(
                            session,
                            run,
                            state,
                        )

                        continue

                    if stage == "incremental_analyze":

                        started = perf_counter()

                        graph = self.graph_factory(
                            "incremental_analyze",
                            session=session,
                        )

                        state = invoke_workflow_graph(
                            graph,
                            state,
                        )

                        duration_ms = (
                            perf_counter()
                            - started
                        ) * 1000

                        stage_result = state[
                            "stages"
                        ].get(
                            "incremental_analyze",
                            {},
                        )

                        usage = state.get(
                            "analysis_usage"
                        )

                        stage_result[
                            "metrics"
                        ] = { # pyright: ignore[reportGeneralTypeIssues]
                            "duration_ms": duration_ms,
                            "input_tokens": (
                                usage.get(
                                    "input_tokens"
                                )
                                if usage
                                else None
                            ),
                            "output_tokens": (
                                usage.get(
                                    "output_tokens"
                                )
                                if usage
                                else None
                            ),
                            "estimated_cost": (
                                usage.get(
                                    "estimated_cost"
                                )
                                if usage
                                else None
                            ),
                        }

                        state[
                            "stages"
                        ][
                            "incremental_analyze"
                        ] = stage_result # pyright: ignore[reportArgumentType]

                        state[
                            "current_stage"
                        ] = "review"

                        state[
                            "status"
                        ] = "awaiting_review"

                        run = self.checkpoint.save(
                            session,
                            run,
                            state,
                        )

                        return state

                    if stage == "complete":

                        state[
                            "status"
                        ] = "completed"

                        run = self.checkpoint.save(
                            session,
                            run,
                            state,
                        )

                        return state

                    if stage == "failed":
                        return state

                    raise ValueError(
                        f"Cannot resume run {run_id}: "
                        f"unsupported stage '{stage}'"
                    )

        except Exception as exc:

            with SessionLocal() as session:

                run = self.repository.get(
                    session,
                    run_id,
                )

                if run is not None:

                    run.status = "failed"
                    run.error = str(exc)

                    session.commit()

            raise