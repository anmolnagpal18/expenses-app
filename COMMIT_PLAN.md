# Commit Plan

This file outlines the sequential commit roadmap for the Shared Expense Management Application. Each commit is designed to represent a self-contained feature, documentation update, or architectural step.

## Commits Checklist

### Phase 1: Setup & Initial Documentation (Completed)
- [x] `docs: initial setup of AI_CONTEXT.md and COMMIT_PLAN.md`
- [x] `docs: update AI_CONTEXT with product discovery and domain model decisions`
- [x] `docs: update AI_CONTEXT with CSV import and anomaly detection specifications`
- [x] `docs: update AI_CONTEXT with technical architecture and system design`
- [x] `docs: finalize SCOPE.md, DECISIONS.md, AI_USAGE.md, README.md`

### Phase 2: Django Backend Foundation
- [x] `chore: initialize django project structure and postgres config`
- [x] `feat(users): implement custom user model and authentication foundation`
- [x] `test(auth): authentication API test coverage`
- [x] `feat(groups): implement group and membership models`
- [x] `test(groups): membership validation coverage`
- [x] `feat(groups): group management APIs and serializers`
- [x] `test(groups): API coverage for group endpoints`
- [ ] `feat: implement seed command for default users and exchange rate fixtures`

### Phase 3: Expense Split & Settlement Engines
- [x] `feat(expenses): implement expense and settlement domain models`
- [x] `test(expenses): add expense and settlement model validation coverage`
- [x] `feat(expenses): implement expense creation service and split engine`
- [x] `test(expenses): add split engine and expense service coverage`
- [x] `feat(expenses): implement expense creation APIs and serializers`

### Phase 4: Balance Calculation Engine
- [ ] `feat: implement bilateral balance calculation service (zero-sum, no simplify)`
- [ ] `test: unit tests for group and individual balance tracking formulas`

### Phase 5: CSV Import, Anomaly Engine & Resolutions
- [ ] `feat: build staging database tables for imports (batches, rows, anomalies)`
- [ ] `feat(imports): add import state machine`
- [ ] `feat: implement CSV parsing and basic structure validation`
- [ ] `feat: build anomaly detection checks (duplicates, timeline violations, unknown members)`
- [ ] `feat: build anomaly detection checks (settlement patterns, negative amounts, split issues)`
- [ ] `test: unit tests for parsing and anomaly engine detection accuracy`
- [ ] `feat: implement staging reviewer resolution actions (mapping, conversions, overrides)`
- [ ] `feat: implement staging transaction commit (staging to live data promotion)`

### Phase 6: System Reporting & Audit Logs
- [ ] `feat: implement audit logging hook and DB logger service`
- [ ] `feat: implement CSV and PDF import report generation APIs`
- [ ] `test: integration tests for complete import workflow to balance outputs`

### Phase 7: React Frontend - Foundations & Auth
- [ ] `chore: initialize react project with vite, tailwind, and router`
- [ ] `feat: build api axios client, auth contexts, login and signup pages`

### Phase 8: React Frontend - Core expense Management
- [ ] `feat: build groups dashboard, details, and membership timeline management`
- [ ] `feat: build expense forms with split configuration dynamic UI`
- [ ] `feat: build settlements recording and bilateral balance summary display`

### Phase 9: React Frontend - CSV Import & Review
- [ ] `feat: build CSV upload page, staging preview, and anomaly resolutions dashboard`
- [ ] `feat: build audit log viewer, import report summaries, and PDF download actions`

### Phase 10: Walkthrough & Deployment
- [ ] `docs: build final walkthrough.md and record deployment instructions`
