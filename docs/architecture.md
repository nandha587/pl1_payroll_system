# Technical Architecture - PL/I Enterprise Payroll System

This document provides a highly rigorous, detailed technical specification of the data layouts, structure bindings, and financial computational formulas used in the system.

---

## 1. Input Dataset Mappings (Fixed-Width Columns)

All datasets mimic the standard **IBM Mainframe Fixed-Blocked (FB 80)** format, where each sequential record is exactly **80 bytes** in length, padded with spaces, and terminated by a newline.

### A. Employee Master Record (`employees.txt`)
- **Storage Ordering**: Sorted sequentially by `DEPT_NAME` (ascending, alphanumeric) and then by `EMP_ID` (ascending, alphanumeric).
- **PL/I Declaration Structure**:
  ```pli
  DCL 1 EMPLOYEE_RECORD,
        2 EMP_ID          CHAR(5),
        2 EMP_NAME        CHAR(25),
        2 DEPT_NAME       CHAR(10),
        2 BASIC_SALARY    FIXED DEC(7,2),
        2 TAX_PERCENT     FIXED DEC(4,2),
        2 FILLER          CHAR(27);
  ```

- **Precise Character Offsets**:

| Field Name | Data Type | Byte Start | Byte End | Column Width | Format / Examples |
|---|---|---|---|---|---|
| `EMP_ID` | `CHAR(5)` | 1 | 5 | 5 | Left-aligned, space-padded (`E0001`) |
| `EMP_NAME` | `CHAR(25)` | 6 | 30 | 25 | Left-aligned, space-padded (`James Smith`) |
| `DEPT_NAME` | `CHAR(10)` | 31 | 40 | 10 | Left-aligned, space-padded (`FINANCE   `) |
| `BASIC_SALARY` | `FIXED DEC(7,2)` | 41 | 48 | 8 | Zero-padded string (`04500.00`) |
| `TAX_PERCENT` | `FIXED DEC(4,2)` | 49 | 53 | 5 | Zero-padded string (`15.00`) |
| `FILLER` | `CHAR(27)` | 54 | 80 | 27 | Space padding for FB-80 compliance |

---

### B. Attendance Record (`attendance.txt`)
- **Storage Ordering**: Sorted sequentially by `DEPT_NAME` (derived from Master) and `EMP_ID` (ascending, alphanumeric).
- **PL/I Declaration Structure**:
  ```pli
  DCL 1 ATTENDANCE_RECORD,
        2 ATT_ID          CHAR(5),
        2 OVERTIME_HOURS  FIXED BIN(15),
        2 ATTENDANCE_DAYS FIXED BIN(15),
        2 FILLER          CHAR(65);
  ```

- **Precise Character Offsets**:

| Field Name | Data Type | Byte Start | Byte End | Column Width | Format / Examples |
|---|---|---|---|---|---|
| `ATT_ID` | `CHAR(5)` | 1 | 5 | 5 | Left-aligned, space-padded (`E0001`) |
| `OVERTIME_HOURS` | `FIXED BIN(15)` | 6 | 10 | 5 | Zero-padded decimal (`00012`) |
| `ATTENDANCE_DAYS` | `FIXED BIN(15)` | 11 | 15 | 5 | Zero-padded decimal (`00021`) |
| `FILLER` | `CHAR(65)` | 16 | 80 | 65 | Space padding for FB-80 compliance |

---

## 2. Computational Formulas & Arithmetic Rules

All financial calculations are implemented inside `salary_calculator.pli` using standard fixed-point decimal scaling to prevent floating-point binary rounding errors:

### A. Base Salary Adjustment
Adjusts the basic monthly salary based on the actual attendance days compared to the standard 22-day monthly calendar.
$$\text{Base Salary} = \text{Basic Salary} \times \left( \frac{\text{Attendance Days}}{22.00} \right)$$
*In PL/I, integer days are cast explicitly to decimal using `DEC(ATT_DAYS, 4, 2)` before scaling division.*

### B. Overtime Premium Pay
Assumes standard monthly working hours equal 176 (22 days * 8 hours). Overtime hours are compensated at a 1.5x multiplier.
$$\text{Hourly Rate} = \frac{\text{Basic Salary}}{176.00}$$
$$\text{Overtime Pay} = \text{Hourly Rate} \times \text{Overtime Hours} \times 1.50$$

### C. Gross Salary Payout
$$\text{Gross Salary} = \text{Base Salary} + \text{Overtime Pay}$$

### D. Deductions
1. **Tax Deduction**: Calculated based on the individual tax slab percentage.
   $$\text{Tax Deduction} = \text{Gross Salary} \times \left( \frac{\text{Tax Percent}}{100.00} \right)$$
2. **Provident Fund (PF) Deduction**: Flat 8.00% employee salary deduction rate.
   $$\text{PF Deduction} = \text{Gross Salary} \times 0.08$$

### E. Net Salary Payout
$$\text{Net Salary} = \text{Gross Salary} - \text{Tax Deduction} - \text{PF Deduction}$$
