import os
import excel2img

final_file = os.path.abspath(r"Team H\Rahul_Gajera_Final_Report.xlsx")
png_file = os.path.abspath(r"Team H\Rahul_Gajera_Final_Report_Screenshot.png")

try:
    excel2img.export_img(final_file, png_file, "Overview", None)
    print("SUCCESS")
except Exception as e:
    print(f"FAILED: {e}")
