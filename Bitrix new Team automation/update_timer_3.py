import os

directories = [
    r"c:\Users\Meet Patel\Desktop\Bitrix new Team khushi automation",
    r"\\10.0.8.33\Karma Automation\Bitrix Team Task Automation"
]

for base_dir in directories:
    master_path = os.path.join(base_dir, "master_runner.py")
    if os.path.exists(master_path):
        with open(master_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Change wait time to 3 minutes
        content = content.replace("WAIT_SECONDS = 5 * 60", "WAIT_SECONDS = 3 * 60")
        content = content.replace("5 minutes", "3 minutes")
        
        with open(master_path, 'w', encoding='utf-8') as f:
            f.write(content)
            
        print(f"Updated wait time to 3 minutes in {master_path}")

