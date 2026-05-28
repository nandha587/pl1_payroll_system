#!/usr/bin/env python3
"""
batch_runtime.py
Lightweight Python execution simulator for the PL/I Payroll Processing System.
Emulates the sequential matching, department control-breaks, duplicate tracking,
validation limits, and checkpoint recovery defined in the PL/I source modules.
"""
import os
import sys
import json
import time
from datetime import datetime

# Setup paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

EMPLOYEES_FILE = os.path.join(DATA_DIR, "employees.txt")
ATTENDANCE_FILE = os.path.join(DATA_DIR, "attendance.txt")
REPORT_FILE = os.path.join(OUTPUT_DIR, "payroll_report.txt")
ERROR_FILE = os.path.join(OUTPUT_DIR, "error_log.txt")
TOTALS_FILE = os.path.join(OUTPUT_DIR, "control_totals.txt")
SUMMARY_FILE = os.path.join(OUTPUT_DIR, "batch_summary.txt")
CHECKPOINT_FILE = os.path.join(OUTPUT_DIR, "checkpoint.state")

BATCH_ID = "PAY20260529A"

# Format strings mapping directly to PL/I Picture and Character specifications
HEADER_LINE = "=" * 80
DETAIL_COLS = "ID     NAME                       DEPARTMENT  GROSS PAY  TAX DED.   PF DED.    NET PAY"
DETAIL_SEP = "-" * 80

def parse_employee_record(line):
    """
    Parses a fixed-width employee master record matching the PL/I struct exactly:
    DCL 1 EMPLOYEE_RECORD,
          2 EMP_ID          CHAR(5),
          2 EMP_NAME        CHAR(25),
          2 DEPT_NAME       CHAR(10),
          2 BASIC_SALARY    FIXED DEC(7,2),
          2 TAX_PERCENT     FIXED DEC(4,2),
          2 FILLER          CHAR(27);
    """
    if not line or len(line) < 80:
        return None
    return {
        "emp_id": line[0:5].strip(),
        "emp_name": line[5:30].strip(),
        "dept_name": line[30:40].strip(),
        "basic_salary": float(line[40:48]),
        "tax_percent": float(line[48:53]),
    }

def parse_attendance_record(line):
    """
    Parses a fixed-width attendance record matching the PL/I struct exactly:
    DCL 1 ATTENDANCE_RECORD,
          2 ATT_ID          CHAR(5),
          2 ATT_DEPT        CHAR(10),
          2 OVERTIME_HOURS  FIXED BIN(15),
          2 ATTENDANCE_DAYS FIXED BIN(15),
          2 FILLER          CHAR(55);
    """
    if not line or len(line) < 80:
        return None
    return {
        "att_id": line[0:5].strip(),
        "att_dept": line[5:15].strip(),
        "overtime_hours": int(line[15:20]),
        "attendance_days": int(line[20:25]),
    }

def validate_record(emp_id, salary, tax_pct, ot_hrs, att_days, last_emp_id):
    """
    Replicates PL/I validation.pli logic.
    """
    if emp_id == last_emp_id:
        return "ERR-103"  # Duplicate Employee ID in master
    if salary <= 0.0:
        return "ERR-201"  # Zero or negative basic salary
    if tax_pct < 0.0 or tax_pct > 50.0:
        return "ERR-202"  # Out of bounds tax percent
    if ot_hrs < 0 or ot_hrs > 80:
        return "ERR-203"  # Out of bounds overtime
    if att_days < 0 or att_days > 31:
        return "ERR-204"  # Out of bounds attendance days
    return "SUCCESS"

def get_error_desc(code):
    """
    Replicates PL/I error_logger.pli lookup.
    """
    mapping = {
        "ERR-101": "RECONCILIATION: ATTENDANCE RECORD MISSING IN LOG",
        "ERR-102": "RECONCILIATION: MASTER RECORD MISSING (ORPHAN)",
        "ERR-103": "VALIDATION: DUPLICATE EMPLOYEE ID IN MASTER FILE",
        "ERR-104": "VALIDATION: DUPLICATE EMPLOYEE ID IN ATTENDANCE",
        "ERR-201": "VALIDATION: ZERO OR NEGATIVE BASIC SALARY VALUE",
        "ERR-202": "VALIDATION: OUT-OF-BOUNDS TAX PERCENTAGE (0-50%)",
        "ERR-203": "VALIDATION: NEGATIVE OR EXCESSIVE OVERTIME HOURS",
        "ERR-204": "VALIDATION: OUT-OF-BOUNDS ATTENDANCE DAYS (0-31)",
    }
    return mapping.get(code, "SYSTEM: UNKNOWN BATCH RUNTIME TRANSACTION ERROR")

def calculate_salary(basic, att_days, ot_hours, tax_percent):
    """
    Replicates PL/I salary_calculator.pli math.
    """
    standard_days = 22.0
    standard_hours = 176.0
    ot_multiplier = 1.5
    pf_rate = 0.08

    base_pay = basic * (float(att_days) / standard_days)
    
    if ot_hours > 0:
        hourly_rate = basic / standard_hours
        ot_pay = hourly_rate * float(ot_hours) * ot_multiplier
    else:
        ot_pay = 0.0

    gross_pay = base_pay + ot_pay
    tax_ded = gross_pay * (tax_percent / 100.0)
    pf_ded = gross_pay * pf_rate
    net_pay = gross_pay - tax_ded - pf_ded

    return gross_pay, ot_pay, tax_ded, pf_ded, net_pay

def format_detail_row(emp_id, name, dept, gross, tax, pf, net):
    """
    Replicates PL/I Picture format mappings in report_generator.pli detail rows.
    """
    gross_str = f"${gross:8.2f}"
    tax_str = f"${tax:7.2f}"
    pf_str = f"${pf:7.2f}"
    net_str = f"${net:8.2f}"
    
    return f"{emp_id:<5}  {name:<25}  {dept:<10}  {gross_str:<10}  {tax_str:<9}  {pf_str:<8}  {net_str:<9}"

def format_dept_summary(dept, count, gross, tax, pf, net):
    """
    Replicates report_generator.pli control-break subtotal blocks.
    """
    gross_str = f"${gross:10.2f}"
    tax_str = f"${tax:9.2f}"
    pf_str = f"${pf:9.2f}"
    net_str = f"${net:10.2f}"
    
    return (
        "================================================================================\n"
        f"DEPARTMENT SUMMARY: {dept:<10}  TOTAL PROCESSED: {count:<10}\n"
        f"  SUBTOTAL GROSS   : {gross_str.strip():<10}\n"
        f"  SUBTOTAL TAX     : {tax_str.strip():<9}\n"
        f"  SUBTOTAL PF      : {pf_str.strip():<8}\n"
        f"  SUBTOTAL NET     : {net_str.strip():<9}\n"
        "================================================================================"
    )

def main():
    print("==========================================================")
    print("  BATCH RUNTIME SIMULATOR FOR PL/I PAYROLL SYSTEM")
    print("==========================================================")

    # Check execution flags
    resume = False
    crash_at = None
    if "--resume" in sys.argv:
        resume = True
    if "--crash-at" in sys.argv:
        try:
            idx = sys.argv.index("--crash-at")
            crash_at = int(sys.argv[idx + 1])
            print(f"[INFO] Batch run configured to abort at loop iteration {crash_at}.")
        except (ValueError, IndexError):
            print("[WARNING] Invalid or missing value for --crash-at. Ignored.")

    # 1. Verify file availability
    if not os.path.exists(EMPLOYEES_FILE) or not os.path.exists(ATTENDANCE_FILE):
        print(f"[FATAL] Input files missing. Run 'generate_test_data.py' first.")
        sys.exit(1)

    # Initialize State Variables
    start_time = datetime.now()
    tot_input_recs = 0
    tot_valid_recs = 0
    tot_error_recs = 0
    tot_gross_pay = 0.0
    tot_tax_collect = 0.0
    tot_pf_collect = 0.0
    tot_net_pay = 0.0

    dept_emp_count = 0
    dept_gross = 0.0
    dept_tax = 0.0
    dept_pf = 0.0
    dept_net = 0.0

    last_emp_id = ""
    current_dept = ""

    emp_offset = 0
    att_offset = 0

    report_lines = []
    error_lines = []

    # 2. Checkpoint recovery
    if resume:
        if os.path.exists(CHECKPOINT_FILE):
            print(f"[RECOVERY] Reading state from {CHECKPOINT_FILE}...")
            try:
                with open(CHECKPOINT_FILE, "r") as ck:
                    state = json.load(ck)
                
                tot_input_recs = state["tot_input_recs"]
                tot_valid_recs = state["tot_valid_recs"]
                tot_error_recs = state["tot_error_recs"]
                tot_gross_pay = state["tot_gross_pay"]
                tot_tax_collect = state["tot_tax_collect"]
                tot_pf_collect = state["tot_pf_collect"]
                tot_net_pay = state["tot_net_pay"]

                dept_emp_count = state["dept_emp_count"]
                dept_gross = state["dept_gross"]
                dept_tax = state["dept_tax"]
                dept_pf = state["dept_pf"]
                dept_net = state["dept_net"]

                last_emp_id = state["last_emp_id"]
                current_dept = state["current_dept"]
                
                emp_offset = state["emp_offset"]
                att_offset = state["att_offset"]
                
                if os.path.exists(REPORT_FILE):
                    with open(REPORT_FILE, "r") as rf:
                        report_lines = rf.readlines()
                if os.path.exists(ERROR_FILE):
                    with open(ERROR_FILE, "r") as ef:
                        error_lines = ef.readlines()
                
                print(f"[RECOVERY] Resuming execution from master record index {emp_offset} / attendance index {att_offset}")
            except Exception as ex:
                print(f"[RECOVERY ERROR] Failed to parse checkpoint state: {ex}. Starting raw batch run.")
                resume = False
        else:
            print("[RECOVERY WARNING] Checkpoint state file not found. Running raw batch.")
            resume = False

    # Load file streams
    with open(EMPLOYEES_FILE, "r") as f_emp:
        emp_lines = [line.rstrip("\n") for line in f_emp.readlines()]
    with open(ATTENDANCE_FILE, "r") as f_att:
        att_lines = [line.rstrip("\n") for line in f_att.readlines()]

    emp_idx = emp_offset
    att_idx = att_offset

    # Open files or maintain buffers
    if not resume:
        # Standard initial output headers
        report_lines.append(HEADER_LINE + "\n")
        report_lines.append(f"BATCH PAYROLL DETAILS REPORT - RUN ID: {BATCH_ID}\n")
        report_lines.append(HEADER_LINE + "\n")
        report_lines.append(DETAIL_COLS + "\n")
        report_lines.append(DETAIL_SEP + "\n")
        
        # Clear output directories
        if os.path.exists(REPORT_FILE): os.remove(REPORT_FILE)
        if os.path.exists(ERROR_FILE): os.remove(ERROR_FILE)

    print(f"[INFO] BATCH ID: {BATCH_ID} started processing stream...")

    # Main Match-Merge Sequential Loop
    while emp_idx < len(emp_lines) or att_idx < len(att_lines):
        tot_input_recs += 1

        # Determine sequential keys (use ZZZZZ high values for EOF flushing)
        emp_rec = parse_employee_record(emp_lines[emp_idx]) if emp_idx < len(emp_lines) else None
        att_rec = parse_attendance_record(att_lines[att_idx]) if att_idx < len(att_lines) else None

        # Build compound sorting keys matching PL/I exactly: DEPT_NAME + EMP_ID (length 15)
        match_key_emp = f"{emp_rec['dept_name']:<10}{emp_rec['emp_id']:<5}" if emp_rec else "ZZZZZZZZZZZZZZZ"
        match_key_att = f"{att_rec['att_dept']:<10}{att_rec['att_id']:<5}" if att_rec else "ZZZZZZZZZZZZZZZ"

        # Case 1: Keys match perfectly
        if match_key_emp == match_key_att and match_key_emp != "ZZZZZZZZZZZZZZZ":
            emp_id = emp_rec["emp_id"]
            dept = emp_rec["dept_name"]
            
            # Department Control Break Check
            if not current_dept:
                current_dept = dept
            elif current_dept != dept:
                # Flush Subtotals
                sum_block = format_dept_summary(current_dept, dept_emp_count, dept_gross, dept_tax, dept_pf, dept_net)
                report_lines.append(sum_block + "\n")
                
                # Accumulate globally
                tot_gross_pay += dept_gross
                tot_tax_collect += dept_tax
                tot_pf_collect += dept_pf
                tot_net_pay += dept_net
                
                # Reset counters
                dept_emp_count = 0
                dept_gross = 0.0
                dept_tax = 0.0
                dept_pf = 0.0
                dept_net = 0.0
                
                current_dept = dept

            # Run Validation checks (duplicate ID & boundary limits)
            v_status = validate_record(emp_id, emp_rec["basic_salary"], emp_rec["tax_percent"], 
                                       att_rec["overtime_hours"], att_rec["attendance_days"], last_emp_id)
            
            # Check for duplicate timesheet (duplicate key in attendance log)
            # Replicates PL/I ERR-104: if attendance has duplicate timesheet
            is_att_duplicate = False
            if att_idx + 1 < len(att_lines):
                next_att = parse_attendance_record(att_lines[att_idx + 1])
                if next_att and next_att["att_id"] == emp_id and next_att["att_dept"] == dept:
                    is_att_duplicate = True

            if v_status != "SUCCESS":
                # Validation error
                desc = get_error_desc(v_status)
                err_row = f"{v_status} | {BATCH_ID} | {emp_id:<5} | {desc}"
                error_lines.append(err_row + "\n")
                tot_error_recs += 1
            else:
                # Validation success: compute and stage details
                gross, ot_pay, tax, pf, net = calculate_salary(emp_rec["basic_salary"], att_rec["attendance_days"], 
                                                               att_rec["overtime_hours"], emp_rec["tax_percent"])
                
                row_str = format_detail_row(emp_id, emp_rec["emp_name"], dept, gross, tax, pf, net)
                report_lines.append(row_str + "\n")
                
                # Accumulate department sub-totals
                dept_emp_count += 1
                dept_gross += gross
                dept_tax += tax
                dept_pf += pf
                dept_net += net
                
                tot_valid_recs += 1

            if is_att_duplicate:
                # Log duplicate timesheet entry immediately
                desc = get_error_desc("ERR-104")
                err_row = f"ERR-104 | {BATCH_ID} | {emp_id:<5} | {desc}"
                error_lines.append(err_row + "\n")
                tot_error_recs += 1
                # Skip duplicate timesheet record in stream
                att_idx += 1

            # Update tracker and advance streams
            last_emp_id = emp_id
            emp_idx += 1
            att_idx += 1

        # Case 2: Master ID is missing in Attendance log (Master < Attendance)
        elif match_key_emp < match_key_att:
            emp_id = emp_rec["emp_id"]
            desc = get_error_desc("ERR-101")
            err_row = f"ERR-101 | {BATCH_ID} | {emp_id:<5} | {desc}"
            error_lines.append(err_row + "\n")
            
            tot_error_recs += 1
            last_emp_id = emp_id
            emp_idx += 1

        # Case 3: Attendance log exists without Master record (Master > Attendance)
        else:
            att_id = att_rec["att_id"]
            desc = get_error_desc("ERR-102")
            err_row = f"ERR-102 | {BATCH_ID} | {att_id:<5} | {desc}"
            error_lines.append(err_row + "\n")
            
            tot_error_recs += 1
            att_idx += 1

        # Checkpoint serialization every 100 loop iterations
        if tot_input_recs % 100 == 0:
            with open(REPORT_FILE, "w", encoding="utf-8") as rf:
                rf.writelines(report_lines)
            with open(ERROR_FILE, "w", encoding="utf-8") as ef:
                ef.writelines(error_lines)

            state = {
                "tot_input_recs": tot_input_recs,
                "tot_valid_recs": tot_valid_recs,
                "tot_error_recs": tot_error_recs,
                "tot_gross_pay": tot_gross_pay,
                "tot_tax_collect": tot_tax_collect,
                "tot_pf_collect": tot_pf_collect,
                "tot_net_pay": tot_net_pay,
                "dept_emp_count": dept_emp_count,
                "dept_gross": dept_gross,
                "dept_tax": dept_tax,
                "dept_pf": dept_pf,
                "dept_net": dept_net,
                "last_emp_id": last_emp_id,
                "current_dept": current_dept,
                "emp_offset": emp_idx,
                "att_offset": att_idx
            }
            with open(CHECKPOINT_FILE, "w") as ck:
                json.dump(state, ck)
            
            print(f"[CHECKPOINT] Saved state at loop {tot_input_recs}. Master Index: {emp_idx}, Attendance Index: {att_idx}")
            time.sleep(0.05)

        # Simulated batch abort for testing recovery
        if crash_at and tot_input_recs >= crash_at:
            print(f"[FATAL] Simulated batch abort triggered at loop iteration {tot_input_recs}.")
            sys.exit(2)

    # Flush final control break sub-totals for last department
    if dept_emp_count > 0:
        sum_block = format_dept_summary(current_dept, dept_emp_count, dept_gross, dept_tax, dept_pf, dept_net)
        report_lines.append(sum_block + "\n")
        
        tot_gross_pay += dept_gross
        tot_tax_collect += dept_tax
        tot_pf_collect += dept_pf
        tot_net_pay += dept_net

    # Flush buffers to disk
    with open(REPORT_FILE, "w", encoding="utf-8") as rf:
        rf.writelines(report_lines)
    with open(ERROR_FILE, "w", encoding="utf-8") as ef:
        ef.writelines(error_lines)

    # Write Audit Control Totals summary (control_totals.txt)
    with open(TOTALS_FILE, "w", encoding="utf-8") as tf:
        tf.write(HEADER_LINE + "\n")
        tf.write(f"AUDIT CONTROL TOTALS SUMMARY - BATCH RUN ID: {BATCH_ID}\n")
        tf.write(HEADER_LINE + "\n")
        tf.write(f"INPUT RECORDS READ        : {tot_input_recs}\n")
        tf.write(f"SUCCESSFULLY PROCESSED    : {tot_valid_recs}\n")
        tf.write(f"EXCEPTIONS / REJECTIONS   : {tot_error_recs}\n")
        tf.write(f"TOTAL CUMULATIVE GROSS PAY: ${tot_gross_pay:12.2f}\n")
        tf.write(f"TOTAL TAX DEDUCTED        : ${tot_tax_collect:12.2f}\n")
        tf.write(f"TOTAL NET PAYOUT TO EXP   : ${tot_net_pay:12.2f}\n")
        tf.write(HEADER_LINE + "\n")

    # Write Run Metadata Summary (batch_summary.txt)
    end_time = datetime.now()
    elapsed = end_time - start_time
    with open(SUMMARY_FILE, "w", encoding="utf-8") as sf:
        sf.write(f"BATCH_ID    : {BATCH_ID}\n")
        sf.write(f"STATUS      : SUCCESS\n")
        sf.write(f"START_TIME  : {start_time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        sf.write(f"END_TIME    : {end_time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        sf.write(f"DURATION    : {elapsed.total_seconds():.3f} SECONDS\n")
        sf.write(f"RECORDS/SEC : {tot_input_recs / (elapsed.total_seconds() or 1.0):.2f}\n")

    # Clean up checkpoint on complete success
    if os.path.exists(CHECKPOINT_FILE):
        os.remove(CHECKPOINT_FILE)

    print("==========================================================")
    print("  BATCH EXECUTION COMPLETED SUCCESSFULLY")
    print("==========================================================")
    print(f"Detail Report   : {REPORT_FILE}")
    print(f"Exceptions Log  : {ERROR_FILE}")
    print(f"Control Totals  : {TOTALS_FILE}")
    print(f"Batch Summary   : {SUMMARY_FILE}")
    print("==========================================================")

if __name__ == "__main__":
    main()
