import re

for filename in ['Team H/process_team_h.py', 'Team D/process_team_d.py']:
    with open(filename, 'r') as f:
        content = f.read()
        
    target_regex = r"# Removed the global styling loop for task sheets because build_grouped_sheet already handles it properly\s+print\(f\"Could not generate screenshot: \{e\}\"\)"
    
    replacement = '''# Removed the global styling loop for task sheets because build_grouped_sheet already handles it properly
            
            try:
                import excel2img
                png_file = final_file.replace('.xlsx', '.png')
                excel2img.export_img(final_file, png_file, "Overview", None)
            except Exception as e:
                print(f"Could not generate screenshot: {e}")'''
                
    content = re.sub(target_regex, replacement, content)
    
    with open(filename, 'w') as f:
        f.write(content)
        
    print(f"Fixed {filename}")
