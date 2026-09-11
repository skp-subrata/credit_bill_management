import csv
from io import StringIO, BytesIO
from datetime import datetime
from openpyxl import Workbook

def calculate_aging_category(bill_date_str):
    """
    Calculate bill aging category based on bill date vs current date.
    Categories: 0-3 days, 4-7 days, 8-15 days, 16-30 days, 31-60 days, >60 days
    """
    if not bill_date_str:
        return "Unknown"
    try:
        bdate = datetime.strptime(bill_date_str, "%Y-%m-%d")
        delta = (datetime.now() - bdate).days
        if delta <= 3:
            return "0–3 days"
        elif delta <= 7:
            return "4–7 days"
        elif delta <= 15:
            return "8–15 days"
        elif delta <= 30:
            return "16–30 days"
        elif delta <= 60:
            return "31–60 days"
        else:
            return ">60 days"
    except Exception:
        return "Unknown"

def generate_csv_report(headers, rows):
    """Generate CSV string from header list and row data."""
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(headers)
    for r in rows:
        writer.writerow(r)
    return output.getvalue()

def generate_excel_report(sheet_name, headers, rows):
    """Generate OpenPyXL Excel workbook bytes."""
    wb = Workbook()
    ws = wb.active
    ws.title = sheet_name[:31]

    # Write headers
    ws.append(headers)

    # Write data rows
    for r in rows:
        ws.append(r)

    # Format header row
    for cell in ws[1]:
        cell.font = cell.font.copy(bold=True)

    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer.getvalue()

