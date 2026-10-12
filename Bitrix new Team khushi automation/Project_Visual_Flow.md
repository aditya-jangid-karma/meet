# Project Visual Flowchart (Detailed End-to-End Logic)

This flowchart visualizes the complete step-by-step logic of the automation, including the newly added logic for sending congratulatory messages when a team member has zero active overdue tasks.

```mermaid
flowchart TD
    %% Styling Definitions
    classDef python fill:#e1f5fe,stroke:#03a9f4,stroke-width:2px;
    classDef bitrix fill:#e8f5e9,stroke:#4caf50,stroke-width:2px;
    classDef localfile fill:#fff3e0,stroke:#ff9800,stroke-width:2px;
    classDef delivery fill:#f3e5f5,stroke:#9c27b0,stroke-width:2px;
    classDef condition fill:#fff9c4,stroke:#fbc02d,stroke-width:2px;

    Start([🚀 Start Automation]) --> Phase1
    
    subgraph Phase 1: Data Extraction & Filtering
        Phase1(Execute process_team.py)
        Phase1 --> B1[Fetch All Projects from Bitrix API]
        B1 --> Cond1{Does Project Name match\nRegex & Team Letter?}
        Cond1 -->|No| Skip1[Skip Project]
        Cond1 -->|Yes| B2[Batch Fetch Tasks via Pagination]
        
        B2 --> Cond2{Is Task Status = Completed?}
        Cond2 -->|Yes| Skip2[Skip Task]
        Cond2 -->|No| Cond3{Does Task have a Deadline?}
        Cond3 -->|No| Skip2
        
        Cond3 -->|Yes| F1{Categorize by Deadline Date}
        F1 -->|< Today 00:00| C1[🔴 Overdue Array]
        F1 -->|>= Today & < Tomorrow 00:00| C2[🟡 Due Today Array]
        F1 -->|>= Tomorrow & < Next Day| C3[🟢 Due Tomorrow Array]
        F1 -->|> Next Day| Skip2
    end

    subgraph Phase 2: Report Generation
        C1 & C2 & C3 --> Group[Group Tasks by L1 Project Lead]
        Group --> Cond4{Does Lead have > 0 total tasks?}
        Cond4 -->|No| Skip3[Skip Lead\nDo Not Generate Excel]
        Cond4 -->|Yes| G1[Generate Styled Excel Report\nOverview + Detailed Sheets]
        G1 --> G2[Attempt to take PNG Screenshot\nusing excel2img COM Object]
    end

    subgraph Phase 3: Delivery
        G2 -.-> S1
        Skip3 -.-> S1
        S1(Execute send_team.py)
        
        S1 --> Cond7{Did process_team.py\ngenerate an Excel file?}
        
        %% Path A: Has Tasks
        Cond7 -->|Yes| Cond5{Did screenshot generate?}
        Cond5 -->|Yes| Up1[Upload Excel & PNG to Bitrix Drive]
        Cond5 -->|No| Up2[Upload ONLY Excel to Bitrix Drive]
        Up1 & Up2 --> D1[📬 Send to Lead's Mapped Chat\nMessage 1: PNG Image\nMessage 2: Excel File]
        D1 --> D3[📬 Send Copy to Testing Channel]
        
        %% Path B: No Tasks
        Cond7 -->|No| D2[📬 Send ZERO TASKS Message\n'Great news! You have no tasks...'\nDirect to Lead's Mapped Chat]
        D2 --> D4[📬 Send Copy to Testing Channel]
    end
    
    Skip1 -.-> End
    Skip2 -.-> End
    D3 --> End([🏁 End Automation])
    D4 --> End

    %% Class Assignments
    class Phase1,Skip1,Skip2,Skip3,C1,C2,C3,Group,S1 python;
    class B1,B2,Up1,Up2 bitrix;
    class G1,G2 localfile;
    class D1,D2,D3,D4 delivery;
    class Cond1,Cond2,Cond3,Cond4,Cond5,Cond7,F1 condition;
```
