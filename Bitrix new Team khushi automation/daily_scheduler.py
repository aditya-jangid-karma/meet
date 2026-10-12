import time
from datetime import datetime, timedelta
import subprocess
import os
import sys

def wait_until_noon():
    now = datetime.now()
    target = now.replace(hour=12, minute=0, second=0, microsecond=0)
    if now >= target:
        target += timedelta(days=1)
        
    wait_seconds = (target - now).total_seconds()
    print(f"[{now.strftime('%I:%M:%S %p')}] Sleeping... The automation will automatically run at {target.strftime('%m/%d/%Y %I:%M %p')}")
    time.sleep(wait_seconds)

def main():
    print("==================================================")
    print("   PYTHON 24/7 AUTOMATIC DAILY SCHEDULER ACTIVE   ")
    print("==================================================")
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)
    
    while True:
        wait_until_noon()
        
        print("\n==================================================")
        print(f"[{datetime.now().strftime('%I:%M %p')}] IT IS 12:00 PM! TRIGGERING MASTER RUNNER...")
        print("==================================================")
        
        
        try:
            subprocess.run([sys.executable, "master_runner.py"], check=True)
            print(f"\n[{datetime.now().strftime('%I:%M %p')}] Master Runner finished executing for the day!")
        except Exception as e:
            print(f"\n[X] Error executing Master Runner: {e}")
            
        print("Resetting timer for tomorrow...\n")

if __name__ == '__main__':
    main()
