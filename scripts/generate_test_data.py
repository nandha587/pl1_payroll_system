#!/usr/bin/env python3
"""
generate_test_data.py
Generates realistic, fixed-width sequential datasets for the PL/I Payroll Processing System.
Both files are sorted by Department and Employee ID to support sequential control-break and reconciliation logic.
"""
import os
import random

# Base directory setup
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

EMPLOYEES_FILE = os.path.join(DATA_DIR, "employees.txt")
ATTENDANCE_FILE = os.path.join(DATA_DIR, "attendance.txt")

DEPARTMENTS = ["FINANCE", "HR", "SALES", "IT", "OPS"]

# Setup deterministic random numbers
random.seed(42)

# Raw list of realistic names to sample from
FIRST_NAMES = ["James", "Mary", "John", "Patricia", "Robert", "Jennifer", "Michael", "Elizabeth", "William", "Linda", 
               "David", "Barbara", "Richard", "Susan", "Joseph", "Jessica", "Thomas", "Sarah", "Charles", "Karen",
               "Christopher", "Lisa", "Daniel", "Nancy", "Matthew", "Betty", "Anthony", "Sandra", "Mark", "Margaret"]
LAST_NAMES = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Rodriguez", "Martinez",
              "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson", "Thomas", "Taylor", "Moore", "Jackson", "Martin"]

def generate_name():
    return f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"

def main():
    print("Generating sorted sequential datasets for PL/I Payroll Processing System...")
    
    # 1. Create a pool of valid records grouped by department
    emp_counter = 1
    records_by_dept = {dept: [] for dept in DEPARTMENTS}
    
    # Generate ~500 employees spread across departments
    for dept in DEPARTMENTS:
        dept_size = random.randint(95, 105)
        for _ in range(dept_size):
            emp_id = f"E{emp_counter:04d}"
            name = generate_name()
            basic_salary = round(random.uniform(2500.00, 8500.00), 2)
            tax_percent = round(random.choice([10.00, 12.50, 15.00, 20.00, 22.00, 25.00]), 2)
            
            records_by_dept[dept].append({
                "emp_id": emp_id,
                "name": name,
                "dept": dept,
                "basic_salary": basic_salary,
                "tax_percent": tax_percent,
                "overtime_hours": random.randint(0, 25),
                "attendance_days": random.randint(18, 22)
            })
            emp_counter += 1

    # Define validation and reconciliation anomaly targets
    anomalies = [
        # A1: Duplicate employee in Master file
        {"type": "dup_master", "dept": "HR", "emp_id": "E0110", "name": "Duplicate HR Master", "basic_salary": 4500.00, "tax_percent": 15.00},
        # A2: Duplicate employee in Attendance file
        {"type": "dup_attendance", "dept": "IT", "emp_id": "E0320", "overtime_hours": 10, "attendance_days": 20},
        # A3: Negative Basic Salary
        {"type": "neg_salary", "dept": "SALES", "emp_id": "E0250"},
        # A4: Invalid Tax Percentage (too high)
        {"type": "invalid_tax", "dept": "IT", "emp_id": "E0340"},
        # A5: Negative Overtime Hours
        {"type": "neg_overtime", "dept": "OPS", "emp_id": "E0440"},
        # A6: Excessive Attendance Days (>31)
        {"type": "excess_attendance", "dept": "FINANCE", "emp_id": "E0050"},
        # A7: Missing Employee Master (present in attendance, missing in master)
        {"type": "missing_master", "dept": "FINANCE", "emp_id": "E0999", "overtime_hours": 15, "attendance_days": 21},
        # A8: Missing Attendance Record (present in master, missing in attendance)
        {"type": "missing_attendance", "dept": "OPS", "emp_id": "E0480"},
    ]

    master_list = []
    attendance_list = []

    # Assemble records into master and attendance lists, inserting anomalies in-order
    for dept in DEPARTMENTS:
        dept_records = records_by_dept[dept]
        
        # Sort dept records by employee ID to ensure strict sequential order
        dept_records.sort(key=lambda x: x["emp_id"])
        
        for rec in dept_records:
            emp_id = rec["emp_id"]
            
            # Anomaly checks
            if any(a["type"] == "neg_salary" and a["emp_id"] == emp_id for a in anomalies):
                rec["basic_salary"] = -3200.00
            if any(a["type"] == "invalid_tax" and a["emp_id"] == emp_id for a in anomalies):
                rec["tax_percent"] = 55.00
            if any(a["type"] == "neg_overtime" and a["emp_id"] == emp_id for a in anomalies):
                rec["overtime_hours"] = -5
            if any(a["type"] == "excess_attendance" and a["emp_id"] == emp_id for a in anomalies):
                rec["attendance_days"] = 35

            # Anomaly: Missing Attendance (We omit writing it to attendance_list)
            if any(a["type"] == "missing_attendance" and a["emp_id"] == emp_id for a in anomalies):
                master_list.append(rec)
                continue

            # Standard path: write both master and attendance
            master_list.append(rec)
            attendance_list.append({
                "emp_id": rec["emp_id"],
                "dept": rec["dept"],
                "overtime_hours": rec["overtime_hours"],
                "attendance_days": rec["attendance_days"]
            })
            
            # Anomaly: Duplicate Master
            for a in anomalies:
                if a["type"] == "dup_master" and a["emp_id"] == emp_id and a["dept"] == dept:
                    master_list.append({
                        "emp_id": a["emp_id"],
                        "name": a["name"],
                        "dept": a["dept"],
                        "basic_salary": a["basic_salary"],
                        "tax_percent": a["tax_percent"]
                    })
            
            # Anomaly: Duplicate Attendance
            for a in anomalies:
                if a["type"] == "dup_attendance" and a["emp_id"] == emp_id and a["dept"] == dept:
                    attendance_list.append({
                        "emp_id": a["emp_id"],
                        "dept": a["dept"],
                        "overtime_hours": a["overtime_hours"],
                        "attendance_days": a["attendance_days"]
                    })

    # Anomaly: Missing Master (present in attendance, missing in master)
    for a in anomalies:
        if a["type"] == "missing_master":
            finance_indices = [i for i, att in enumerate(attendance_list) if att["dept"] == "FINANCE"]
            last_finance_idx = finance_indices[-1] if finance_indices else 0
            attendance_list.insert(last_finance_idx + 1, {
                "emp_id": a["emp_id"],
                "dept": "FINANCE",
                "overtime_hours": a["overtime_hours"],
                "attendance_days": a["attendance_days"]
            })

    # Sort final lists to ensure perfect alignment by Department, then by Employee ID
    master_list.sort(key=lambda x: (x["dept"], x["emp_id"]))
    attendance_list.sort(key=lambda x: (x["dept"], x["emp_id"]))

    # 2. Write Master File (employees.txt) as fixed-width records of exactly 80 chars
    # Structure: EMP_ID (5), Name (25), Dept (10), Basic (8), Tax (5), Filler (27)
    with open(EMPLOYEES_FILE, "w", encoding="utf-8") as f_emp:
        for emp in master_list:
            emp_id_str = f"{emp['emp_id']:<5}"
            name_str = f"{emp['name']:<25}"[:25]
            dept_str = f"{emp['dept']:<10}"
            basic_str = f"{emp['basic_salary']:08.2f}"
            tax_str = f"{emp['tax_percent']:05.2f}"
            filler = " " * 27
            
            line = f"{emp_id_str}{name_str}{dept_str}{basic_str}{tax_str}{filler}"
            assert len(line) == 80, f"Line length is {len(line)}, expected 80. Content: '{line}'"
            f_emp.write(line + "\n")

    # 3. Write Attendance File (attendance.txt) as fixed-width records of exactly 80 chars
    # Structure: EMP_ID (5), DEPT_NAME (10), Overtime (5), Attendance (5), Filler (55)
    with open(ATTENDANCE_FILE, "w", encoding="utf-8") as f_att:
        for att in attendance_list:
            emp_id_str = f"{att['emp_id']:<5}"
            dept_str = f"{att['dept']:<10}"
            ot_str = f"{att['overtime_hours']:05d}"
            att_str = f"{att['attendance_days']:05d}"
            filler = " " * 55
            
            line = f"{emp_id_str}{dept_str}{ot_str}{att_str}{filler}"
            assert len(line) == 80, f"Line length is {len(line)}, expected 80. Content: '{line}'"
            f_att.write(line + "\n")

    print(f"Successfully generated employees database at: {EMPLOYEES_FILE} ({len(master_list)} records)")
    print(f"Successfully generated attendance database at: {ATTENDANCE_FILE} ({len(attendance_list)} records)")
    print("Sequential sorting matches exactly (Dept, ID). Injected 8 logical verification anomalies.")

if __name__ == "__main__":
    main()
