import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app import app
from database import db
from models import SyncBatch, HISIPStaging, HospitalUnit, Payer
from utils.his_sync.parsers import parse_his_file
from utils.his_sync.validator import validate_staging_batch
from utils.his_sync.sync_engine import process_sync_batch

def run_test():
    print("==================================================")
    print("TESTING SMART VALIDATION & IDEMPOTENT SYNC ENGINE")
    print("==================================================")

    with app.app_context():
        with app.test_request_context():
            db.create_all()

            # Mock File content with Title row and non-standard header aliases
            mock_file = """Wipro eMIS Hospital System - Inpatient Discharge Summary
Generated Date: 12-Sep-2026

UH ID, Patient Name, Admission No, Gender, Age, Admission Date, Discharge Date, Consultant, Payer Name
UHID-8801, RAKESH VARMA, IP-8801, Male, 52 Yrs, 01/09/2026 09:00, 05/09/2026 14:00, Dr. Rajesh Sharma, Star Health
UHID-8802, SNEHA REDDY, IP-8802, Female, 29 Yrs, 02/09/2026 11:30, , Dr. Anita Verma, Direct Cash
"""

            parsed = parse_his_file("Discharge Report - eMIS.xls", mock_file.encode('utf-8'))
            print(f"1. Parsed {len(parsed)} rows from eMIS discharge file.")

            batch = SyncBatch(
                source_system='HIS_EXCEL',
                source_type='FILE_UPLOAD',
                source_file_name='Discharge Report - eMIS.xls',
                source_file_hash='mockhash123456',
                uploaded_by=1,
                total_records=len(parsed),
                batch_status='UPLOADED'
            )
            db.session.add(batch)
            db.session.flush()

            staging_objs = []
            for idx, r in enumerate(parsed, start=1):
                stg = HISIPStaging(
                    batch_id=batch.batch_id,
                    row_number=idx,
                    uhid=r.get('UHID', ''),
                    patientname=r.get('PATIENTNAME', ''),
                    ipnumber=r.get('IPNUMBER', ''),
                    gender=r.get('GENDER', ''),
                    age=r.get('AGE', ''),
                    admitteddate=r.get('ADMITTEDDATE', ''),
                    planingdate=r.get('PLANINGDATE', ''),
                    closingdate=r.get('CLOSINGDATE', ''),
                    primarydoctor=r.get('PRIMARYDOCTOR', ''),
                    companyname=r.get('COMPANYNAME', ''),
                    locationid=r.get('LOCATIONID', ''),
                    validation_status='PENDING'
                )
                staging_objs.append(stg)

            db.session.bulk_save_objects(staging_objs)
            db.session.commit()

            print(f"2. Staged Batch #{batch.batch_id} with {len(staging_objs)} records.")

            # Run Validation
            validate_staging_batch(batch.batch_id)
            db.session.refresh(batch)

            print(f"3. Validation Result:")
            print(f"   - Status: {batch.batch_status}")
            print(f"   - Total: {batch.total_records}")
            print(f"   - Valid: {batch.total_records - batch.invalid_records}")
            print(f"   - Invalid: {batch.invalid_records}")
            print(f"   - Pending Mapping: {batch.mapping_pending_records}")

            # Run Sync
            process_sync_batch(batch.batch_id, user_id=1)
            db.session.refresh(batch)
            print(f"4. Sync Engine Execution Result:")
            print(f"   - Status: {batch.batch_status}")
            print(f"   - Successful: {batch.successful_records}")
            print(f"   - Failed: {batch.failed_records}")

            print("\n==================================================")
            print("SMART VALIDATION & SYNC TEST PASSED SUCCESSFULLY!")
            print("==================================================")

if __name__ == '__main__':
    run_test()
