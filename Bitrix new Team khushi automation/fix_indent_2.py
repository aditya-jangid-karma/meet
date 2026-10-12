import re

for filename in ['Team H/process_team_h.py', 'Team D/process_team_d.py']:
    with open(filename, 'r') as f:
        content = f.read()
        
    target = '''            if isinstance(next_pages, dict):
                for k, start_val in next_pages.items():
                next_cmd[k] = base_cmd[k] + f'&start={start_val}'
                
            active_cmd = next_cmd'''
            
    replacement = '''            if isinstance(next_pages, dict):
                for k, start_val in next_pages.items():
                    next_cmd[k] = base_cmd[k] + f'&start={start_val}'
                
            active_cmd = next_cmd'''
                
    new_content = content.replace(target, replacement)
    
    if new_content != content:
        with open(filename, 'w') as f:
            f.write(new_content)
        print(f"Fixed indent in {filename}")

