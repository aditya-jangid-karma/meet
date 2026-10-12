import re

for filename in ['Team H/process_team_h.py', 'Team D/process_team_d.py']:
    with open(filename, 'r') as f:
        content = f.read()
        
    # We need to make sure 'import time' is at the top
    if 'import time' not in content:
        content = 'import time\n' + content
        
    target_logic = "wb.save(final_file)\n            print(f\"Saved {final_file}\")\n            \n            try:"
    replacement_logic = "wb.save(final_file)\n            print(f\"Saved {final_file}\")\n            time.sleep(2)\n            \n            try:"
    
    new_content = content.replace(target_logic, replacement_logic)
    
    if new_content != content:
        with open(filename, 'w') as f:
            f.write(new_content)
        print(f"Updated {filename}")
    else:
        print(f"Target logic not found in {filename}")

