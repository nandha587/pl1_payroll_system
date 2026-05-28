# Enterprise Batch Execution Flow

This document details the operational batch pipeline for executing the Payroll Processing System. It outlines the equivalent steps required in a mainframe environment using **JCL (Job Control Language)** and the **DFSORT** system utilities to establish the sequential stream alignment.

---

## 1. Batch Execution Pipeline

In a legacy core business environment, batch jobs are executed overnight in scheduled streams. To perform high-integrity matching, files are prepared, sorted, validated, and processed sequentially:

```
+--------------------+      +--------------------+
| Raw Employee Data  |      | Raw Attendance Log |
+--------------------+      +--------------------+
          |                            |
          v                            v
   [ JCL STEP 010 ]             [ JCL STEP 020 ]
   DFSORT by Dept + ID          DFSORT by Dept + ID
          |                            |
          v                            v
+--------------------+      +--------------------+
| Sorted Master File |      | Sorted Trans File  |
+--------------------+      +--------------------+
          \                            /
           \                          /
            v                        v
          [ JCL STEP 030: PAYROLL BATCH RUN ]
          - Sequential match-merge processing
          - Control Break aggregate summary
          - Checkpoint serialization (every 100 recs)
            /            |             \
           /             |              \
          v              v               v
+----------------+ +---------------+ +---------------+
| Detail Report  | | Exception Log | | Audit Totals  |
| (payroll_rep)  | | (error_log)   | | (control_tot) |
+----------------+ +---------------+ +---------------+
```

---

## 2. JCL Operational Steps (Equivalent Specification)

### A. JCL STEP 010: Sorting the Employee Master
Before sequential processing, the Employee Master dataset (`EMPLOYEES.RAW`) must be sorted by Department and Employee ID.
```jcl
//SORTMST  JOB  (PAYROLL),'SORT MASTER',CLASS=A,MSGCLASS=X
//STEP010  EXEC PGM=SORT
//SYSOUT   DD   SYSOUT=*
//SORTIN   DD   DSN=SYS.PAYROLL.RAW.EMPLOYEES,DISP=SHR
//SORTOUT  DD   DSN=SYS.PAYROLL.SORTED.EMPLOYEES,DISP=(NEW,CATLG,DELETE),
//             SPACE=(CYL,(5,2)),DCB=(RECFM=FB,Lrecl=80,BLKSIZE=800)
//SYSIN    DD   *
  SORT FIELDS=(31,10,CH,A,1,5,CH,A)
/*
```
*Note: Fields `(31,10,CH,A)` sorts starting at offset 31 for 10 characters (DEPT_NAME) ascending, and `(1,5,CH,A)` sorts starting at offset 1 for 5 characters (EMP_ID) ascending.*

---

### B. JCL STEP 020: Sorting the Attendance Records
Similarly, the Attendance Log (`ATTEND.RAW`) is sorted to align with the Master's order.
```jcl
//SORTATT  JOB  (PAYROLL),'SORT ATTENDANCE',CLASS=A,MSGCLASS=X
//STEP020  EXEC PGM=SORT
//SYSOUT   DD   SYSOUT=*
//SORTIN   DD   DSN=SYS.PAYROLL.RAW.ATTENDANCE,DISP=SHR
//SORTOUT  DD   DSN=SYS.PAYROLL.SORTED.ATTENDANCE,DISP=(NEW,CATLG,DELETE),
//             SPACE=(CYL,(5,2)),DCB=(RECFM=FB,Lrecl=80,BLKSIZE=800)
//SYSIN    DD   *
  SORT FIELDS=(16,10,CH,A,1,5,CH,A)
/*
```

---

### C. JCL STEP 030: Running the PL/I Payroll Batch Engine
Executes the main compiled program. In the event of a crash, JCL checks the condition code and initiates a restart parameter (`PARM='RESUME'`) to restore state from the checkpoint dataset.
```jcl
//PAYRUN   JOB  (PAYROLL),'RUN PAYROLL',CLASS=A,MSGCLASS=X
//STEP030  EXEC PGM=PAYMAIN,PARM='RUN'
//STEPLIB  DD   DSN=SYS.PAYROLL.LOADLIB,DISP=SHR
//EMPFILE  DD   DSN=SYS.PAYROLL.SORTED.EMPLOYEES,DISP=SHR
//ATTFILE  DD   DSN=SYS.PAYROLL.SORTED.ATTENDANCE,DISP=SHR
//REPFILE  DD   DSN=SYS.PAYROLL.OUTPUT.REPORT,DISP=(NEW,CATLG),
//             SPACE=(TRK,(10,5)),DCB=(RECFM=FBA,Lrecl=121,BLKSIZE=1210)
//ERRFILE  DD   DSN=SYS.PAYROLL.OUTPUT.ERRORS,DISP=(NEW,CATLG),
//             SPACE=(TRK,(5,2)),DCB=(RECFM=FB,Lrecl=120,BLKSIZE=1200)
//SUMFILE  DD   DSN=SYS.PAYROLL.OUTPUT.SUMTotals,DISP=(NEW,CATLG),
//             SPACE=(TRK,(1,1)),DCB=(RECFM=FB,Lrecl=80,BLKSIZE=80)
//CHKFILE  DD   DSN=SYS.PAYROLL.CHECKPOINT.STATE,DISP=OLD
//SYSPRINT DD   SYSOUT=*
```

---

## 3. Checkpoint/Restart Logic Flow

The checkpoint mechanism in `payroll_main.pli` operates as follows:
1. **Periodic Serialization**: Every 100 loop cycles, the program pauses file stream processing.
2. **Buffer Flush**: The current contents of memory buffers are flushed to `REPFILE` and `ERRFILE`.
3. **State Save**: Variables describing the exact record counters (`REC_INDEX_EMP`, `REC_INDEX_ATT`), global accumulators, and current department state are serialized to the `CHKFILE` dataset.
4. **Crash Recovery**: If the job terminates abnormally (e.g. out of memory, power failure):
   - The systems administrator restarts the job.
   - The runtime library reads the checkpoint file, sets file pointers directly to the recorded offsets, restores cumulative total values into memory, and resumes execution seamlessly.
   - This eliminates the need to restart large-scale multi-million row processing batches from record 1.
5. **Cleanup**: Upon full successful batch completion, the program automatically purges/deletes the checkpoint file.
