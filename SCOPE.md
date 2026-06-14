# Scope: Shared Expense Management Application

## 1. Product Goals
The primary purpose is to manage shared expenses for groups with dynamic membership. The application is tailored for:
1. Long-term groups (e.g. roommates managing ongoing rent, utilities, groceries).
2. Short-term groups (e.g. trips, dinners, specific events).
3. Data reviewers importing historical data spreadsheets.

---

## 2. In-Scope Features (MVP)

### A. Authentication & User Management
- JWT Authentication (Access token: 15 mins, Refresh token: 7 days) stored in `localStorage`.
- User registration (Sign Up) and Login.
- Database seeder command to create default evaluation users (Aisha, Rohan, Priya, Meera, Sam, Dev) with default credentials.

### B. Group & Membership Management
- Create and manage groups.
- Set a group's base currency (e.g. INR).
- Add/remove members with explicit `joined_at` and `left_at` (nullable) timestamps.
- Support multiple membership periods (intervals) for the same user in the same group (re-joining).
- Allow members to leave groups even with a non-zero balance. Balance calculations continue dynamically based on historical participation.

### C. Expense split Engine
- Record expenses within groups.
- Multiple payers: Support paying via multiple contributors (tracked via `ExpenseContribution`).
- Extensible split strategies:
  1. **Equal Split:** Divided evenly.
  2. **Percentage Split:** Split by percentage values summing to 100%.
  3. **Exact Split:** Split by exact amounts summing to total expense amount.
  4. **Shares/Ratios Split:** Split by relative parts (shares).
- Transaction currency conversion: If an expense currency differs from the group base currency, convert using a static exchange rate stored in the database.

### D. Settlement Tracking
- Separate `Settlement` entity (not an expense).
- One-payer, one-receiver, positive amounts, belongs to a group.
- Restrict settlements to users who were active group members at the time of the settlement date.
- Settlements immediately update balances (no confirmation/approval required).

### E. Balance Calculation Engine
- Calculate direct peer-to-peer (bilateral) balances.
- No debt simplification algorithm (optimizations are excluded to ensure balances are fully traceable).
- Enforce membership dates: Users are only charged for expenses occurring within their active membership periods.
- Group balances must always sum to zero.

### F. CSV Import & Staging Engine
- Parse CSV files with columns: `Date`, `Description`, `Amount`, `Currency`, `Paid By`, `Split Type`, `Participants`, `Split Values`, `Notes`, `Category`, `External Reference`, `Import Source`.
- Stage uploads in database tables (`ImportBatch`, `ImportRow`, `ImportAnomaly`) before committing to group balances.
- Run a multi-check validation engine to detect anomalies.

### G. Anomaly Detection
Detect and flag:
- Duplicate expenses (high/medium confidence levels).
- Conflicting duplicate entries (same date/description, different amounts/splits).
- Settlement patterns entered as expenses (identified by keyword patterns and two-participant splits).
- Unknown members (unmapped names).
- Membership timeline violations (transaction dates outside a user's membership dates).
- Invalid/missing currencies and unparseable dates.
- Negative amounts.
- Bad splits (sums not matching).

### H. Review Workflow & Reports
- Interactive UI to resolve anomalies row-by-row (merge duplicates, map unknown users, convert expenses to settlements, override membership boundaries, etc.).
- Generate detailed interactive reports with options to download as PDF and CSV summaries.
- Log all actions into a DB-backed `AuditLog` (Actor, Event, Entities, Timestamp).

---

## 3. Out of Scope (Future Improvements)
- **Business Expense Reporting:** Mileage tracking, corporate approvals, tax receipts, and business expense reimbursement.
- **Direct 1-on-1 Expenses:** All expenses must belong to a group. One-on-one balances outside a group are excluded.
- **Automated Anomaly Correction:** The system will never silently modify or delete data; human review is mandatory.
- **Settlement Verification Workflow:** Receiver approval of settlements is excluded; settlements affect balances immediately.
- **Live Currency API Integration:** Real-time exchange rate API integration is excluded in favor of a static rate registry in the database.
