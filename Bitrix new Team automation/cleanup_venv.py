import os
import shutil

directories = [
    r"c:\Users\Meet Patel\Desktop\Bitrix new Team khushi automation",
    r"\\10.0.8.33\Karma Automation\Bitrix Team Task Automation"
]

for base_dir in directories:
    # 1. Delete START_AUTOMATION.bat
    bat = os.path.join(base_dir, "START_AUTOMATION.bat")
    if os.path.exists(bat):
        os.remove(bat)
        
    # 2. Delete .venv (on server it's in the parent folder of Bitrix Team Task Automation)
    # Wait, the user said .venv was in Karma Automation\.venv
    parent_dir = os.path.dirname(base_dir)
    venv_dir = os.path.join(parent_dir, ".venv")
    if os.path.exists(venv_dir):
        try:
            shutil.rmtree(venv_dir)
            print(f"Deleted {venv_dir}")
        except Exception as e:
            print(f"Failed to delete {venv_dir}: {e}")

    # 3. Update schedulers to remove the get_python_exe logic and just use sys.executable
    for script in ["daily_scheduler.py", "demo_scheduler.py", "master_runner.py"]:
        script_path = os.path.join(base_dir, script)
        if os.path.exists(script_path):
            with open(script_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # Strip out the custom get_python_exe block
            if "def get_python_exe():" in content:
                # Simplistic replace, since it's hardcoded
                import re
                content = re.sub(r'def get_python_exe\(\):[\s\S]*?return sys\.executable\n\n', '', content)
                content = content.replace("python_exe = get_python_exe()", "")
                content = content.replace("subprocess.run([python_exe,", "subprocess.run([sys.executable,")
                
            with open(script_path, 'w', encoding='utf-8') as f:
                f.write(content)

print("Cleanup complete!")
