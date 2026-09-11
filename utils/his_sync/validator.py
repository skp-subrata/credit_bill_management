from database import db
from models import HospitalUnit, HISPayerMapping, DoctorMaster, HISDoctorMapping, Patient, IPAdmission
from utils.his_sync.normalizers import normalize_string, parse_datetime_safe

def validate_staging_batch(batch_id):
    """
    Validate every row in the staging batch.
    Sets validation_status to VALID, INVALID, WARNING, or MAPPING_PENDING.
    """
    from models import HISIPStaging, SyncBatch

    batch = SyncBatch.query.get(batch_id)
    if not batch:
        return

    batch.batch_status = 'VALIDATING'
    db.session.commit()

    staging_rows = HISIPStaging.query.filter_by(batch_id=batch_id).all()

    # Pre-fetch lookup structures for performance
    units_by_id = {str(u.unit_id): u for u in HospitalUnit.query.all()}
    units_by_code = {u.unit_code.upper(): u for u in HospitalUnit.query.all()}
    payer_mappings = {m.normalized_company_name: m for m in HISPayerMapping.query.filter_by(active=True).all()}

    valid_cnt = 0
    invalid_cnt = 0
    mapping_pending_cnt = 0
    updated_cnt = 0
    new_cnt = 0
    unchanged_cnt = 0

    seen_in_batch = set()

    for row in staging_rows:
        errors = []
        status = 'VALID'
        classification = 'NEW'

        uhid = normalize_string(row.uhid)
        ipnumber = normalize_string(row.ipnumber)
        locationid = normalize_string(row.locationid)
        patientname = normalize_string(row.patientname)
        companyname = normalize_string(row.companyname)

        # 1. Mandatory Fields Validation
        if not uhid:
            errors.append("Missing mandatory UHID")
        if not ipnumber:
            errors.append("Missing mandatory IPNUMBER")
        if not patientname:
            errors.append("Missing mandatory PATIENTNAME")
        if not locationid:
            errors.append("Missing mandatory LOCATIONID")

        # 2. Location ID Validation
        unit = units_by_id.get(locationid) or units_by_code.get(locationid.upper())
        if not unit:
            errors.append(f"Invalid Hospital Unit / Location ID '{locationid}'")

        # 3. Date & Time Validation
        admitted_date, _ = parse_datetime_safe(row.admitteddate)
        closing_date, _ = parse_datetime_safe(row.closingdate)

        if row.admitteddate and not admitted_date:
            errors.append(f"Unparseable ADMITTEDDATE '{row.admitteddate}'")

        if row.closingdate and not closing_date:
            errors.append(f"Unparseable CLOSINGDATE '{row.closingdate}'")

        if admitted_date and closing_date and closing_date < admitted_date:
            errors.append(f"CLOSINGDATE '{closing_date}' cannot precede ADMITTEDDATE '{admitted_date}'")

        # 4. Batch Row Duplicate Check
        batch_key = f"{locationid}:{ipnumber}"
        if batch_key in seen_in_batch:
            classification = 'DUPLICATE'
            errors.append(f"Duplicate IP Number '{ipnumber}' within same upload file")
        else:
            seen_in_batch.add(batch_key)

        # 5. Payer Mapping Resolution Check
        if companyname and companyname.upper() not in ('CASH', 'SELF', 'SELF PAY', 'DIRECT'):
            mapped_payer = payer_mappings.get(companyname)
            if not mapped_payer:
                status = 'MAPPING_PENDING'
                classification = 'MAPPING_PENDING'
                errors.append(f"Payer company '{companyname}' requires mapping")

        # 6. Change & Existing Record Classification
        if unit and ipnumber and not errors:
            existing_adm = IPAdmission.query.filter_by(unit_id=unit.unit_id, ip_number=ipnumber).first()
            if existing_adm:
                # Compare status
                new_status = 'DISCHARGED' if closing_date else 'ADMITTED'
                if existing_adm.admission_status != new_status:
                    classification = 'UPDATED'
                else:
                    classification = 'UNCHANGED'
            else:
                classification = 'NEW'

        if errors:
            if status != 'MAPPING_PENDING':
                status = 'INVALID'
                classification = 'INVALID'

        row.validation_status = status
        row.validation_error = " | ".join(errors) if errors else ""
        row.classification = classification

        if status == 'VALID':
            valid_cnt += 1
            if classification == 'NEW':
                new_cnt += 1
            elif classification == 'UPDATED':
                updated_cnt += 1
            elif classification == 'UNCHANGED':
                unchanged_cnt += 1
        elif status == 'MAPPING_PENDING':
            mapping_pending_cnt += 1
        else:
            invalid_cnt += 1

    batch.total_records = len(staging_rows)
    batch.invalid_records = invalid_cnt
    batch.mapping_pending_records = mapping_pending_cnt
    batch.new_records = new_cnt
    batch.updated_records = updated_cnt
    batch.unchanged_records = unchanged_cnt
    batch.batch_status = 'VALIDATED'

    db.session.commit()
