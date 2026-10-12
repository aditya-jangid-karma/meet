import os
import subprocess
import time
import sys
from datetime import datetime

TEAMS = ["Team B", "Team C", "Team D", "Team H", "Team I", "Team F"]
WAIT_SECONDS = 1 * 60
LOG_FILE = "automation_daily_log.txt"

def log(msg):
    # Print to console and write to log file
    print(msg)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(msg + "\n")

def run_script(folder, script_name):
    script_path = os.path.join(folder, script_name)
    if not os.path.exists(script_path):
        log(f"  [!] Missing {script_name} in {folder}! Skipping.")
        return False
        
    log(f"  -> Running {script_name}...")
    try:
        # We capture the output of the script to write it to the log file
        with open(LOG_FILE, "a", encoding="utf-8") as log_out:
            subprocess.run([sys.executable, script_name], cwd=folder, check=True, stdout=log_out, stderr=subprocess.STDOUT)
        return True
    except subprocess.CalledProcessError as e:
        log(f"  [X] Error running {script_name}: {e}")
        return False

def main():
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write("\n\n")
        
    log("==================================================")
    log(f" AUTOMATION MASTER STARTED AT: {datetime.now().strftime('%I:%M %p')} on {datetime.now().strftime('%Y-%m-%d')}")
    log("==================================================\n")

    for i, team in enumerate(TEAMS):
        log(f"\n[{datetime.now().strftime('%I:%M %p')}] STARTING {team.upper()}")
        
        run_script(team, f"process_{team.lower().replace(' ', '_')}.py")
        run_script(team, f"send_{team.lower().replace(' ', '_')}.py")
        
        log(f"[{datetime.now().strftime('%I:%M %p')}] FINISHED {team.upper()}")

        if i < len(TEAMS) - 1:
            log(f"\n Sleeping for 3 minutes before the next team...\n")
            time.sleep(WAIT_SECONDS)

    log("\n==================================================")
    log(f" ALL TEAMS COMPLETED AT: {datetime.now().strftime('%I:%M %p')}")
    log("==================================================")

if __name__ == '__main__':
    main()
