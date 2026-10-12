import re

for filename in ['Team H/process_team_h.py', 'Team D/process_team_d.py']:
    with open(filename, 'r') as f:
        content = f.read()
        
    target = '''            next_pages = batch_resp.get('result', {}).get('result_next', {})
            next_cmd = {}
            for k, start_val in next_pages.items():'''
            
    replacement = '''            next_pages = batch_resp.get('result', {}).get('result_next', {})
            next_cmd = {}
            if isinstance(next_pages, dict):
                for k, start_val in next_pages.items():'''
                
    new_content = content.replace(target, replacement)
    
    if new_content != content:
        with open(filename, 'w') as f:
            f.write(new_content)
        print(f"Fixed {filename}")

