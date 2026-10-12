import win32com.client
import os

fn_excel = os.path.abspath(r"Team H\Rahul_Gajera_Final_Report.xlsx")
print(f"Opening: {fn_excel}")
print(f"Exists: {os.path.exists(fn_excel)}")

try:
    excel = win32com.client.Dispatch("Excel.Application")
    excel.Visible = False
    excel.DisplayAlerts = False
    
    wb = excel.Workbooks.Open(fn_excel)
    print("Success!")
    wb.Close(False)
    excel.Quit()
except Exception as e:
    import traceback
    traceback.print_exc()
    try:
        excel.Quit()
    except:
        pass
