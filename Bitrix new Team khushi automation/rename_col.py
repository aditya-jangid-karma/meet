import os

base_dir = r"\\10.0.8.33\Karma Automation\Bitrix Team Task Automation"
teams = ["B", "C", "D", "F", "H", "I"]

for t in teams:
    path = os.path.join(base_dir, f"Team {t}", f"process_team_{t.lower()}.py")
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        content = content.replace("'Task Count':", "'Overdue Task Count':")
        content = content.replace('"Task Count":', '"Overdue Task Count":')
        
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Updated header in Team {t}")
