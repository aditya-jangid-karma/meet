import os

base_dir = r"\\10.0.8.33\Karma Automation\Bitrix Team Task Automation"
teams = ["B", "C", "D", "F", "H", "I"]
errors = []

# 1. Check daily_scheduler.py
daily = os.path.join(base_dir, "daily_scheduler.py")
if os.path.exists(daily):
    with open(daily, 'r') as f:
        c = f.read()
    if ".venv" in c:
        errors.append("daily_scheduler.py still contains .venv references")
    if 'subprocess.run([sys.executable, "master_runner.py"]' not in c:
        errors.append("daily_scheduler.py is not using sys.executable correctly")
else:
    errors.append("daily_scheduler.py is missing!")

# 2. Check master_runner.py
master = os.path.join(base_dir, "master_runner.py")
if os.path.exists(master):
    with open(master, 'r') as f:
        c = f.read()
    if 'subprocess.run([sys.executable, script_name]' not in c:
        errors.append("master_runner.py is not using sys.executable")
    if 'WAIT_SECONDS = 3 * 60' not in c:
        errors.append("master_runner.py wait time is not 3 minutes")
else:
    errors.append("master_runner.py is missing!")

# 3. Check teams
for t in teams:
    team_dir = os.path.join(base_dir, f"Team {t}")
    proc = os.path.join(team_dir, f"process_team_{t.lower()}.py")
    send = os.path.join(team_dir, f"send_team_{t.lower()}.py")
    
    if os.path.exists(proc):
        with open(proc, 'r', encoding='utf-8') as f:
            c = f.read()
        if "'Overdue Task Count':" not in c and '"Overdue Task Count":' not in c:
            errors.append(f"Team {t} process is missing Overdue Task Count header")
        if "today_str" not in c:
            errors.append(f"Team {t} process is missing Date formatting logic")
    else:
        errors.append(f"Team {t} process file missing!")
        
    if os.path.exists(send):
        with open(send, 'r', encoding='utf-8') as f:
            c = f.read()
        if "\n# LEAD_CHATS" in c or "\n#LEAD_CHATS" in c:
            errors.append(f"Team {t} send has commented LEAD_CHATS")
        if "today_str" not in c:
            errors.append(f"Team {t} send is missing Date formatting logic")
    else:
        errors.append(f"Team {t} send file missing!")

if errors:
    print("ERRORS FOUND:")
    for e in errors:
        print(" - " + e)
else:
    print("ALL SYSTEMS NOMINAL. 100% READY.")
