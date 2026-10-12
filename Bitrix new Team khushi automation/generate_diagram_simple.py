import zlib
import base64
import requests
import re
import os
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Simplified flowchart without classes for Kroki
mermaid_code = '''
flowchart TD
    Start([Start Automation]) --> P1
    
    subgraph Phase 1: Data Extraction & Filtering
        P1(Execute process_team.py) --> B1[Fetch All Projects from Bitrix API]
        B1 --> Cond1{Matches Team Regex?}
        Cond1 -->|No| Skip1[Skip Project]
        Cond1 -->|Yes| B2[Batch Fetch Tasks via Pagination]
        
        B2 --> Cond2{Task Completed?}
        Cond2 -->|Yes| Skip2[Skip Task]
        Cond2 -->|No| Cond3{Has Deadline?}
        Cond3 -->|No| Skip2
        
        Cond3 -->|Yes| F1{Categorize by Date}
        F1 -->|< Today 00:00| C1[Overdue]
        F1 -->|>= Today & < Tomorrow| C2[Due Today]
        F1 -->|>= Tomorrow & < Next Day| C3[Due Tomorrow]
        F1 -->|> Next Day| Skip2
    end

    subgraph Phase 2: Report Generation
        C1 & C2 & C3 --> Group[Group Tasks by L1 Project Lead]
        Group --> Cond4{Lead has > 0 tasks?}
        Cond4 -->|No| Skip3[Skip Lead: Avoid Blank Reports]
        Cond4 -->|Yes| G1[Generate Styled Excel Report]
        G1 --> G2[Attempt PNG Screenshot]
    end

    subgraph Phase 3: Delivery
        G2 --> S1
        S1(Execute send_team.py) --> Cond5{Screenshot generated?}
        
        Cond5 -->|Yes| Up1[Upload Excel & PNG to Bitrix Drive]
        Cond5 -->|No| Up2[Upload ONLY Excel to Bitrix Drive]
        
        Up1 & Up2 --> Cond6{Have Lead's Chat ID?}
        
        Cond6 -->|Yes| D1[Send to L1 Lead Chat]
        D1 --> D2
        
        Cond6 -->|No| D2[Send to Testing Channel]
    end
    
    Skip1 -.-> End
    Skip2 -.-> End
    Skip3 -.-> End
    D2 --> End([End Automation])
'''

compressed = zlib.compress(mermaid_code.encode('utf-8'), 9)
b64 = base64.urlsafe_b64encode(compressed).decode('ascii')

url = f"https://kroki.io/mermaid/png/{b64}"
resp = requests.get(url, verify=False)

out_path = r'C:\Users\Meet Patel\.gemini\antigravity\brain\deed56d0-d9ac-4bca-84cd-c195c5f19a4a\Flowchart_Image.png'
if resp.status_code == 200:
    with open(out_path, 'wb') as f:
        f.write(resp.content)
    print(f"Successfully generated diagram image at: {out_path}")
else:
    print(f"Failed to fetch image: {resp.status_code} {resp.text}")
