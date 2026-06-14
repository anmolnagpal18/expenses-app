# Architectural Decisions (ADR)

This document records the key architectural and technical decisions made for the Shared Expense Management Application.

---

## DR-01: Technical Stack Selection
- **Decision:** Build the backend using Django REST Framework (DRF) with PostgreSQL, and the frontend using React with Vite and Tailwind CSS.
- **Rationale:** 
  - Django REST Framework provides powerful validation, built-in ORM relationships, and rapid development capabilities.
  - PostgreSQL offers strong referential integrity, transaction support, and advanced queries necessary for robust financial and staging tables.
  - React/Vite provides a fast, lightweight, and modern Single Page Application (SPA) experience.
  - Tailwind CSS enables rapid custom styling without the overhead of heavy component libraries.

---

## DR-02: JWT Authentication Storage
- **Decision:** JWT access tokens and refresh tokens will be stored in frontend `localStorage`.
- **Rationale:** 
  - Since this is an internship assignment, using `localStorage` significantly reduces setup complexity, avoids CORS/Cookie domain configuration issues, and speeds up development.
  - Production-grade security measures (such as HttpOnly, Secure cookies, and CSRF protection) are noted as future improvements.

---

## DR-03: Balance Calculation - Direct Bilateral Balances
- **Decision:** Calculate peer-to-peer (bilateral) balances directly without a debt-simplification algorithm (Option A).
- **Rationale:**
  - The assignment prioritizes traceability ("Rohan: If the app says I owe ₹2300, I want to see exactly which expenses make that up").
  - Debt simplification introduces indirect transfers that make it very difficult to link a balance back to the specific real-world transactions that generated it.

---

## DR-04: Multi-Currency & Conversion
- **Decision:** Implement a Group Base Currency model with a Static Exchange Rate Registry (Option A).
- **Rationale:**
  - Tracking separate balances per currency (e.g. Alice owes Bob $10 and ₹500) makes group settlement difficult. Converting to a group base currency at entry simplifies calculations.
  - A static exchange rate registry database table avoids calling third-party APIs during imports or calculations. This eliminates external network dependencies, api keys, and rate volatility, making evaluation predictable and robust.
  - The exchange rate used is stored on the `Expense` at creation/import time to maintain historical accuracy.

---

## DR-05: CSV Import Staging Tables
- **Decision:** Implement a staging table approach (Option A) for CSV imports (`ImportBatch`, `ImportRow`, `ImportAnomaly`, `ImportResolution`).
- **Rationale:**
  - Importing raw rows directly into primary tables with a "flagged" status pollutes clean transaction histories and complicates balance calculations.
  - A staging area isolates raw, dirty data until a reviewer (Meera) corrects anomalies. Only when the batch is approved are actual `Expense` and `Settlement` records created in the primary database.

---

## DR-06: Distinct Settlement Entity
- **Decision:** Represent `Settlement` as a completely separate database table rather than an `Expense` with a special flag.
- **Rationale:**
  - Expenses (which add debt) and Settlements (which reduce debt) have completely different validation requirements.
  - A dedicated `Settlement` table enforces positive values, 1-to-1 relationships, active membership timelines, and simple queries. It also avoids complex conditional split logic checks that an unified model would require.

---

## DR-07: Dynamic Membership Date Enforcement
- **Decision:** Enforce membership date windows (`joined_at` to `left_at`) strictly on the backend (Option A).
- **Rationale:**
  - Restricts expense split participation to users whose active membership covers the transaction date.
  - This satisfies the requirement ("Why would March electricity affect my balance?").
  - Validation at the service layer prevents inconsistent splits.
