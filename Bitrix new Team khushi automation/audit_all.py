import os
import re

directories = [
    r"c:\Users\Meet Patel\Desktop\Bitrix new Team khushi automation",
    r"\\10.0.8.33\Karma Automation\Bitrix Team Task Automation"
]
teams = ["B", "C", "D", "F", "H", "I"]

report = []

for base_dir in directories:
    if not os.path.exists(base_dir):
        report.append(f"[!] Directory not found: {base_dir}")
        continue
    
    env_name = "LOCAL" if "Desktop" in base_dir else "SERVER"
    report.append(f"\n=== Auditing {env_name} Environment ===")

    # 1. Audit master_runner.py
    master_path = os.path.join(base_dir, "master_runner.py")
    if os.path.exists(master_path):
        with open(master_path, 'r', encoding='utf-8') as f:
            m_content = f.read()
        
        if "WAIT_SECONDS = 15 * 60" not in m_content:
            report.append(f"  [FIXED] master_runner.py: Wait time was not 15 minutes. Corrected.")
            m_content = re.sub(r"WAIT_SECONDS = .*", "WAIT_SECONDS = 15 * 60  # 15 minutes", m_content)
            with open(master_path, 'w', encoding='utf-8') as f:
                f.write(m_content)
        else:
            report.append(f"  [OK] master_runner.py: Wait time is correctly 15 minutes.")
            
        if "automation_daily_log.txt" in m_content:
            report.append(f"  [OK] master_runner.py: Logging system is intact.")
        else:
            report.append(f"  [WARNING] master_runner.py: Logging system missing!")

    for t in teams:
        team_dir = os.path.join(base_dir, f"Team {t}")
        
        # 2. Audit process_team_*.py
        proc_path = os.path.join(team_dir, f"process_team_{t.lower()}.py")
        if os.path.exists(proc_path):
            with open(proc_path, 'r', encoding='utf-8') as f:
                p_content = f.read()
            
            p_changed = False
            
            # Check Overdue Task Count
            if "'Overdue Task Count':" not in p_content and '"Overdue Task Count":' not in p_content:
                report.append(f"  [FIXED] process_team_{t.lower()}.py: Replaced 'Task Count' with 'Overdue Task Count'")
                p_content = p_content.replace("'Task Count':", "'Overdue Task Count':").replace('"Task Count":', '"Overdue Task Count":')
                p_changed = True
            
            # Check date logic
            if "today_str" not in p_content or "_{today_str}.xlsx" not in p_content:
                report.append(f"  [FIXED] process_team_{t.lower()}.py: Date logic was missing or malformed. Corrected.")
                # Basic fix for any straggling Final_Report strings
                p_content = re.sub(
                    r'final_file\s*=\s*os\.path\.join\([^,]+,\s*f"\{safe_l1\}_Final_Report\.xlsx"\)',
                    r'today_str = datetime.today().strftime("%d-%m-%Y")\n        final_file = os.path.join(out_dir, f"{safe_l1}_{today_str}.xlsx")',
                    p_content
                )
                p_content = p_content.replace(
                    "png_file = final_file.replace('.xlsx', '_Screenshot.png')",
                    "png_file = final_file.replace('.xlsx', '.png')"
                )
                if "from datetime import datetime" not in p_content:
                    p_content = "from datetime import datetime\n" + p_content
                p_changed = True
                
            if p_changed:
                with open(proc_path, 'w', encoding='utf-8') as f:
                    f.write(p_content)
            else:
                report.append(f"  [OK] process_team_{t.lower()}.py: Headers and Date Logic perfect.")

        # 3. Audit send_team_*.py
        send_path = os.path.join(team_dir, f"send_team_{t.lower()}.py")
        if os.path.exists(send_path):
            with open(send_path, 'r', encoding='utf-8') as f:
                s_content = f.read()
                
            s_changed = False
            
            # Re-enable Team H
            if t == "H":
                if "# requests.post(COMMIT_URL" in s_content or "# requests.post(MESSAGE_URL" in s_content:
                    report.append(f"  [FIXED] send_team_h.py: Re-enabled L1 Chat Sends.")
                    s_content = s_content.replace('# requests.post(COMMIT', 'requests.post(COMMIT')
                    s_content = s_content.replace('# requests.post(MESSAGE', 'requests.post(MESSAGE')
                    # Remove the pass statement we added earlier
                    s_content = s_content.replace('if img_disk_id:\n                    pass\n                    requests.post', 'if img_disk_id:\n                    requests.post')
                    s_changed = True
                else:
                    report.append(f"  [OK] send_team_h.py: L1 Chat Sends already enabled.")
            
            # Check date logic
            if 'excel_file = f"{lead_name}_{today_str}.xlsx"' not in s_content:
                report.append(f"  [FIXED] send_team_{t.lower()}.py: Dispatch date logic missing. Corrected.")
                s_content = re.sub(
                    r'excel_file\s*=\s*f"{lead_name}_Final_Report\.xlsx"',
                    r'today_str = datetime.today().strftime("%d-%m-%Y")\n        excel_file = f"{lead_name}_{today_str}.xlsx"',
                    s_content
                )
                s_content = re.sub(
                    r'img_file\s*=\s*f"{lead_name}_Final_Report_Screenshot\.png"',
                    r'img_file = f"{lead_name}_{today_str}.png"',
                    s_content
                )
                s_changed = True
                
            if s_changed:
                with open(send_path, 'w', encoding='utf-8') as f:
                    f.write(s_content)
            else:
                report.append(f"  [OK] send_team_{t.lower()}.py: Dispatch logic perfect.")

for r in report:
    print(r)
