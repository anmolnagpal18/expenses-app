# AI Context: Shared Expense Management Application

## Project Overview
A Shared Expense Management Application similar to Splitwise, developed as a Software Engineering Internship Assignment.

## Document Status
- **Last Updated:** 2026-06-14
- **Current Phase:** Product & Requirements Discovery (Interview)

---

## 1. Product Discovery

### Product Goals
- **Core Objective:** Manage shared expenses for groups where membership can change dynamically over time.
  - Supports roommates managing ongoing household expenses (rent, utilities, groceries, etc.).
  - Supports temporary groups (trips, vacations, events).
  - Must calculate balances correctly when members join or leave groups.
  - **Exclusion:** Not intended for business expense reimbursement or corporate accounting.
- **CSV Import & Anomaly Detection:**
  - Import historical expense records from messy spreadsheets.
  - Detect inconsistencies/data quality issues and surface them to users (transparency over automation).
  - Allow users to review and approve/reject corrections.
  - Maintain a complete audit trail of all actions and decisions.
  - **No Silent Modification:** The system must never silently modify data.

### User Personas
- **Persona A (Casual Expense Splitter):** Friends splitting bills (dinners, trips, events). Needs fast expense entry, equal/percentage splits, clear balances, and a mobile-responsive interface. Primary goal: Know who owes whom and settle quickly.
- **Persona B (Household / Roommate Manager):** Long-term living arrangements (flatmates, shared apartments). Needs ongoing expense tracking, dynamic membership dates (join/leave dates), utility/recurring expenses, detailed balance breakdowns, and history. Primary goal: Maintain fair and accurate balances over time.
- **Persona C (Data Reviewer / Meera):** User responsible for reviewing imports. Needs visibility into anomalies, approval/rejection workflows, audit history, and import reports. Primary goal: Ensure imported data remains trustworthy.

### Success Criteria
- **Functional Success:**
  1. Group creation and management.
  2. Tracking membership changes (dates of joining/leaving).
  3. Expense creation, updates, and deletion.
  4. Record settlements.
  5. Multiple split types (e.g., equal, percentage).
  6. Accurate group and individual balances.
  7. Historical CSV imports.
  8. Every anomaly surfaced to users; none silently ignored.
  9. Detailed import reports generated for every import.
  10. Complete action auditability.
- **Balance Calculation Success:**
  - `Total Credits = Total Debits` (Group balance sum = 0).
  - Membership dates respected (users charged only for expenses during active membership).
  - Consistent currency conversion.
  - Minimization and documentation of rounding errors.
- **Technical Success:**
  - **Backend:** Django REST Framework, PostgreSQL.
  - **Frontend:** React, Vite, Tailwind CSS.
  - **Auth:** JWT.
  - **Deployment:** Publicly deployed backend and frontend.
  - **Performance Targets:** CSV imports <10s for the assignment dataset, dashboard load <3s, and fast API response times.
- **CSV Import Success:**
  1. File structure validation passes.
  2. All anomalies detected and surfaced.
  3. Suggested actions displayed.
  4. User approvals recorded.
  5. Imported data stored correctly.
  6. Import report generated.
  7. Audit log generated.

---

## 2. Product Scope & Features

### Core Entities & Domain Decisions

#### A. Dynamic Group Memberships
- **Join/Leave Date Logic (Option A):** 
  - Every membership record contains `joined_at` and `left_at` (nullable).
  - A member can only participate in expenses whose transaction date falls within their active membership period.
  - **Backend Enforcement:** Mandatory backend validation to reject expenses outside a user's active membership period.
- **Leaving with Non-Zero Balances:**
  - Allowed. Inactive members can leave with non-zero balances.
  - The debt continues to exist, and balances are calculated using historical expenses and settlements.
  - Inactive users are excluded from *future* expenses but remain part of past balance calculations.
- **Re-joining:**
  - Allowed. A user can leave and rejoin the same group later, creating multiple active membership periods (multiple records in the database).

#### B. Expense Models & Splits
- **All Expenses in Groups:** Every expense must belong to a group. Direct one-to-one expenses outside a group are out of scope.
- **Multiple Payers:** Supported. An expense can be paid by multiple people.
  - *Structure:* Tracked via an `ExpenseContribution` model (who paid what portion) rather than a single `paid_by` field.
- **Supported Split Types:**
  1. **Equal Split:** Calculated evenly among all split participants.
  2. **Percentage Split:** Split specified as percentages (must sum to 100%).
  3. **Exact Amount Split:** Split specified as exact amounts (must sum to total expense amount).
  4. **Shares/Ratio Split:** Split specified in shares/ratios (total shares calculated dynamically).
  - *Extensibility:* The database schema must use a flexible design (e.g., `Expense`, `ExpenseSplit`, `SplitStrategy`) to support new split types.

#### C. Settlements
- **Data Representation:** Separate entity from `Expense`.
  - fields: `from_user`, `to_user`, `amount`, `currency`, `settlement_date`, `group`.
- **Validation Rules:**
  - Positive amounts only.
  - Exactly one payer (`from_user`) and one receiver (`to_user`).
  - No split strategies or distributions.
  - Cannot reference inactive users at the time of settlement date (cannot settle if outside active membership period).
  - Must belong to a group.
- **Verification Workflow:**
  - No approval workflow required; settles immediately affect balances.
  - Triggers recalculation, adds to history, and logs to audit.

#### D. Balance Rules
1. **Zero-Sum:** Group balances must always sum to zero (`Total Credits = Total Debits`).
2. **Historical Persistence:** Historical expenses remain valid even after a member leaves.
3. **Period Boundaries:** Membership periods only affect future participation.
4. **Settlement Modification:** Settlements reduce balances but never modify expense history.
5. **Pre-conversion:** Currency conversion should occur before balance calculations.
6. **Traceability:** Every balance must be traceable to underlying expenses and settlements.

---

## 3. Architecture & Technical Decisions
*To be detailed after we complete the requirements interview.*

---

## 4. Open Questions & Clarifications
*To be tracked during the interview.*
