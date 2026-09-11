from datetime import datetime
from database import db
from models import (
    SyncBatch, HISIPStaging, Patient, IPAdmission, IPDischarge, 
    HospitalUnit, Payer, HospitalPayer, HISPayerMapping, DoctorMaster, HISDoctorMapping
)
from utils.his_sync.normalizers import normalize_string, parse_datetime_safe
from utils.audit import log_audit

def process_sync_batch(batch_id, user_id=None):
    """
    Idempotent Synchronization Engine.
    Processes VALID and UNCHANGED staging rows into main application tables.
    Respects source authority rules and database transaction safety.
    """
    batch = SyncBatch.query.get(batch_id)
    if not batch:
        return False

    batch.batch_status = 'PROCESSING'
    batch.started_at = datetime.utcnow()
    db.session.commit()

    staging_rows = HISIPStaging.query.filter_by(batch_id=batch_id).filter(
        HISIPStaging.validation_status.in_(['VALID', 'WARNING'])
    ).all()

    units_by_id = {str(u.unit_id): u for u in HospitalUnit.query.all()}
    units_by_code = {u.unit_code.upper(): u for u in HospitalUnit.query.all()}
    payer_mappings = {m.normalized_company_name: m for m in HISPayerMapping.query.filter_by(active=True).all()}

    success_cnt = 0
    failed_cnt = 0

    for row in staging_rows:
        try:
            # Use database savepoint for per-record transaction isolation
            with db.session.begin_nested():
                uhid = normalize_string(row.uhid)
                ipnumber = normalize_string(row.ipnumber)
                locationid = normalize_string(row.locationid)
                patientname = normalize_string(row.patientname)
                companyname = normalize_string(row.companyname)
                primarydoctor = normalize_string(row.primarydoctor)
                treatingdoctor = normalize_string(row.treating_doctor)

                unit = units_by_id.get(locationid) or units_by_code.get(locationid.upper())

                # 1. Patient Upsert
                patient = Patient.query.filter_by(uhid=uhid).first()
                if not patient:
                    patient = Patient(
                        uhid=uhid,
                        patient_name=patientname,
                        gender=normalize_string(row.gender) or 'OTHER',
                        phone=normalize_string(row.contactno),
                        address=normalize_string(row.address1)
                    )
                    db.session.add(patient)
                    db.session.flush()
                else:
                    # Update permitted fields
                    if patientname:
                        patient.patient_name = patientname
                    if row.contactno:
                        patient.phone = normalize_string(row.contactno)

                # 2. Payer Resolution
                payer_id = None
                hospital_payer_id = None
                bill_type = 'CREDIT'

                if companyname and companyname.upper() in ('CASH', 'SELF', 'SELF PAY', 'DIRECT'):
                    bill_type = 'CASH'
                elif companyname:
                    mapped_payer = payer_mappings.get(companyname)
                    if mapped_payer:
                        payer_id = mapped_payer.payer_id
                        bill_type = mapped_payer.bill_type
                        # Lookup hospital payer config
                        hp = HospitalPayer.query.filter_by(unit_id=unit.unit_id, payer_id=payer_id).first()
                        if hp:
                            hospital_payer_id = hp.hospital_payer_id

                # 3. Doctor Resolution
                # 3. Doctor Resolution & Master Upsert
                doctor_name = treatingdoctor or primarydoctor or 'Staff Doctor'
                if doctor_name and doctor_name != 'Staff Doctor':
                    norm_doc = normalize_string(doctor_name)
                    doc_obj = DoctorMaster.query.filter_by(normalized_doctor_name=norm_doc).first()
                    if not doc_obj:
                        dept = normalize_string(row.admiting_doctor_dept or row.treating_doctor_dept or row.specializationdesc) or 'General'
                        spec = normalize_string(row.specializationdesc or row.specialization) or 'General'
                        doc_obj = DoctorMaster(
                            doctor_code=f"DOC-{(hash(norm_doc) & 0xffff):04d}",
                            doctor_name=doctor_name,
                            normalized_doctor_name=norm_doc,
                            department=dept,
                            specialization=spec,
                            unit_id=unit.unit_id if unit else None
                        )
                        db.session.add(doc_obj)
                        db.session.flush()

                    doc_map = HISDoctorMapping.query.filter_by(normalized_doctor_name=norm_doc).first()
                    if not doc_map:
                        doc_map = HISDoctorMapping(
                            source_doctor_name=doctor_name,
                            normalized_doctor_name=norm_doc,
                            doctor_id=doc_obj.doctor_id
                        )
                        db.session.add(doc_map)

                # 4. IP Admission Upsert (LOCATIONID + IPNUMBER)
                admitted_date, admitted_time = parse_datetime_safe(row.admitteddate)
                closing_date, closing_time = parse_datetime_safe(row.closingdate)

                admission = IPAdmission.query.filter_by(unit_id=unit.unit_id, ip_number=ipnumber).first()
                if not admission:
                    admission = IPAdmission(
                        ip_number=ipnumber,
                        unit_id=unit.unit_id,
                        patient_id=patient.patient_id,
                        patient_name_snapshot=patient.patient_name,
                        admission_date=admitted_date or datetime.utcnow().strftime('%Y-%m-%d'),
                        admission_time=admitted_time or '',
                        department=normalize_string(row.specialization) or 'General',
                        doctor_name=doctor_name,
                        bill_type=bill_type,
                        payer_id=payer_id,
                        hospital_payer_id=hospital_payer_id,
                        admission_status='DISCHARGED' if closing_date else 'ADMITTED',
                        discharge_status='DISCHARGED' if closing_date else 'NOT_DISCHARGED',
                        billing_eligible=True if closing_date else False
                    )
                    db.session.add(admission)
                    db.session.flush()
                else:
                    # Update HIS-controlled fields without overwriting app workflow fields
                    if admitted_date:
                        admission.admission_date = admitted_date
                    if doctor_name:
                        admission.doctor_name = doctor_name
                    if closing_date:
                        admission.admission_status = 'DISCHARGED'
                        admission.discharge_status = 'DISCHARGED'
                        admission.billing_eligible = True

                # 5. IP Discharge Processing
                if closing_date:
                    discharge = IPDischarge.query.filter_by(admission_id=admission.admission_id).first()
                    if not discharge:
                        discharge = IPDischarge(
                            admission_id=admission.admission_id,
                            ip_number=ipnumber,
                            discharge_date=closing_date,
                            discharge_time=closing_time or '',
                            discharge_type='REGULAR',
                            discharge_status='COMPLETED',
                            discharge_summary_status='COMPLETED',
                            final_bill_status='PENDING',
                            remarks=normalize_string(row.reasonandremarks)
                        )
                        db.session.add(discharge)
                    else:
                        discharge.discharge_date = closing_date
                        if closing_time:
                            discharge.discharge_time = closing_time

                # Mark Staging Row Success
                row.processing_status = 'PROCESSED'
                row.application_record_id = str(admission.admission_id)
                row.processed_at = datetime.utcnow()
                success_cnt += 1

        except Exception as e:
            row.processing_status = 'FAILED'
            row.validation_error = f"Sync execution failure: {str(e)}"
            failed_cnt += 1

    batch.successful_records = success_cnt
    batch.failed_records = failed_cnt
    batch.completed_at = datetime.utcnow()

    if failed_cnt == 0:
        batch.batch_status = 'COMPLETED'
    else:
        batch.batch_status = 'PARTIALLY_COMPLETED'

    db.session.commit()

    log_audit('EXECUTE_HIS_SYNC_BATCH', 'SyncBatch', batch.batch_id, None, {
        'total': batch.total_records,
        'successful': success_cnt,
        'failed': failed_cnt
    })
    return True
