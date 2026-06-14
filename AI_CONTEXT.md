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

### CSV Import & Anomaly Detection Specifications

#### A. CSV File Structure
- **Required Columns:** `Date`, `Description`, `Amount`, `Currency`, `Paid By`, `Split Type`, `Participants`, `Split Values`, `Notes`
- **Optional Columns:** `Category`, `External Reference`, `Import Source`
- **User Identification:** Users are identified in CSV by name (e.g., Aisha, Rohan). 
  - *Matching Logic:* 1. Exact match -> 2. Case-insensitive match -> 3. Alias matching -> 4. Flag as "Unknown Member" anomaly.
  - *Constraint:* No automatic user creation on matching failure.

#### B. Anomaly Definitions & Confidence Signals
- **Duplicate Expense:** Identical `Date`, `Payer`, `Amount`, `Group`, `Participants`.
  - *High Confidence:* All fields match exactly.
  - *Medium Confidence:* Same date, similar description, amount difference < 5%.
  - *Action:* Flag for review. Never automatically delete.
- **Conflicting Duplicate Entry:** Appears to represent the same real-world event but with conflicting values (e.g., "Dinner at Marina" ₹2400 vs "Marina Dinner" ₹2450 on the same date).
  - *Action:* Reviewer chooses Keep A, Keep B, Keep Both, or Merge.
- **Settlement entered as Expense:** Detects if an expense actually represents debt repayment.
  - *Signals:* Keywords ("settle", "settlement", "repay", "reimbursement", "transfer", "paid back", "returned", "deposit paid"), only two participants, split pattern/notes implying repayment.
  - *Action:* Recommend "Convert to Settlement". Reviewer confirms.
- **Unknown Member:** CSV participant does not map to a database/group user.
  - *Action:* Reviewer can map to an existing user, create a new user, or skip the row.
- **Membership Timeline Violation:** Expense date falls outside active membership dates.
  - *Action:* Flag anomaly. Reviewer can remove member, adjust date, or keep and override.
- **Invalid Currency:** Currency missing or unsupported.
  - *Action:* Recommend group default currency (e.g., INR). Reviewer must approve or skip row.
- **Invalid Date:** Date is unparseable or ambiguous (e.g. `04-05-2026` could be April 5 or May 4).
  - *Action:* Require review/clarification.
- **Negative Amount:** Amount is negative (refund, correction, or error).
  - *Action:* Recommend "Convert to Refund Transaction" or "Keep Negative Expense".
- **Incorrect Split Configuration:**
  - Percentage Split: Sum != 100%.
  - Exact Split: Sum != total amount.
  - Share Split: Shares are negative or sum to 0.
  - Equal Split: Participants do not exist.
  - *Action:* Flag for manual correction.

#### C. Staging Table Workflow (Option A)
1. **Upload CSV** -> Creates `ImportBatch`.
2. **Parse Rows** -> Creates `ImportRow` records in staging tables.
3. **Run Validation Engine** -> Identifies anomalies and creates `ImportAnomaly` records.
4. **Interactive Review** -> User reviews staging data and selects resolutions. Resolutions are stored in `ImportResolution`.
5. **Approve Import** -> Converts valid/resolved staging records into live `Expense` and `Settlement` records.
6. **Generate Reports & Logs** -> Outputs downloadable reports and logs audit events.

#### D. Import Report Deliverables
- **Format:** Interactive UI view, downloadable PDF, and downloadable CSV.
- **Contents:**
  - *Summary:* Import date, uploader, total rows.
  - *Stats:* Successful rows, failed rows, warning rows, total anomalies found.
  - *Breakdown:* Count of anomalies by type.
  - *Resolution Summary:* Log of every anomaly detected and the action taken (who, what, when).
  - *Status:* Success, Partial Success, or Failed.

#### E. Audit Logs
- **Storage:** Stored in the database.
- **Events Logged:** CSV Uploaded, Anomaly Detected, User Mapping, Duplicate Merge, Settlement Conversion, Import Approved, Import Rejected, Expense Created, Settlement Created, Member Added, Member Removed.
- **Fields:** `id`, `actor`, `event_type`, `entity_type`, `entity_id`, `old_value`, `new_value`, `timestamp`.
- **Access Control:** Reviewers and Group Owners have full access; regular members have read-only access to audit events affecting their balances.

---

## 3. Architecture & Technical Decisions

### Tech Stack Layers (Backend)
- **Django REST Framework (DRF)**
- **Architecture Pattern:** Controller (API Views/Serializers) → Service Layer (Business Logic / Validations) → Repository Layer (Querying Database) → Database (PostgreSQL).
- **Core Benefit:** Complete separation of business rules (e.g. split engine, dynamic membership checks) from API endpoints. Highly testable.

### Tech Stack (Frontend)
- **React + Vite + Tailwind CSS**
- **Libraries:**
  - `React Router` (Routing)
  - `TanStack Query` (State & caching of API requests)
  - `Axios` (HTTP client)
  - `React Hook Form` (Form state & validation)

### Database Schema (Relational Tables)

#### `User`
- Standard Django auth User fields.

#### `Group`
- `id` (UUID)
- `name` (String)
- `base_currency` (String, default 'INR')
- `created_at` (Timestamp)

#### `Membership`
- `id` (UUID)
- `group_id` (FK → Group)
- `user_id` (FK → User)
- `joined_at` (Timestamp)
- `left_at` (Timestamp, nullable)

#### `StaticExchangeRate`
- `id` (Integer)
- `from_currency` (String, e.g. 'USD')
- `to_currency` (String, e.g. 'INR')
- `rate` (Decimal)

#### `Expense`
- `id` (UUID)
- `group_id` (FK → Group)
- `description` (String)
- `date` (Date)
- `original_amount` (Decimal)
- `converted_amount` (Decimal)
- `currency` (String)
- `exchange_rate` (Decimal)
- `split_type` (String: 'equal', 'percentage', 'exact', 'shares')
- `created_at` (Timestamp)

#### `ExpenseContribution`
- `id` (UUID)
- `expense_id` (FK → Expense)
- `user_id` (FK → User)
- `amount_paid` (Decimal)

#### `ExpenseSplit`
- `id` (UUID)
- `expense_id` (FK → Expense)
- `user_id` (FK → User)
- `share_value` (Decimal) -- e.g., percentage, share ratio, or exact amount
- `amount_owed` (Decimal)

#### `Settlement`
- `id` (UUID)
- `group_id` (FK → Group)
- `from_user_id` (FK → User)
- `to_user_id` (FK → User)
- `original_amount` (Decimal)
- `converted_amount` (Decimal)
- `currency` (String)
- `exchange_rate` (Decimal)
- `settlement_date` (Date)

#### `ImportBatch`
- `id` (UUID)
- `group_id` (FK → Group)
- `uploaded_by` (FK → User)
- `status` (String: 'pending_review', 'completed', 'failed')
- `created_at` (Timestamp)

#### `ImportRow`
- `id` (UUID)
- `batch_id` (FK → ImportBatch)
- `row_index` (Integer)
- `raw_data` (JSON)
- `status` (String: 'pending', 'resolved', 'ignored')

#### `ImportAnomaly`
- `id` (UUID)
- `row_id` (FK → ImportRow)
- `anomaly_type` (String)
- `severity` (String: 'high', 'medium', 'low')
- `message` (Text)
- `suggested_action` (String)

#### `ImportResolution`
- `id` (UUID)
- `row_id` (FK → ImportRow)
- `action_taken` (String)
- `resolved_by` (FK → User)
- `timestamp` (Timestamp)

#### `AuditLog`
- `id` (UUID)
- `actor` (FK → User)
- `event_type` (String)
- `entity_type` (String)
- `entity_id` (UUID)
- `old_value` (JSON, nullable)
- `new_value` (JSON, nullable)
- `timestamp` (Timestamp)

---

### Authentication Strategy
- **JWT Storage:** Tokens are stored in frontend `localStorage`.
- **JWT Lifetimes:** 
  - Access Token: 15 minutes
  - Refresh Token: 7 days
- **Registration:** Fully supported login and signup workflows.

---

### Balance Calculation (Option A: Direct Bilateral Balances)
- **Debt Simplification:** NOT used. Direct peer-to-peer calculations are done to maintain full traceability.
- **Calculation Formula:**
  - For any two users A and B in group G:
    - User A's net balance with User B is calculated as:
      `Sum(A's contributions split with B) - Sum(B's contributions split with A) + Sum(Settlements from B to A) - Sum(Settlements from A to B)`
  - **Membership boundaries:** Sums only run over periods where they both had active membership.
- **Traceability:** Every calculated balance must links directly to the detailed underlying transactions.

---

### Currency Conversion
- **Group Base Currency:** Groups declare a base currency (e.g. INR). 
- **Conversion at Entry:** Expenses added in non-base currency (e.g. USD) are converted to the base currency using a static database registry (`StaticExchangeRate`) at the time of creation.
- **Rate Retention:** Once an expense is saved, its rate and converted amount are frozen.

---

### Seed Command Configuration
- A Django admin seed command creates the default users:
  - Aisha, Rohan, Priya, Meera, Sam, Dev
  - Password: `Password@123`
  - Seed baseline static conversion rates (USD/EUR/GBP to INR).

---

## 4. Open Questions & Clarifications
*To be tracked during the interview.*
