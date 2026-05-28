# Sequential Multi-File Reconciliation Logic

This document describes the multi-file matching algorithm and data correction protocols used by the PL/I batch reconciliation system.

---

## 1. The Match-Merge Sequential Algorithm

The core program logic inside `payroll_main.pli` utilizes the classic single-pass sorted sequential match-merge algorithm. By assuming that both files are sorted by Department and Employee ID, we can read both streams concurrently in a single linear pass $O(N)$ with a constant memory footprint of $O(1)$.

### Sequential Matching Matrix

Let $K_{emp}$ be the key (Department + Employee ID) of the current Master record.
Let $K_{att}$ be the key (Department + Employee ID) of the current Attendance transaction record.

| Condition | Match State | Program Action | Code |
|---|---|---|---|
| **$K_{emp} = K_{att}$** | **Perfect Match** | Validate record fields. If valid, calculate pay and print detail row. Advance both streams. | `SUCCESS` |
| **$K_{emp} < K_{att}$** | **Unmatched Master** | The master record has no transaction data. Log exception and increment totals. Advance **Master** stream only. | `ERR-101` |
| **$K_{emp} > K_{att}$** | **Orphan Transaction** | Attendance data exists for an unregistered ID. Log exception. Advance **Attendance** stream only. | `ERR-102` |

---

## 2. Standardized Exception Categories

When validation or reconciliation discrepancies are detected, standard mainframe error codes are logged to `error_log.txt`:

### A. Integrity Exceptions (Reconciliation Mismatch)
These error codes indicate that the two sequential input files do not match at the structural level.

- **`ERR-101` (Attendance Record Missing)**:
  - *Trigger*: An employee exists in the Master database but has no corresponding record in the Attendance Log.
  - *Business Impact*: Unpaid employee. Suggests that the employee did not file their monthly timesheet or their log was lost.
  - *Audit Action*: Flag to payroll officer to manually input timesheet details before rerun.

- **`ERR-102` (Orphan Record - Master Missing)**:
  - *Trigger*: An attendance record is encountered for an Employee ID that does not exist in the Master database.
  - *Business Impact*: Potential security risk or ghost employee scam.
  - *Audit Action*: Immediately investigate the source of the attendance timesheet. Confirm if the employee was recently hired and not yet registered in the Master.

---

### B. Validation Exceptions (Duplicate Entries)
Duplicate keys invalidate sequential processing and represent serious administrative errors.

- **`ERR-103` (Duplicate Master Entry)**:
  - *Trigger*: The current Employee Master record has the same ID as the preceding record.
  - *Business Impact*: Database integrity failure.
  - *Audit Action*: Purge duplicate, verify salary details with HR.

- **`ERR-104` (Duplicate Attendance Entry)**:
  - *Trigger*: The current Attendance record has the same ID as the preceding record.
  - *Business Impact*: Risk of double-paying an employee for overtime and base work.
  - *Audit Action*: Cross-reference original paper timesheets to resolve the duplication.

---

### C. Boundary Validation Exceptions (Field Integrity)
These errors indicate that the transaction data fields violate physical business bounds.

- **`ERR-201` (Negative or Zero Salary)**:
  - *Trigger*: Basic Salary is $\le 0.00$.
  - *Business Impact*: Impossible salary calculation, violates labor compliance.
  
- **`ERR-202` (Out-of-bounds Tax Percent)**:
  - *Trigger*: Tax slab is negative or exceeds 50.00%.
  
- **`ERR-203` (Out-of-bounds Overtime Hours)**:
  - *Trigger*: Overtime exceeds the monthly ceiling of 80 hours.
  
- **`ERR-204` (Out-of-bounds Attendance Days)**:
  - *Trigger*: Working days are negative or exceed 31 calendar days.
