LABREPORT PRO  -  Material Testing Reports & Observation Sheets
=================================================================

GET THE .EXE (one time, 3 minutes, on a Windows PC)
 1. Install Python 3.10 or newer from python.org  (tick "Add Python to PATH").
 2. Double-click  build_exe.bat   ->  creates  dist\LabReportPro.exe
 3. Copy LabReportPro.exe anywhere. Double-click to run. No install needed on other PCs.
    (To try without building: double-click run_without_building.bat)

WHERE DATA IS STORED
 A folder  LabData  appears beside the .exe:  labdata.db (all jobs, readings, test definitions),
 Reports\ (PDFs), Backups\ (copies). Back up the whole LabData folder. Settings tab -> "Backup database now".

DAILY WORK
 Jobs / Reports tab -> "+ New job"
   - choose the Material (OPC 33/43/53, PPC, Fly Ash, Admixture, Sand, 10mm, 20mm, or your own)
   - fill the job details once, then open each test tab and type the readings.
     Results appear instantly. Fields marked "auto" are taken from an earlier test (e.g. SO3 sample = I.R. sample).
   - Save, then "Observation Sheet (PDF)" or "Test Report (PDF)".
 Any old job can be re-opened, corrected and re-printed at any time. Search box finds by report no., customer, job no., material.
 "Copy job as new" duplicates the header details for a repeat sample.

ADDING A NEW TESTING ITEM / MATERIAL  (no programming)
 Test Library tab
   - New material  (e.g. "GGBS", "Bricks", "Water")  or  Duplicate an existing one and edit.
   - Add test -> give: code, name, method, unit, limit text, decimals, report page.
       Observation fields  = what the analyst types (weights, volumes, readings).
       Calculations        = formulas, evaluated top to bottom; tick ONE as the reported result.
   - Formula examples:   (B-C)*100/(B-A)      avg(l1,l2,l3)      iff(V>0, V*2, 0)      (CAO_result-0.7*SO3_result)/2
     Use +  -  *  /  **  ( )  and  avg sum min max round sqrt abs ln log10 iff.
     Use CODE_variable to read another test of the same material (e.g. IR_A, SIO2_result).
   - "Test formulas with sample numbers" lets you try it before saving.
   - Untick "In report" for a calculation-only step. "Report page" makes multi-page reports (like Aggregate).
   - Blank input => blank result (never an error); a test with no result is simply left out of the report.

SETTINGS TAB
 Lab name, testing location, blank letterhead space at top of report (mm), reviewer / analyst names, report notes,
 Backup, and "Export everything to Excel" (Register + Results + all Observations).

NOTES
 * The standard library (cement, fly ash, admixture, aggregate) was built from your Excel files; results
   were checked against your original sheets and match.  Limits/methods are editable in the Test Library.
 * Sand soundness: blank cycles are ignored in the average (the old Excel counted a blank as 100% loss).
 * PDFs use the Cambria font (Windows Fonts folder). Excel exports are also in Cambria.
 * Every job has 4 outputs: Test Report (PDF / Excel) and Observation Sheet (PDF / Excel).
   Excel files contain the same content as the PDFs (values, not live formulas) and are saved in LabData\Reports.
 * Long text in Name of Work, Address, etc. wraps onto extra lines automatically.
 * After "New material" the program offers to add its tests straight away (parameters, limit, method, formulas).

VERSION 2 ADDITIONS
 1. Multi-page reports: pages after the first show only "Report No :- ..." and "Page x of y" at the top
    (every page also has "Page x of y" at the bottom). Same for Observation Sheets, PDF and Excel print headers.
 2. Equipment & Logbook tab: register your equipment once (ID, name, calibration due). In the Test Library tick the equipment normally
    used for each test. When you save a job, every test that has readings is logged automatically against the ticked equipment,
    dated with the job's Test Start Date (you can change the tick per job on each test tab). Manual entries (calibration,
    maintenance) can be added. Filter by equipment/date, export Excel or PDF.
 3. Chemical Standardization Record tab: any field marked Normality / Molarity (detected from the label, or set in the field editor) is
    saved automatically, for the testing day, with the reagent name and the jobs that used it. Edit a record to add the primary standard,
    volumes and titre - the strength is calculated (N1V1 = N2V2). Export Excel / PDF.
 4. Date rules on every job: Date of Receipt <= Test Start <= Test Completion <= Report Date. A red warning appears while typing and
    saving is blocked until corrected.
 5. Maker credit: "Software by Mr. Ganesh Raykar" in the window footer and About box. Settings -> tick the box to also print it in the
    footer of PDF / Excel files.
 Upgrading: replace the files on GitHub, rebuild the exe, put the new LabReportPro.exe next to your existing LabData folder -
 the database upgrades itself and all old jobs are kept.

VERSION 3 ADDITIONS
 1. LOGIN & PERMISSIONS - At the very first start the program asks you to create the Administrator (no default password exists - note it down).
    Users & Permissions tab: the Administrator adds users and, for every section (Jobs, Test Library, Equipment & Logbook, Standardization,
    Settings, Users, Audit Trail) ticks what the person may View / Add / Edit / Delete. Role templates: Administrator, Analyst, Reviewer, Viewer, Custom.
    Buttons a user may not use are greyed out, and the database refuses the action even if a button is reached another way.
    New users must change their temporary password at first login. 5 wrong passwords lock the account (Administrator unlocks it).
 2. SCROLLING - every form, dialog and list now scrolls (mouse wheel or scroll bar); nothing is hidden below the window edge.
 3. JOB NO. RULE - a Job No. cannot be used twice in the same year (year = year of the Date of Receipt). The same number may be used in a different
    year. A red warning shows as you type. "Copy job as new" leaves the Job No. blank so you enter a new one.
 4. AUDIT TRAIL - tab "Audit Trail": actual date, time, user, section, action, record and every old -> new value (job fields, readings, equipment,
    test-library edits, users/permissions, settings, logins, failed logins, backups, report exports). Entries cannot be edited or deleted in the program;
    "Verify integrity" detects any tampering with the database file. Export to Excel / PDF.
 5. LOGO - the Civil Tech logo (taken from your Excel files) shows on the login screen, main window and the program/exe icon, and prints on Observation
    Sheets. Settings -> "Choose logo file..." replaces it with a better-quality picture; options let you print it on Test Reports too.
 SECURITY NOTE: the program controls what people can do inside LabReport Pro. Also keep the LabData folder on a PC / shared folder that only authorised
 people can open (Windows folder permissions), and take backups (Settings -> Backup).

FORGOT PASSWORD
 * Analysts / other users: ask the Administrator -> Users & Permissions -> select the user -> "Reset password" (gives a temporary password).
 * Administrator: when the Administrator account is created the program shows a RECOVERY CODE once - write it down and keep it safe.
   On the login window click "Forgot password?", enter the user name, the recovery code and a new password. Each code works once and a new
   code is shown after use. If your account was created before this feature, a code is created the next time you log in (or use
   Users & Permissions -> "My recovery code (new)").
 * The login window now sizes itself to the screen / Windows text scaling, so LOGIN, Exit and "Forgot password?" are always visible.

INSTALLER (shows in Windows Settings -> Apps / Control Panel -> Programs, with Uninstall)
 GitHub now builds TWO files: LabReportPro_Setup.exe (installer - use this) and LabReportPro.exe (portable, no install).
 Run LabReportPro_Setup.exe -> Next -> Install. It adds a Start-menu entry (and optional desktop icon) and an entry in
 Apps & features, from where you can uninstall. Uninstall asks whether to delete your data (default: keep it).
 Installed version stores data in C:\ProgramData\LabReportPro\LabData (shared by all Windows users of the PC, survives upgrades/uninstall).
 Upgrade: just run the new Setup over the old one. Moving old data: copy the old LabData folder's contents into the folder above.
 Backup: copy that folder (or Settings -> Backup).

VERSION 4 - TESTS FROM "Observation_Sheet_Combine.xlsx" (added automatically once, at the first start after the update)
 New materials in the Test Library (each sheet of your workbook): Ambient Air (PM10, PM2.5, SO2, NOx), Building Lime (9 tests), GGBS (cement tests),
 Hardened Concrete (pH, Chloride, Acid Soluble Sulphate), Soil (14 tests incl. C:N ratio), Waste Water (39 tests), Drinking Water (28 tests incl. Odour, Taste panel,
 Coliform, E. coli), Construction Water (9 tests). Admixture, Fly Ash, Cement/OPC/PPC and Aggregate sheets were already in the program.
 Limits are blank (your observation sheets do not give them) - enter them in Test Library -> Edit test.
 Every test tab now has its own "Date of analysis" and "Analysed by" (must lie between Test Start and Test Completion date); these print on the observation sheet.
 "Equipment types on the observation sheet" (Balance, Oven, Burette ...) are stored per test: the matching equipment you registered is ticked automatically for the logbook.
 Every Normality / Molarity in the new tests feeds the Chemical Standardization Record on the testing day of that test.
