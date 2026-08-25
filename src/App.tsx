import { useEffect, useMemo, useState } from "react";
import "./App.css";

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

type Finding = {
  finding_id: string;
  description: string;
  status: string;
  evidence: string[];
};

type Stage = {
  status: string;
  error: string | null;
};

type Run = {
  run_id: string;
  document_path: string;
  status: string;
  current_stage: string;
  error: string | null;
  findings: Finding[];
  stages: Record<string, Stage>;
};

const STAGES = ["extract", "analyze", "review", "complete"];

function formatStage(value: string) {
  return value.replaceAll("_", " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function stageIndex(stage: string) {
  const index = STAGES.indexOf(stage.toLowerCase());
  return index === -1 ? 0 : index;
}

function statusLabel(status: string) {
  return status.replaceAll("_", " ");
}

function App() {
  const [runId, setRunId] = useState("");
  const [run, setRun] = useState<Run | null>(null);
  const [loading, setLoading] = useState(false);
  const [reviewing, setReviewing] = useState<string | null>(null);
  const [error, setError] = useState("");

  const currentStageIndex = useMemo(
    () => (run ? stageIndex(run.current_stage) : -1),
    [run],
  );

  async function request<T>(
    path: string,
    options?: RequestInit,
  ): Promise<T> {
    const response = await fetch(`${API_BASE_URL}${path}`, {
      headers: {
        "Content-Type": "application/json",
        ...(options?.headers ?? {}),
      },
      ...options,
    });

    const body = await response.json().catch(() => null);

    if (!response.ok) {
      const message =
        body?.detail ?? `Request failed with status ${response.status}`;
      throw new Error(message);
    }

    return body as T;
  }

  async function loadRun(id = runId) {
    if (!id.trim()) {
      setError("Enter an analysis run ID.");
      return;
    }

    setLoading(true);
    setError("");

    try {
      const data = await request<Run>(`/runs/${id.trim()}`);
      setRun(data);
      setRunId(id.trim());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load run.");
      setRun(null);
    } finally {
      setLoading(false);
    }
  }

  async function resumeRun() {
    if (!run) return;

    setLoading(true);
    setError("");

    try {
      const data = await request<Run>(`/runs/${run.run_id}/resume`, {
        method: "POST",
      });

      setRun(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to resume run.");
    } finally {
      setLoading(false);
    }
  }

  async function reviewFinding(
    findingId: string,
    decision: "approved" | "rejected",
  ) {
    if (!run) return;

    setReviewing(findingId);
    setError("");

    try {
      const data = await request<Run>(`/runs/${run.run_id}/review`, {
        method: "POST",
        body: JSON.stringify({
          finding_id: findingId,
          decision,
        }),
      });

      setRun(data);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Unable to submit review.",
      );
    } finally {
      setReviewing(null);
    }
  }

  useEffect(() => {
    if (!run) return;

    const activeStatuses = new Set([
      "pending",
      "running",
      "processing",
      "in_progress",
    ]);

    if (!activeStatuses.has(run.status)) return;

    const interval = window.setInterval(() => {
      loadRun(run.run_id);
    }, 3000);

    return () => window.clearInterval(interval);
  }, [run?.run_id, run?.status]);

  return (
    <div className="app-shell">
      <header className="topbar">
        <div>
          <div className="brand">SUPERDOCS</div>
          <div className="brand-subtitle">Document Intelligence Console</div>
        </div>

        <div className="system-status">
          <span className="status-dot" />
          API connected
        </div>
      </header>

      <main className="content">
        <section className="hero-section">
          <div>
            <p className="eyebrow">ANALYSIS WORKSPACE</p>
            <h1>Review an analysis run</h1>
            <p className="hero-copy">
              Inspect durable workflow state, review findings, and track
              execution progress from one interface.
            </p>
          </div>

          <form
            className="run-loader"
            onSubmit={(event) => {
              event.preventDefault();
              loadRun();
            }}
          >
            <label htmlFor="run-id">Analysis run ID</label>

            <div className="run-input-row">
              <input
                id="run-id"
                value={runId}
                onChange={(event) => setRunId(event.target.value)}
                placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
              />

              <button type="submit" disabled={loading}>
                {loading ? "Loading..." : "Load run"}
              </button>
            </div>
          </form>
        </section>

        {error && (
          <div className="alert error-alert" role="alert">
            <strong>Request failed</strong>
            <span>{error}</span>
          </div>
        )}

        {!run && !loading && !error && (
          <section className="empty-state">
            <div className="empty-icon">◎</div>
            <h2>No run selected</h2>
            <p>
              Enter an analysis run ID above to inspect its workflow state and
              findings.
            </p>
          </section>
        )}

        {loading && !run && (
          <section className="empty-state">
            <div className="spinner" />
            <h2>Loading run</h2>
            <p>Fetching durable workflow state from the API.</p>
          </section>
        )}

        {run && (
          <>
            <section className="run-overview">
              <div className="overview-main">
                <div className="section-label">ANALYSIS RUN</div>
                <div className="run-id">{run.run_id}</div>

                <div className="document-path">
                  <span className="file-icon">▣</span>
                  {run.document_path}
                </div>
              </div>

              <div className="overview-status">
                <span className="section-label">STATUS</span>
                <span className={`status-pill ${run.status}`}>
                  <span className="pill-dot" />
                  {statusLabel(run.status)}
                </span>
              </div>

              <div className="overview-status">
                <span className="section-label">CURRENT STAGE</span>
                <strong>{formatStage(run.current_stage)}</strong>
              </div>

              <button
                className="secondary-button"
                onClick={resumeRun}
                disabled={loading}
              >
                {loading ? "Running..." : "Resume workflow"}
              </button>
            </section>

            <section className="workflow-card">
              <div className="card-heading">
                <div>
                  <div className="section-label">WORKFLOW</div>
                  <h2>Execution pipeline</h2>
                </div>
              </div>

              <div className="workflow">
                {STAGES.map((stage, index) => {
                  const isRunComplete = run.status === "completed";
                  const completed =
                  index < currentStageIndex ||
                  (index === currentStageIndex && isRunComplete);

                const active =
                  index === currentStageIndex && !isRunComplete;

                  return (
                    <div className="workflow-step-wrapper" key={stage}>
                      <div
                        className={`workflow-step ${
                          completed ? "completed" : ""
                        } ${active ? "active" : ""}`}
                      >
                        <div className="stage-marker">
                          {completed ? "✓" : index + 1}
                        </div>

                        <div>
                          <div className="stage-name">
                            {formatStage(stage)}
                          </div>

                          <div className="stage-status">
                            {completed
                              ? "Completed"
                              : active
                                ? statusLabel(run.status)
                                : "Pending"}
                          </div>
                        </div>
                      </div>

                      {index < STAGES.length - 1 && (
                        <div
                          className={`workflow-line ${
                            index < currentStageIndex ? "completed" : ""
                          }`}
                        />
                      )}
                    </div>
                  );
                })}
              </div>
            </section>

            <section className="findings-section">
              <div className="section-heading-row">
                <div>
                  <div className="section-label">HUMAN REVIEW</div>
                  <h2>Findings</h2>
                </div>

                <span className="finding-count">
                  {run.findings.length}{" "}
                  {run.findings.length === 1 ? "finding" : "findings"}
                </span>
              </div>

              {run.findings.length === 0 ? (
                <div className="empty-card">
                  <span>✓</span>
                  <div>
                    <strong>No findings</strong>
                    <p>
                      This analysis run has not produced any review findings.
                    </p>
                  </div>
                </div>
              ) : (
                <div className="finding-list">
                  {run.findings.map((finding) => {
                    const pending = finding.status === "pending";
                    const busy = reviewing === finding.finding_id;

                    return (
                      <article
                        className={`finding-card ${
                          pending ? "pending" : finding.status
                        }`}
                        key={finding.finding_id}
                      >
                        <div className="finding-header">
                          <div>
                            <span className="finding-id">
                              {finding.finding_id}
                            </span>
                            <span
                              className={`finding-status ${finding.status}`}
                            >
                              {statusLabel(finding.status)}
                            </span>
                          </div>
                        </div>

                        <h3>{finding.description}</h3>

                        <div className="evidence">
                          <div className="evidence-label">
                            SOURCE EVIDENCE
                          </div>

                          {finding.evidence.length === 0 ? (
                            <p className="no-evidence">
                              No evidence recorded.
                            </p>
                          ) : (
                            <ul>
                              {finding.evidence.map((item, index) => (
                                <li key={`${item}-${index}`}>
                                  <span className="evidence-marker">↳</span>
                                  <span>{item}</span>
                                </li>
                              ))}
                            </ul>
                          )}
                        </div>

                        {pending && (
                          <div className="review-actions">
                            <button
                              className="approve-button"
                              disabled={busy}
                              onClick={() =>
                                reviewFinding(
                                  finding.finding_id,
                                  "approved",
                                )
                              }
                            >
                              {busy ? "Submitting..." : "Approve"}
                            </button>

                            <button
                              className="reject-button"
                              disabled={busy}
                              onClick={() =>
                                reviewFinding(
                                  finding.finding_id,
                                  "rejected",
                                )
                              }
                            >
                              Reject
                            </button>
                          </div>
                        )}
                      </article>
                    );
                  })}
                </div>
              )}
            </section>

            <section className="execution-section">
              <div className="section-heading-row">
                <div>
                  <div className="section-label">OBSERVABILITY</div>
                  <h2>Execution details</h2>
                </div>
              </div>

              <div className="execution-card">
                {Object.keys(run.stages).length === 0 ? (
                  <div className="execution-empty">
                    No stage execution metrics recorded yet.
                  </div>
                ) : (
                  Object.entries(run.stages).map(([stage, details]) => (
                    <div className="execution-row" key={stage}>
                      <div className="execution-stage">
                        <span className="execution-icon">
                          {details.status === "completed" ? "✓" : "•"}
                        </span>
                        <strong>{formatStage(stage)}</strong>
                      </div>

                      <span className={`execution-status ${details.status}`}>
                        {statusLabel(details.status)}
                      </span>

                      <span className="execution-error">
                        {details.error ?? "—"}
                      </span>
                    </div>
                  ))
                )}
              </div>
            </section>

            {run.error && (
              <div className="alert workflow-alert">
                <strong>Workflow error</strong>
                <span>{run.error}</span>
              </div>
            )}
          </>
        )}
      </main>

      <footer className="footer">
        <span>SuperDocs</span>
        <span>Durable document analysis &amp; human review</span>
      </footer>
    </div>
  );
}

export default App;