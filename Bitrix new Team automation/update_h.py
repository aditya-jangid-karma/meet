import re
with open('Team H/process_team_h.py', 'r') as f:
    content = f.read()

# Define the build_grouped_sheet function to insert before main()
helper_func = '''
def build_grouped_sheet(ws, tasks_data):
    if not tasks_data:
        return
        
    df = pd.DataFrame(tasks_data)
    
    type_order = {'Overdue (Old)': 0, 'Due Today': 1, 'Due Tomorrow': 2}
    df['Type_Sort'] = df['Type'].map(type_order).fillna(3)
    df = df.sort_values(by=['Client', 'Type_Sort', 'Deadline'])
    
    headers = ['Type', 'Client', 'Task ID', 'Task Title', 'Deadline', 'Responsible Person', 'Status']
    header_fill = PatternFill(start_color="1A3B69", end_color="1A3B69", fill_type="solid")
    header_font = Font(color="FFFFFF", bold=True)
    group_font = Font(size=14, bold=True)
    
    thin_border = Border(left=Side(style='thin'), right=Side(style='thin'), 
                         top=Side(style='thin'), bottom=Side(style='thin'))
                         
    row_idx = 1
    
    for client, group in df.groupby('Client', sort=False):
        code = group.iloc[0].get('Client Code', '')
        ws.cell(row=row_idx, column=1, value=f"{code} {client}").font = group_font
        ws.merge_cells(start_row=row_idx, start_column=1, end_row=row_idx, end_column=len(headers))
        row_idx += 1
        
        for col_idx, h in enumerate(headers, 1):
            c = ws.cell(row=row_idx, column=col_idx, value=h)
            c.fill = header_fill
            c.font = header_font
        row_idx += 1
        
        for _, row in group.iterrows():
            vals = [
                row.get('Type', ''), row.get('Client', ''), row.get('Task ID', ''),
                row.get('Task Title', ''), row.get('Deadline', ''),
                row.get('Responsible Person', ''), row.get('Status', '')
            ]
            for col_idx, val in enumerate(vals, 1):
                c = ws.cell(row=row_idx, column=col_idx, value=val)
                c.border = thin_border
            row_idx += 1
            
        row_idx += 1
        
    ws.column_dimensions['A'].width = 15
    ws.column_dimensions['B'].width = 25
    ws.column_dimensions['C'].width = 12
    ws.column_dimensions['D'].width = 45
    ws.column_dimensions['E'].width = 15
    ws.column_dimensions['F'].width = 25
    ws.column_dimensions['G'].width = 15

'''

if 'def build_grouped_sheet' not in content:
    content = content.replace('def main():', helper_func + '\ndef main():')

# Replace the df_all pandas logic with manual openpyxl logic
target_block = '''            df_all = pd.DataFrame(all_tasks_data)
            if not df_all.empty:
                df_all = df_all.sort_values(by=['Client', 'Deadline'])
            
            # Write All Client Groups (renamed from All Overdue Tasks to match Team H)
            df_all.to_excel(writer, sheet_name='All Client Groups', index=False)
            
            # Create a tab for each unique Responsible Person
            if not df_all.empty:
                resp_persons = df_all['Responsible Person'].unique()
                for rp in resp_persons:
                    if not rp or rp == 'Unknown': continue
                    safe_name = re.sub(r'[\\/*?:\[\]]', '', str(rp))[:31]
                    df_rp = df_all[df_all['Responsible Person'] == rp]
                    df_rp.to_excel(writer, sheet_name=safe_name, index=False)'''

replacement_block = '''            wb = writer.book
            
            # Write All Client Groups with grouping layout
            if all_tasks_data:
                ws_all = wb.create_sheet('All Client Groups')
                build_grouped_sheet(ws_all, all_tasks_data)
                
                # Create a tab for each unique Responsible Person
                df_all = pd.DataFrame(all_tasks_data)
                resp_persons = df_all['Responsible Person'].unique()
                for rp in resp_persons:
                    if not rp or rp == 'Unknown': continue
                    safe_name = re.sub(r'[\\\\/*?:\\[\\]]', '', str(rp))[:31]
                    rp_tasks = [t for t in all_tasks_data if t.get('Responsible Person') == rp]
                    ws_rp = wb.create_sheet(safe_name)
                    build_grouped_sheet(ws_rp, rp_tasks)'''

content = content.replace(target_block, replacement_block)

# Also need to make sure the style loop doesn't overwrite our nice grouped layout headers!
style_target = '''            for sheet_name in wb.sheetnames:
                if sheet_name == 'Overview': continue
                s = wb[sheet_name]
                s.freeze_panes = 'A2'
                
                # Headers
                for col_idx in range(1, s.max_column + 1):
                    c = s.cell(row=1, column=col_idx)
                    c.fill = header_fill
                    c.font = Font(color="FFFFFF", bold=True)
                
                # Alternate row colors
                for row_idx in range(2, s.max_row + 1):
                    if row_idx % 2 == 0:
                        for col_idx in range(1, s.max_column + 1):
                            s.cell(row=row_idx, column=col_idx).fill = alt_fill'''

style_replacement = '''            # Removed the global styling loop for task sheets because build_grouped_sheet already handles it properly'''

content = content.replace(style_target, style_replacement)

with open('Team H/process_team_h.py', 'w') as f:
    f.write(content)
print("Updated process_team_h.py")
