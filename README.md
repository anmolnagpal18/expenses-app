# Shared Expense Management Application (Splitwise Clone)

A web application built to manage shared expenses for groups where membership can change dynamically over time. This application supports roommates tracking ongoing household expenses and temporary groups tracking trips or vacations, featuring a robust CSV import and anomaly detection engine.

## 🚀 Tech Stack

- **Backend:** Django REST Framework, PostgreSQL
- **Frontend:** React, Vite, Tailwind CSS, TanStack Query, Axios
- **Authentication:** JWT (Stored in localStorage)
- **Deployment:** Render (Backend & PostgreSQL), Vercel (Frontend)

---

## 🛠️ Key Features

1. **User Authentication:** Sign up, Login, and JWT-based session security.
2. **Dynamic Group Memberships:** Add and remove members with explicit activation windows. Validation prevents charging members for expenses outside their active periods.
3. **Multi-Payer Expense Splits:** Record expenses paid by multiple members, split using custom strategies (Equal, Percentage, Exact Amount, Shares/Ratios).
4. **Group Settlements:** Record direct peer-to-peer payments to resolve debts.
5. **Direct Bilateral Balances:** Every balance is calculated directly between pairs of users for complete traceability.
6. **CSV Import & Anomaly Staging:** Upload messy CSV spreadsheets, staging transactions before they affect balances.
7. **Anomaly Detection Engine:** Flags duplicate expenses, conflicting duplicates, settlement patterns, unknown members, date conflicts, and membership timeline violations.
8. **Interactive Review Workflow:** Resolves anomalies with options to map users, convert items to settlements, merge duplicates, or override constraints.
9. **Import Reports & Audit Logs:** Generates PDF/CSV summaries of imports and tracks system actions in a database-backed audit log.

---

## 📁 Repository Structure

```
├── backend/               # Django REST Framework backend
├── frontend/              # React + Vite frontend
├── tests/
│   └── data/              # Test CSV datasets (expenses_export.csv, etc.)
├── README.md              # Project introduction and quickstart
├── AI_CONTEXT.md          # AI partner context (Single Source of Truth)
├── SCOPE.md               # Detailed product feature scope
├── DECISIONS.md           # Architecture Decision Records (ADR)
├── AI_USAGE.md            # Guidelines for AI code generation and usage
└── COMMIT_PLAN.md         # Step-by-step commit roadmap
```

---

## 🚦 Quick Start (Local Setup)

*Detailed setup commands and configuration parameters will be documented as backend and frontend packages are initialized.*
