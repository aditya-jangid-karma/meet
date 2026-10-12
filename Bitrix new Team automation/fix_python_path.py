import os
import sys

directories = [
    r"c:\Users\Meet Patel\Desktop\Bitrix new Team khushi automation",
    r"\\10.0.8.33\Karma Automation\Bitrix Team Task Automation"
]

for base_dir in directories:
    # 1. Update master_runner.py
    master_path = os.path.join(base_dir, "master_runner.py")
    if os.path.exists(master_path):
        with open(master_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        content = content.replace('subprocess.run(["python", script_name]', 'subprocess.run([sys.executable, script_name]')
        
        with open(master_path, 'w', encoding='utf-8') as f:
            f.write(content)

    # 2. Update demo_scheduler.py
    demo_path = os.path.join(base_dir, "demo_scheduler.py")
    if os.path.exists(demo_path):
        with open(demo_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        if "import sys" not in content:
            content = "import sys\n" + content
            
        content = content.replace('subprocess.run(["python", "master_runner.py"]', 'subprocess.run([sys.executable, "master_runner.py"]')
        
        with open(demo_path, 'w', encoding='utf-8') as f:
            f.write(content)

    # 3. Update daily_scheduler.py
    daily_path = os.path.join(base_dir, "daily_scheduler.py")
    if os.path.exists(daily_path):
        with open(daily_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        if "import sys" not in content:
            content = "import sys\n" + content
            
        content = content.replace('subprocess.run(["python", "master_runner.py"]', 'subprocess.run([sys.executable, "master_runner.py"]')
        
        with open(daily_path, 'w', encoding='utf-8') as f:
            f.write(content)

print("Updated all orchestrators to use sys.executable!")
