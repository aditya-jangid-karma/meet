import os
import shutil

base_dir = r"\\10.0.8.33\Karma Automation\Bitrix Team Task Automation"
teams = ["B", "C", "D", "F", "H", "I"]

deleted = []
for t in teams:
    team_dir = os.path.join(base_dir, f"Team {t}")
    if os.path.exists(team_dir):
        # Delete output folders
        out_folder = os.path.join(team_dir, f"team_{t.lower()}_output")
        if os.path.exists(out_folder):
            shutil.rmtree(out_folder)
            deleted.append(f"Team {t} output folder")
        
        # Delete pycache
        pycache = os.path.join(team_dir, "__pycache__")
        if os.path.exists(pycache):
            shutil.rmtree(pycache)
            deleted.append(f"Team {t} __pycache__")
            
        # Delete stray screenshots in Team H root (from older bugs)
        for f in os.listdir(team_dir):
            if f.endswith(".png") or f.endswith(".xlsx"):
                os.remove(os.path.join(team_dir, f))
                deleted.append(f"Stray file {f} in Team {t}")

print(f"DELETED ITEMS: {', '.join(deleted) if deleted else 'Nothing to delete.'}")
