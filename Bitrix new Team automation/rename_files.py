import os
import re

directories = [
    r"c:\Users\Meet Patel\Desktop\Bitrix new Team khushi automation",
    r"\\10.0.8.33\Karma Automation\Bitrix Team Task Automation"
]
teams = ["B", "C", "D", "F", "H", "I"]

for base_dir in directories:
    if not os.path.exists(base_dir):
        continue
        
    for t in teams:
        # Update process_team_*.py
        proc_path = os.path.join(base_dir, f"Team {t}", f"process_team_{t.lower()}.py")
        if os.path.exists(proc_path):
            with open(proc_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Ensure datetime is imported
            if "from datetime import datetime" not in content:
                content = "from datetime import datetime\n" + content
                
            # Replace file names
            content = re.sub(
                r'excel_file\s*=\s*(.*?)"{safe_lead_name}_Final_Report\.xlsx"',
                r'today_str = datetime.today().strftime("%d-%m-%Y")\n            excel_file = \1f"{safe_lead_name}_{today_str}.xlsx"',
                content
            )
            content = re.sub(
                r'img_file\s*=\s*(.*?)"{safe_lead_name}_Final_Report_Screenshot\.png"',
                r'img_file = \1f"{safe_lead_name}_{today_str}.png"',
                content
            )
            
            with open(proc_path, 'w', encoding='utf-8') as f:
                f.write(content)
                
        # Update send_team_*.py
        send_path = os.path.join(base_dir, f"Team {t}", f"send_team_{t.lower()}.py")
        if os.path.exists(send_path):
            with open(send_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Ensure datetime is imported
            if "from datetime import datetime" not in content:
                content = "from datetime import datetime\n" + content
                
            # Replace file names
            content = re.sub(
                r'excel_file\s*=\s*f"{lead_name}_Final_Report\.xlsx"',
                r'today_str = datetime.today().strftime("%d-%m-%Y")\n        excel_file = f"{lead_name}_{today_str}.xlsx"',
                content
            )
            content = re.sub(
                r'img_file\s*=\s*f"{lead_name}_Final_Report_Screenshot\.png"',
                r'img_file = f"{lead_name}_{today_str}.png"',
                content
            )
            
            with open(send_path, 'w', encoding='utf-8') as f:
                f.write(content)

print("Updated filenames to dynamic Today's Date across all teams!")
