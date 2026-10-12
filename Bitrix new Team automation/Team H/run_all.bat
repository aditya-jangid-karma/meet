@echo off
set "startTime=%time%"
echo Start Time: %startTime%
echo Starting 3 PM Live Data Extraction and Reporting...

echo Step 1: Fetching basic overdue tasks...
python team_h_overdue_tasks.py

echo Step 2: Fixing Overview formatting...
python fix_overview.py

echo Step 2.5: Fetching Due Today data...
python add_due_today_col.py

echo Step 3: Splitting by L1 and getting Due Tomorrow data...
python final_split_L1.py

echo Step 4: Restructuring files to 2 core tabs...
python restructure_files.py

echo Step 5: Adding Responsible Persons stats and generating screenshots...
python add_responsible_persons.py

echo Step 6: Dispatching final reports to Bitrix Channels...
rem python send_to_leads.py

echo Moving files to new output...
mkdir "new output" 2>nul
copy *_Final_Report.xlsx "new output\"
copy *_Screenshot.png "new output\"

set "endTime=%time%"
echo =========================================
echo Started at: %startTime%
echo Ended at:   %endTime%
echo Time taken: %endTime% - %startTime%
echo =========================================
echo All tasks completed successfully!
echo ----------- Enter any key... ------------
pause
