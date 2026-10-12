import re

for filename in ['Team H/process_team_h.py', 'Team D/process_team_d.py']:
    with open(filename, 'r') as f:
        content = f.read()
        
    target_logic = '''            total_today = len(td_tasks)
            total_tomorrow = len(tm_tasks)
            
            # Create a row for each person
            for idx, (rname, counts) in enumerate(sorted_persons):
                client_rows.append({
                    'Client Code': code if idx == 0 else '',
                    'Client': client if idx == 0 else '',
                    'Responsible Person': rname,
                    'Overdue Tasks': counts['overdue'],
                    'Due Today': total_today if idx == 0 else '',
                    'Due Tomorrow': total_tomorrow if idx == 0 else ''
                })'''
                
    replacement_logic = '''            # Create a row for each person
            for idx, (rname, counts) in enumerate(sorted_persons):
                client_rows.append({
                    'Client Code': code if idx == 0 else '',
                    'Client': client if idx == 0 else '',
                    'Responsible Person': rname,
                    'Overdue Tasks': counts['overdue'],
                    'Due Today': counts['today'] if counts['today'] > 0 else 0,
                    'Due Tomorrow': counts['tomorrow'] if counts['tomorrow'] > 0 else 0
                })'''
                
    new_content = content.replace(target_logic, replacement_logic)
    
    if new_content != content:
        with open(filename, 'w') as f:
            f.write(new_content)
        print(f"Updated {filename}")
    else:
        print(f"Target logic not found in {filename}")

