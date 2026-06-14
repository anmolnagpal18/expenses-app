# AI Usage & Collaboration Guidelines

This document outlines the guidelines for AI-human collaboration during the development of the Shared Expense Management Application.

---

## 1. Core Workflow Principles
- **Documentation First:** All system changes, architecture layouts, and requirements must be documented in `AI_CONTEXT.md` first. It serves as the single source of truth (SSOT).
- **No Large Commits:** Never generate a single massive commit. Every self-contained feature, refactor, or documentation update must have its own commit.
- **No Premature Code:** Do not write implementation code until architecture designs are explicitly reviewed and approved by the user.
- **Traceability:** Prioritize simple, clean code over clever optimizations. Every module must be easily explainable during a technical interview.

---

## 2. Commit Strategy & Message Rules
- Suggest commit messages throughout development before running them.
- Follow the Conventional Commits specification:
  - `feat: ...` for new features
  - `fix: ...` for bug fixes
  - `docs: ...` for documentation
  - `test: ...` for adding/modifying tests
  - `chore: ...` for configuration or setup updates
- Keep the `COMMIT_PLAN.md` file updated, checking off items as they are committed.

---

## 3. Review & Verification
- Prioritize test-driven behaviors. Write unit tests for core services (e.g. balance calculations, CSV parse rules, anomaly detection) to verify edge cases.
- Walkthroughs: Update the walkthrough documentation to record manual checks, API payloads, and UI screen changes.
