# SuperDocs — Agentic Document Analysis Workflow

A production-oriented agentic document analysis workflow built for the SuperDocs engineering assignment.

The system is designed around durable workflow state, resumable execution, and human-in-the-loop review.

## Current Status

**Task 1 — Core workflow and review infrastructure**

- 25 automated tests passing
- Durable PostgreSQL-backed workflow state
- Stage-level checkpointing
- Process kill/restart recovery
- Completed-stage no-replay guarantee
- Human review gate
- Item-level approve/reject decisions
- Resume after review
- Optimistic concurrency protection

The machine-driven API, evidence grounding, security hardening, telemetry, and final submission documentation are being implemented incrementally.

---

## Architecture

```text
                    Document
                       │
                       ▼
              ┌─────────────────┐
              │   Workflow      │
              │     Runner      │
              └────────┬────────┘
                       │
          ┌────────────┼────────────┐
          ▼            ▼            ▼
     extract_text    analyze     review
          │            │            │
          └────────────┴────────────┘
                       │
                       ▼
                Durable Checkpoint
                       │
                       ▼
                   PostgreSQL
