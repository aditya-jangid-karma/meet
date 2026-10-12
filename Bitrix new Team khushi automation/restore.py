import os

base_dir = r"\\10.0.8.33\Karma Automation\Bitrix Team Task Automation"

# 1. Restore L1 chat sends in all teams
teams = ["B", "C", "D", "F", "H", "I"]
for t in teams:
    send_file = os.path.join(base_dir, f"Team {t}", f"send_team_{t.lower()}.py")
    if os.path.exists(send_file):
        with open(send_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Uncomment the lines that send to chat_id
        content = content.replace(
            '# requests.post(COMMIT_URL, json={"CHAT_ID": chat_id, "MESSAGE": " ", "DISK_ID": [img_disk_id]}, verify=False)',
            'requests.post(COMMIT_URL, json={"CHAT_ID": chat_id, "MESSAGE": " ", "DISK_ID": [img_disk_id]}, verify=False)'
        )
        content = content.replace(
            '# requests.post(COMMIT_URL, json={"CHAT_ID": chat_id, "MESSAGE": f"Here is the latest overdue task report for {display_name}:\\n{excel_file}", "DISK_ID": [excel_disk_id]}, verify=False)',
            'requests.post(COMMIT_URL, json={"CHAT_ID": chat_id, "MESSAGE": f"Here is the latest overdue task report for {display_name}:\\n{excel_file}", "DISK_ID": [excel_disk_id]}, verify=False)'
        )
        content = content.replace(
            '# requests.post(MESSAGE_URL, json={"CHAT_ID": chat_id, "MESSAGE": success_msg}, verify=False)',
            'requests.post(MESSAGE_URL, json={"CHAT_ID": chat_id, "MESSAGE": success_msg}, verify=False)'
        )
        
        with open(send_file, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Restored L1 chat sends in Team {t}")

# 2. Upgrade master_runner.py with Logging and 15-minute wait
master_code = '''import os
import subprocess
import time
import sys
from datetime import datetime

TEAMS = ["Team B", "Team C", "Team D", "Team H", "Team I", "Team F"]
WAIT_SECONDS = 15 * 60  # 15 minutes
LOG_FILE = "automation_daily_log.txt"

def log(msg):
    # Print to console and write to log file
    print(msg)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(msg + "\\n")

def run_script(folder, script_name):
    script_path = os.path.join(folder, script_name)
    if not os.path.exists(script_path):
        log(f"  [!] Missing {script_name} in {folder}! Skipping.")
        return False
        
    log(f"  -> Running {script_name}...")
    try:
        # We capture the output of the script to write it to the log file
        with open(LOG_FILE, "a", encoding="utf-8") as log_out:
            subprocess.run(["python", script_name], cwd=folder, check=True, stdout=log_out, stderr=subprocess.STDOUT)
        return True
    except subprocess.CalledProcessError as e:
        log(f"  [X] Error running {script_name}: {e}")
        return False

def main():
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write("\\n\\n")
        
    log("==================================================")
    log(f" AUTOMATION MASTER STARTED AT: {datetime.now().strftime('%I:%M %p')} on {datetime.now().strftime('%Y-%m-%d')}")
    log("==================================================\\n")

    for i, team in enumerate(TEAMS):
        log(f"\\n[{datetime.now().strftime('%I:%M %p')}] STARTING {team.upper()}")
        
        run_script(team, f"process_{team.lower().replace(' ', '_')}.py")
        run_script(team, f"send_{team.lower().replace(' ', '_')}.py")
        
        log(f"[{datetime.now().strftime('%I:%M %p')}] FINISHED {team.upper()}")

        if i < len(TEAMS) - 1:
            log(f"\\n Sleeping for 15 minutes before the next team...\\n")
            time.sleep(WAIT_SECONDS)

    log("\\n==================================================")
    log(f" ALL TEAMS COMPLETED AT: {datetime.now().strftime('%I:%M %p')}")
    log("==================================================")

if __name__ == '__main__':
    main()
'''

master_path = os.path.join(base_dir, "master_runner.py")
with open(master_path, 'w', encoding='utf-8') as f:
    f.write(master_code)

print("Upgraded master_runner.py with full logging capabilities and restored the 15 minute wait!")
