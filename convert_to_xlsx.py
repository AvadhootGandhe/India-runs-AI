"""
Convert submission.csv to XLSX format with formatting
"""

import pandas as pd
from pathlib import Path
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

def convert_to_xlsx(csv_file, xlsx_file):
    # Read CSV
    df = pd.read_csv(csv_file)
    
    # Write to XLSX
    df.to_excel(xlsx_file, index=False, sheet_name='Ranked Candidates')
    
    # Format the workbook
    wb = openpyxl.load_workbook(xlsx_file)
    ws = wb.active
    
    # Define styles
    header_fill = PatternFill(start_color='4472C4', end_color='4472C4', fill_type='solid')
    header_font = Font(bold=True, color='FFFFFF', size=12)
    border = Border(
        left=Side(style='thin'),
        right=Side(style='thin'),
        top=Side(style='thin'),
        bottom=Side(style='thin')
    )
    
    # Format header row
    for cell in ws[1]:
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
        cell.border = border
    
    # Format data rows
    for row in ws.iter_rows(min_row=2, max_row=ws.max_row):
        for cell in row:
            cell.border = border
            cell.alignment = Alignment(horizontal='left', vertical='top', wrap_text=True)
            
            # Format numeric columns
            if cell.column == 1:  # rank
                cell.alignment = Alignment(horizontal='center', vertical='center')
            elif cell.column == 3:  # score
                cell.number_format = '0.0000'
                cell.alignment = Alignment(horizontal='center', vertical='center')
    
    # Auto-adjust column widths
    ws.column_dimensions['A'].width = 8   # rank
    ws.column_dimensions['B'].width = 15  # candidate_id
    ws.column_dimensions['C'].width = 12  # score
    ws.column_dimensions['D'].width = 120 # reasoning
    
    # Freeze header row
    ws.freeze_panes = 'A2'
    
    # Save
    wb.save(xlsx_file)
    print(f"✓ Converted {csv_file} → {xlsx_file}")

if __name__ == '__main__':
    import sys
    csv_path = Path("submission.csv")
    xlsx_path = Path("ranked_candidates.xlsx")
    
    if csv_path.exists():
        convert_to_xlsx(str(csv_path), str(xlsx_path))
        print(f"✓ File saved to: {xlsx_path.absolute()}")
    else:
        print(f"Error: {csv_path} not found")
        sys.exit(1)
