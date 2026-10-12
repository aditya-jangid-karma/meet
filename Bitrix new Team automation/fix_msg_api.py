import os
import glob

# Scripts to fix
files = ["Team H/send_team_h.py", "Team D/send_team_d.py", "Team C/send_team_c.py", "Team I/send_team_i.py", "Team B/send_team_b.py"]

for filepath in files:
    if os.path.exists(filepath):
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Add the MESSAGE_URL
        if "MESSAGE_URL =" not in content:
            content = content.replace('COMMIT_URL = "https://karma.bitrix24.in/rest/311/ddg2z5eo9ouw706q/im.disk.file.commit"', 
                                      'COMMIT_URL = "https://karma.bitrix24.in/rest/311/ddg2z5eo9ouw706q/im.disk.file.commit"\nMESSAGE_URL = "https://karma.bitrix24.in/rest/311/ddg2z5eo9ouw706q/im.message.add"')
        
        # Replace COMMIT_URL with MESSAGE_URL in the ZERO TASKS block
        parts = content.split("Sending ZERO TASKS message")
        if len(parts) > 1:
            part1 = parts[0]
            part2 = parts[1]
            
            # In part2, we have two requests.post(COMMIT_URL...) that we need to change to MESSAGE_URL
            part2 = part2.replace("requests.post(COMMIT_URL,", "requests.post(MESSAGE_URL,")
            
            content = part1 + "Sending ZERO TASKS message" + part2
            
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Fixed {filepath}")

