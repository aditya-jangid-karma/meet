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
        proc_path = os.path.join(base_dir, f"Team {t}", f"process_team_{t.lower()}.py")
        if os.path.exists(proc_path):
            with open(proc_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Ensure datetime is imported
            if "from datetime import datetime" not in content:
                content = "from datetime import datetime\n" + content
                
            # Replace final_file logic
            content = re.sub(
                r'final_file\s*=\s*os\.path\.join\([^,]+,\s*f"\{safe_l1\}_Final_Report\.xlsx"\)',
                r'today_str = datetime.today().strftime("%d-%m-%Y")\n        final_file = os.path.join(out_dir, f"{safe_l1}_{today_str}.xlsx")',
                content
            )
            # Replace PNG replace logic
            content = content.replace(
                "png_file = final_file.replace('.xlsx', '_Screenshot.png')",
                "png_file = final_file.replace('.xlsx', '.png')"
            )
            
            with open(proc_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            print(f"Fixed {proc_path}")

