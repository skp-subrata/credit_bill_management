import csv
import re
from io import StringIO, BytesIO
from openpyxl import load_workbook

EXPECTED_COLUMNS = [
    "UHID", "PATIENTNAME", "IPNUMBER", "GENDER", "AGE", "ADMITTEDDATE",
    "PLANINGDATE", "CLOSINGDATE", "PRIMARYDOCTOR", "NURSECHECKEDOUTTIME",
    "ADMITING_DOCTOR", "ADMITING_DOCTOR_DEPT", "TREATING_DOCTOR", "TREATING_DOCTOR_DEPT",
    "INTERIMDATE", "DISCHARGE_BILLDATE", "BED_OCCUPIED", "SPECIALIZATION",
    "SPECIALIZATIONDESC", "BEDNO", "BEDTYPE", "BILLABLEBED", "BEDNUMBER",
    "WARDNAME", "COMPANYNAME", "REFRALDOCTOR", "CURRENTSTATUS", "REASONANDREMARKS",
    "CONTACTNO", "ADDRESS1", "COUNTRYNAME", "STATENAME", "CITYNAME",
    "DISTRICTNAME", "CREATEDBY", "LOCATIONID"
]

def normalize_column_name(header):
    """Normalize header string by stripping whitespace and non-alphanumeric chars, converting to uppercase."""
    if header is None:
        return ""
    return re.sub(r'[^A-Z0-9]', '', str(header).strip().upper())

# Alias dictionary mapping normalized variations to canonical HIS column names
HEADER_ALIASES = {
    # UHID
    "UHID": "UHID", "UHIDNO": "UHID", "PATIENTID": "UHID", "MRN": "UHID",
    "REGISTRATIONNO": "UHID", "REGNO": "UHID", "PATIENTCODE": "UHID",

    # PATIENTNAME
    "PATIENTNAME": "PATIENTNAME", "PATIENT": "PATIENTNAME", "NAME": "PATIENTNAME",
    "PATIENTFULLNAME": "PATIENTNAME", "PTNAME": "PATIENTNAME",

    # IPNUMBER
    "IPNUMBER": "IPNUMBER", "IPNO": "IPNUMBER", "IPNUM": "IPNUMBER",
    "ADMISSIONNO": "IPNUMBER", "ADMITNO": "IPNUMBER", "ENCOUNTERNO": "IPNUMBER",
    "IPDNO": "IPNUMBER", "INPATIENTNO": "IPNUMBER",

    # GENDER
    "GENDER": "GENDER", "SEX": "GENDER",

    # AGE
    "AGE": "AGE", "PATIENTAGE": "AGE",

    # ADMITTEDDATE
    "ADMITTEDDATE": "ADMITTEDDATE", "ADMISSIONDATE": "ADMITTEDDATE", "ADMITDATE": "ADMITTEDDATE",
    "DOA": "ADMITTEDDATE", "DATEOFADMISSION": "ADMITTEDDATE", "ADMDATE": "ADMITTEDDATE",

    # PLANINGDATE
    "PLANINGDATE": "PLANINGDATE", "PLANNINGDATE": "PLANINGDATE", "EXPECTEDDISCHARGEDATE": "PLANINGDATE",

    # CLOSINGDATE
    "CLOSINGDATE": "CLOSINGDATE", "DISCHARGEDATE": "CLOSINGDATE", "DOD": "CLOSINGDATE",
    "DATEOFDISCHARGE": "CLOSINGDATE", "DISDATE": "CLOSINGDATE", "DISCHARGEBILLDATE": "DISCHARGE_BILLDATE",

    # PRIMARYDOCTOR
    "PRIMARYDOCTOR": "PRIMARYDOCTOR", "DOCTOR": "PRIMARYDOCTOR", "DOCTORNAME": "PRIMARYDOCTOR",
    "CONSULTANT": "PRIMARYDOCTOR", "ATTENDINGDOCTOR": "PRIMARYDOCTOR", "PHYSICIAN": "PRIMARYDOCTOR",

    # NURSECHECKEDOUTTIME
    "NURSECHECKEDOUTTIME": "NURSECHECKEDOUTTIME", "NURSECHECKOUT": "NURSECHECKEDOUTTIME",

    # ADMITING_DOCTOR
    "ADMITINGDOCTOR": "ADMITING_DOCTOR", "ADMITTINGDOCTOR": "ADMITING_DOCTOR",

    # ADMITING_DOCTOR_DEPT
    "ADMITINGDOCTORDEPT": "ADMITING_DOCTOR_DEPT", "ADMITTINGDOCTORDEPT": "ADMITING_DOCTOR_DEPT",

    # TREATING_DOCTOR
    "TREATINGDOCTOR": "TREATING_DOCTOR", "TREATINGDOCTORNAME": "TREATING_DOCTOR",

    # TREATING_DOCTOR_DEPT
    "TREATINGDOCTORDEPT": "TREATING_DOCTOR_DEPT", "SPECIALTY": "TREATING_DOCTOR_DEPT",

    # INTERIMDATE
    "INTERIMDATE": "INTERIMDATE", "INTERIMBILLDATE": "INTERIMDATE",

    # DISCHARGE_BILLDATE
    "DISCHARGEBILLDATE": "DISCHARGE_BILLDATE", "BILLDATE": "DISCHARGE_BILLDATE", "FINALBILLDATE": "DISCHARGE_BILLDATE",

    # BED_OCCUPIED
    "BEDOCCUPIED": "BED_OCCUPIED", "CURRENTBED": "BED_OCCUPIED",

    # SPECIALIZATION
    "SPECIALIZATION": "SPECIALIZATION", "SPECIALIZATIONCODE": "SPECIALIZATION", "DEPARTMENT": "SPECIALIZATION", "DEPT": "SPECIALIZATION",

    # SPECIALIZATIONDESC
    "SPECIALIZATIONDESC": "SPECIALIZATIONDESC", "DEPARTMENTNAME": "SPECIALIZATIONDESC",

    # BEDNO
    "BEDNO": "BEDNO", "BEDNUM": "BEDNO",

    # BEDTYPE
    "BEDTYPE": "BEDTYPE", "ROOMTYPE": "BEDTYPE", "CATEGORY": "BEDTYPE",

    # BILLABLEBED
    "BILLABLEBED": "BILLABLEBED",

    # BEDNUMBER
    "BEDNUMBER": "BEDNUMBER",

    # WARDNAME
    "WARDNAME": "WARDNAME", "WARD": "WARDNAME", "NURSINGSTATION": "WARDNAME",

    # COMPANYNAME
    "COMPANYNAME": "COMPANYNAME", "COMPANY": "COMPANYNAME", "PAYER": "COMPANYNAME",
    "PAYERNAME": "COMPANYNAME", "SPONSOR": "COMPANYNAME", "INSURANCE": "COMPANYNAME",
    "TPA": "COMPANYNAME", "TARIFF": "COMPANYNAME", "BILLINGTYPE": "COMPANYNAME",

    # REFRALDOCTOR
    "REFRALDOCTOR": "REFRALDOCTOR", "REFERRALDOCTOR": "REFRALDOCTOR",

    # CURRENTSTATUS
    "CURRENTSTATUS": "CURRENTSTATUS", "STATUS": "CURRENTSTATUS", "PATIENTSTATUS": "CURRENTSTATUS",

    # REASONANDREMARKS
    "REASONANDREMARKS": "REASONANDREMARKS", "REMARKS": "REASONANDREMARKS", "REASON": "REASONANDREMARKS", "NOTES": "REASONANDREMARKS",

    # CONTACTNO
    "CONTACTNO": "CONTACTNO", "PHONE": "CONTACTNO", "MOBILENO": "CONTACTNO", "MOBILE": "CONTACTNO",

    # ADDRESS1
    "ADDRESS1": "ADDRESS1", "ADDRESS": "ADDRESS1",

    # COUNTRYNAME
    "COUNTRYNAME": "COUNTRYNAME", "COUNTRY": "COUNTRYNAME",

    # STATENAME
    "STATENAME": "STATENAME", "STATE": "STATENAME",

    # CITYNAME
    "CITYNAME": "CITYNAME", "CITY": "CITYNAME",

    # DISTRICTNAME
    "DISTRICTNAME": "DISTRICTNAME", "DISTRICT": "DISTRICTNAME",

    # CREATEDBY
    "CREATEDBY": "CREATEDBY", "USER": "CREATEDBY",

    # LOCATIONID
    "LOCATIONID": "LOCATIONID", "LOCATION": "LOCATIONID", "UNIT": "LOCATIONID",
    "UNITCODE": "LOCATIONID", "HOSPITALUNIT": "LOCATIONID", "BRANCH": "LOCATIONID", "CENTER": "LOCATIONID"
}

def resolve_canonical_header(raw_header):
    norm = normalize_column_name(raw_header)
    return HEADER_ALIASES.get(norm, None)

def _find_best_header_row(rows):
    """
    Find index of header row from first 20 rows by counting known column matches.
    Returns (header_row_index, header_index_map).
    """
    best_idx = 0
    best_score = 0
    best_map = {}

    for idx, row in enumerate(rows[:20]):
        if not row:
            continue
        current_map = {}
        score = 0
        for c_idx, cell in enumerate(row):
            canonical = resolve_canonical_header(cell)
            if canonical and c_idx not in current_map:
                current_map[c_idx] = canonical
                score += 1
        
        if score > best_score:
            best_score = score
            best_idx = idx
            best_map = current_map

    return best_idx, best_map

def _parse_csv(bytes_data):
    try:
        content = bytes_data.decode('utf-8-sig', errors='replace')
    except Exception:
        content = bytes_data.decode('latin-1', errors='replace')
    
    stream = StringIO(content)
    reader = csv.reader(stream)
    all_raw_rows = [r for r in reader if r and any(r)]
    
    if not all_raw_rows:
        return []

    header_idx, header_map = _find_best_header_row(all_raw_rows)
    if not header_map:
        return []

    parsed_rows = []
    for row in all_raw_rows[header_idx + 1:]:
        row_dict = {}
        for col_idx, canonical_col in header_map.items():
            if col_idx < len(row):
                row_dict[canonical_col] = str(row[col_idx]).strip() if row[col_idx] is not None else ""
        if any(row_dict.values()):
            parsed_rows.append(row_dict)

    return parsed_rows

def _parse_excel(bytes_data):
    wb = load_workbook(filename=BytesIO(bytes_data), data_only=True)
    ws = wb.active
    all_raw_rows = []
    for r in ws.iter_rows(values_only=True):
        if r and any(c is not None and str(c).strip() != '' for c in r):
            all_raw_rows.append([str(c).strip() if c is not None else '' for c in r])

    if not all_raw_rows:
        return []

    header_idx, header_map = _find_best_header_row(all_raw_rows)
    if not header_map:
        return []

    parsed_rows = []
    for row in all_raw_rows[header_idx + 1:]:
        row_dict = {}
        for col_idx, canonical_col in header_map.items():
            if col_idx < len(row):
                val = row[col_idx]
                row_dict[canonical_col] = str(val).strip() if val is not None else ""
        if any(row_dict.values()):
            parsed_rows.append(row_dict)

    return parsed_rows

def parse_his_file(file_name, file_bytes):
    """
    Parse Excel (.xlsx) or CSV (.csv) file into a list of row dicts.
    Robust against title rows, leading blank rows, column alias variations, and format mismatches.
    """
    file_name_lower = file_name.lower()

    if file_name_lower.endswith(('.xlsx', '.xls')):
        try:
            res = _parse_excel(file_bytes)
            if res:
                return res
        except Exception:
            pass
        return _parse_csv(file_bytes)
    else:
        try:
            res = _parse_csv(file_bytes)
            if res:
                return res
        except Exception:
            pass
        return _parse_excel(file_bytes)
