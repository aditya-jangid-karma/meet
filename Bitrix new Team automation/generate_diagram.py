import zlib
import base64
import requests
import re
import os
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

md_path = r'C:\Users\Meet Patel\.gemini\antigravity\brain\deed56d0-d9ac-4bca-84cd-c195c5f19a4a\Project_Visual_Flow.md'
with open(md_path, 'r', encoding='utf-8') as f:
    text = f.read()

# Extract mermaid code
match = re.search(r'`mermaid\n(.*?)\n`', text, re.DOTALL)
if match:
    mermaid_code = match.group(1).encode('utf-8')
    compressed = zlib.compress(mermaid_code, 9)
    b64 = base64.urlsafe_b64encode(compressed).decode('ascii')
    
    url = f"https://kroki.io/mermaid/png/{b64}"
    resp = requests.get(url, verify=False)
    
    if resp.status_code == 200:
        out_path = os.path.join(os.path.dirname(md_path), 'Flowchart_Image.png')
        with open(out_path, 'wb') as f:
            f.write(resp.content)
        print(f"Successfully generated diagram image at: {out_path}")
    else:
        print(f"Failed to fetch image: {resp.status_code} {resp.text}")
else:
    print("Could not find mermaid block.")
