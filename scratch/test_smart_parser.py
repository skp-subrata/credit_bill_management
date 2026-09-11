import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.his_sync.parsers import normalize_column_name, parse_his_file

def test_smart_header_detection():
    print("==================================================")
    print("TESTING SMART HEADER DETECTION & ALIAS RESOLUTION")
    print("==================================================")

    # Test Case 1: Title row on line 1, headers on line 3
    csv_with_title = """Manipal Hospital Bangalore - Daily Discharge Report 2026
Report Generated At 12-Sep-2026 03:00 AM

UH ID, Patient Name, Admission No, Gender, Age, Admission Date, Discharge Date, Consultant, Payer Name, Unit Code
UHID-9901, SUPRITI SWAIN, IP-9901, Female, 34 Yrs, 01/09/2026 10:30, 04/09/2026 15:50, Dr. Rajesh Sharma, Star Health, MH-BLR-01
UHID-9902, AMIT KUMAR, IP-9902, Male, 45 Yrs, 05/09/2026 14:15, , Dr. Anita Verma, Star Health, MH-BLR-01
"""

    parsed = parse_his_file("Discharge Report - eMIS.xls", csv_with_title.encode('utf-8'))
    print(f"\nParsed {len(parsed)} rows from file with title rows.")
    for idx, r in enumerate(parsed, start=1):
        print(f"\nRow #{idx}:")
        print(f"  UHID: '{r.get('UHID')}'")
        print(f"  PATIENTNAME: '{r.get('PATIENTNAME')}'")
        print(f"  IPNUMBER: '{r.get('IPNUMBER')}'")
        print(f"  ADMITTEDDATE: '{r.get('ADMITTEDDATE')}'")
        print(f"  CLOSINGDATE: '{r.get('CLOSINGDATE')}'")
        print(f"  PRIMARYDOCTOR: '{r.get('PRIMARYDOCTOR')}'")
        print(f"  COMPANYNAME: '{r.get('COMPANYNAME')}'")
        print(f"  LOCATIONID: '{r.get('LOCATIONID')}'")

if __name__ == '__main__':
    test_smart_header_detection()

