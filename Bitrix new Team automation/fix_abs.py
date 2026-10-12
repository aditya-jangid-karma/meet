import os

for filename in ['Team H/process_team_h.py', 'Team D/process_team_d.py']:
    with open(filename, 'r') as f:
        content = f.read()
        
    target_logic = "excel2img.export_img(final_file, png_file, \"Overview\", None)"
    replacement_logic = "excel2img.export_img(os.path.abspath(final_file), os.path.abspath(png_file), \"Overview\", None)"
    
    new_content = content.replace(target_logic, replacement_logic)
    
    if new_content != content:
        with open(filename, 'w') as f:
            f.write(new_content)
        print(f"Updated {filename}")
    else:
        print(f"Target logic not found in {filename}")

