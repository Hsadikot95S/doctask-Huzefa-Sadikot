# SuperDocs — Agentic Document Analysis Workflow

A production-oriented agentic document analysis workflow built for the SuperDocs engineering assignment.

The system is designed around **durable workflow state, resumable execution, incremental updates, and human-in-the-loop review**. The implementation favors explicit state transitions, repository-backed persistence, checkpointing, concurrency control, and integration tests over purely in-memory orchestration.

---

## Current Status

### Test Status

**50 automated tests passing.**

### Implemented

- Durable PostgreSQL-backed workflow state
- Stage-level checkpointing
- Process kill/restart recovery
- Completed-stage no-replay behavior
- Human-in-the-loop review boundary
- Item-level approve/reject decisions
- Resume after review
- Optimistic concurrency protection
- Atomic run claiming and worker ownership
- Run leases and lease renewal
- Incremental update creation
- Dedicated runs for incremental updates
- Incremental document extraction
- Incremental analysis routing
- Preservation of existing target findings during incremental updates
- New incremental findings represented as `pending` proposals
- Integration coverage for the incremental-update lifecycle

### In Progress

- Conflict detection between existing findings and new source material
- Change lineage and provenance
- More focused semantic change detection
- Machine-driven API surface
- MCP surface
- Security hardening
- Telemetry and observability
- Final production hardening

---

# Architecture

```text
                           Document
                              │
                              ▼
                    ┌──────────────────┐
                    │ Document Service │
                    └────────┬─────────┘
                             │
                             ▼
                    ┌──────────────────┐
                    │  Workflow Runner │
                    └────────┬─────────┘
                             │
                 ┌───────────┴───────────┐
                 │                       │
            Normal Run             Incremental Run
                 │                       │
                 ▼                       ▼
           extract_text       incremental_extract_text
                 │                       │
                 ▼                       ▼
              analyze           incremental_analyze
                 │                       │
                 └───────────┬───────────┘
                             ▼
                       Review Boundary
                             │
                    ┌────────┴────────┐
                    │                 │
                 approve           reject
                    │                 │
                    └────────┬────────┘
                             ▼
                          complete
                             │
                             ▼
                    Durable PostgreSQL
                       workflow state