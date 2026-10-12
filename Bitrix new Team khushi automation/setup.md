# Bitrix24 Task Automation - Setup Guide

This guide explains how to set up and run the Bitrix Automated Reporting system on a new machine.

## 📋 Prerequisites

1. **Python 3.8+**: Ensure Python is installed and added to your system PATH.
2. **Microsoft Excel**: This project **requires** Microsoft Excel to be installed on the machine. The scripts use a Windows COM Object (excel2img) to silently open Excel in the background and take high-resolution screenshots of the generated reports.
3. **Active Windows Session**: Because the COM Object relies on Excel's graphical rendering, the scripts must be run on a Windows machine (not a headless Linux server).

---

## 🛠️ Installation

1. Open your terminal (PowerShell or Command Prompt).
2. Navigate to this project folder:
   `cmd
   cd "C:\Users\Meet Patel\Desktop\Bitrix new Team khushi automation"
   `
3. Install all required dependencies using the generated equirements.txt file:
   `cmd
   pip install -r requirements.txt
   `

**Installed Packages:**
* pandas & openpyxl (For generating and formatting the Excel reports)
* equests & urllib3 (For communicating with the Bitrix APIs)
* excel2img & pywin32 (For rendering the Excel charts into PNG images)

---

## 🚀 How to Run Manually

The project is split into distinct Team folders (Team B, Team C, Team D, Team H, Team I). To process and send reports for a specific team, you must run both scripts in sequence.

For example, to run **Team C**:

**Step 1: Generate the Reports**
Open terminal, navigate to the Team C folder, and run the processing script:
`cmd
cd "Team C"
python process_team_c.py
`
*This will fetch live data from Bitrix, generate the .xlsx files, take the .png screenshots, and save them in the 	eam_c_output folder.*

**Step 2: Dispatch the Reports**
While still inside the Team C folder, run the sending script:
`cmd
python send_team_c.py
`
*This will upload the generated files to Bitrix Drive, route them to the mapped L1 Group Chats, and send carbon copies to the Testing Channel (345986). If an L1 lead has zero tasks, it will safely skip the file upload and send a plain-text congratulatory message.*

---

## 📅 Future Automation (Task Scheduler)
To fully automate this process, a master batch script (un_all.bat) can be created to loop through all team folders and sequentially execute the python scripts. This batch file can then be bound to a **Windows Task Scheduler** trigger to run automatically at a specific time (e.g., Daily at 3:00 PM).
