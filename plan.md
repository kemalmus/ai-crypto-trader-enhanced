## Relevant Files

- `analysis/consultant_agent.py` - Implements Grok-fast consultant logic for proposal review.
- `analysis/llm_advisor.py` - Produces proposals and reconciles consultant feedback.
- `runner/daemon.py` - Coordinates signal handling, two-agent loop, and execution flow.
- `storage/db.py` - Persists trades, events, sentiment; needs rationale column and logging hooks.
- `configs/app.yaml` - Extends symbol universe and consultation parameters.
- `logging/setup.py` - Ensures enhanced logging formatting and new tags.
- `tests/test_consultant_agent.py` - Validates consultant agent behavior and fallback.
- `tests/test_daemon_workflow.py` - Covers end-to-end consultation flow and event logging.
- `tests/test_storage.py` - Confirms decision rationale persistence.
- `cli/__main__.py` - Surfaces new logging filters or status data if needed.

### Notes

- Coordinate OpenRouter Grok-fast usage with existing DeepSeek advisor settings; reuse shared timeout/retry utilities.
- When altering the schema, provide idempotent migrations and update initialization SQL in `storage/db.py`.
- Keep logging payloads JSON-serializable and align tag names with `replit.md` conventions (`PROPOSAL_MAIN`, `PROPOSAL_CONSULTANT`, `DECISION_FINAL`).
- Run `ruff check .`, `ruff format .`, `pyright`, `pytest -q`, and `agent run --once --dry-run` before completion.
- Document configuration additions and new commands in `replit.md` after implementation.

## Tasks

- [ ] 1.0 Roll Out Consultant Agent Foundations
  - [ ] 1.1 Define Grok-fast prompt, request payload, and response schema aligned with Task 4 requirements.
  - [ ] 1.2 Implement async consultant module in `analysis/consultant_agent.py` with timeout, retries, and structured output.
  - [ ] 1.3 Integrate logging hooks and error handling, ensuring auto-approve fallback on failure.
  - [ ] 1.4 Add targeted unit tests (e.g., mocked OpenRouter) covering approve/reject/timeout paths.

- [ ] 2.0 Orchestrate Main/Consultant Trade Workflow
  - [ ] 2.1 Extend `analysis/llm_advisor.py` to surface proposal metadata and ingest consultant feedback.
  - [ ] 2.2 Update `runner/daemon.py` trade loop to call consultant review, reconcile decisions, and pass decision_id through events.
  - [ ] 2.3 Persist full review chain to `event_log` with new tags/actions and ensure failure modes skip execution safely.
  - [ ] 2.4 Backfill integration tests or async workflow tests validating approve/reject/modify branches.

- [ ] 3.0 Capture Decision Rationale in Storage Layer
  - [ ] 3.1 Introduce `decision_rationale` column to `trades` table and update schema management code.
  - [ ] 3.2 Serialize combined TA, sentiment, proposal, and consultant context when opening or closing trades.
  - [ ] 3.3 Add database/unit tests ensuring rationale persisted and retrievable via API/CLI queries.

- [ ] 4.0 Broaden Market Coverage to Eight Symbols
  - [ ] 4.1 Update symbol configuration (likely `configs/app.yaml` and daemon defaults) to include SOL, AVAX, MATIC, LINK, UNI, AAVE.
  - [ ] 4.2 Verify CCXT adapter compatibility and adjust exchange selection if pairs unavailable.
  - [ ] 4.3 Confirm warm-up, indicator computation, and sentiment collection scale to expanded universe via targeted tests.

- [ ] 5.0 Raise Observability and Transparency
  - [ ] 5.1 Enhance signal, sentiment, and consultation logging per Task 8 examples in daemon and logging setup.
  - [ ] 5.2 Ensure CLI log filters recognize new tags and provide human-readable summaries.
  - [ ] 5.3 Update documentation (`replit.md`, `AGENTS.md`) with logging/consultation changes.

- [ ] 6.0 Prove Stability with End-to-End Validation
  - [ ] 6.1 Execute the scripted scenarios from Task 9, capturing evidence (logs, DB queries, JSONL snippets).
  - [ ] 6.2 Record results of linting, typing, tests, and dry-run cycle; address regressions promptly.
  - [ ] 6.3 Summarize outcomes and residual risks in progress tracking or documentation.


