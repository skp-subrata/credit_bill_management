# Hospital Credit Billing Management System (v1.0.0)

An enterprise-grade Flask web application designed for hospital credit billing management, HIS data synchronization, SLA/TAT tracking, payer-pair rule configuration, and centralized data uploads.

---

## 🌟 Key Features (v1.0.0)

- **Centralized Data Upload Module (`/admin/data-upload`)**:
  - Bulk ingestion engine for 10 master and transaction categories (`hospital_units`, `payers`, `hospital_payers`, `patients`, `doctor_master`, `bills`, `bill_verifications`, `bill_dispatch`, `bill_queries`, `bill_payments`).
  - Dynamic `.xlsx` and `.csv` template generation.
  - Multi-stage validation: Required headers, duplicate detection, data type checks, and master dependency verification.
  - Strict RBAC: Accessible only to `Super Admin` and `Admin` roles.
  - Audit logging via `AdminUploadHistory` with downloadable error CSV reports.

- **Dynamic Payer SLA & Monthly Submission TAT Logic**:
  - Configurable `monthly_submission` boolean per Payer-Pair combination.
  - TAT starts from 1st of following month when `monthly_submission = Yes`.

- **Dispatch Date SLA Restriction (`/billing/bills/<id>`)**:
  - Minimum allowed dispatch date set to `Today - 3 days` (disabling earlier dates) up to `Today`.

- **Lifecycle Stage Derived Bill Status**:
  - Bill status dynamically derived from the highest completed stage in the billing lifecycle (`UNVERIFIED` → `VERIFIED` → `DISPATCHED` → `QUERY_RAISED` / `QUERY_RESOLVED` → `SETTLED`).

- **Automatic High-Contrast Theme System**:
  - Supports 5 distinct themes: `🌙 Dark` (Default), `☀️ Light` (Clinical Clean with WCAG AAA high-contrast text), `🔘 Slate Gray`, `🌿 Emerald Green`, and `👑 Royal Indigo`.

---

## 🚀 Setup & Execution Instructions

1. **Clone Repository & Activate Virtual Environment:**
   ```bash
   git clone https://github.com/skp-subrata/credit_bill_management.git
   cd credit_bill_management
   .venv\Scripts\Activate.ps1   # Windows PowerShell
   # source .venv/bin/activate  # Linux/macOS
   ```

2. **Install Frozen Dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Initialize Database & Seed Data:**
   ```bash
   python seed.py
   ```

4. **Run Application:**
   ```bash
   python app.py
   ```
   Open browser at `http://127.0.0.1:5000/`.

---

## 📦 Version Release Info

- **Current Version**: `v1.0.0`
- **Release Tag**: `v1.0.0`
- **Frozen Dependencies**: Stored in `requirements.txt`

