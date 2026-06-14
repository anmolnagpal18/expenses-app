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
- [x] `test(expenses): add expense API coverage`


### Phase 4: Balance Calculation Engine & Settlements
- [x] `feat(balances): implement bilateral balance calculation engine`
- [x] `test(balances): add bilateral balance engine coverage`
- [x] `feat(settlements): implement settlement APIs and serializers`
- [x] `test(settlements): settlement API coverage`

### Phase 5: CSV Import & Anomaly Engine
- [x] `feat(imports): staging import models`
- [x] `test(imports): staging model coverage`
- [x] `feat(imports): CSV upload and parser`
- [x] `test(imports): parser coverage`
- [ ] `feat(imports): anomaly detection engine`
- [ ] `test(imports): anomaly detection coverage`

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
