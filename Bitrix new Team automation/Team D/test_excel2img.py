import os
import excel2img

final_file = r"team_d_output\Manish_Makvana_Final_Report.xlsx"
png_file = final_file.replace('.xlsx', '_test.png')

try:
    excel2img.export_img(final_file, png_file, "Overview", None)
    print("Relative path SUCCESS")
except Exception as e:
    print(f"Relative path FAILED: {e}")

try:
    abs_file = os.path.abspath(final_file)
    abs_png = os.path.abspath(png_file)
    excel2img.export_img(abs_file, abs_png, "Overview", None)
    print("Absolute path SUCCESS")
except Exception as e:
    print(f"Absolute path FAILED: {e}")
