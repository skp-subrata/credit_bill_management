import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app import app
from database import db
from models import SyncBatch, HISIPStaging, HospitalUnit, HISPayerMapping, Payer

def inspect_batch():
    with app.app_context():
        print("==================================================")
        print("INSPECTING BATCH & STAGING VALIDATION ERRORS")
        print("==================================================")

        batches = SyncBatch.query.order_by(SyncBatch.batch_id.desc()).limit(5).all()
        print(f"\nTotal Recent Batches Found: {len(batches)}")
        for b in batches:
            print(f"Batch #{b.batch_id} | File: {b.source_file_name} | Status: {b.batch_status} | Total: {b.total_records} | Valid: {b.total_records - b.invalid_records} | Invalid: {b.invalid_records} | Pending Mapping: {b.mapping_pending_records} | Failed: {b.failed_records}")

        # Target batch 11 or latest
        target_batch_id = 11 if SyncBatch.query.get(11) else (batches[0].batch_id if batches else None)
        if not target_batch_id:
            print("No batches found in database!")
            return

        print(f"\n--- Detailed Staging Analysis for Batch #{target_batch_id} ---")
        stg_rows = HISIPStaging.query.filter_by(batch_id=target_batch_id).all()
        print(f"Total Staging Rows in Batch #{target_batch_id}: {len(stg_rows)}")

        for idx, row in enumerate(stg_rows[:10], start=1):
            print(f"\nRow #{row.row_number} (Staging ID: {row.staging_id}):")
            print(f"  UHID: '{row.uhid}'")
            print(f"  IP Number: '{row.ipnumber}'")
            print(f"  Patient Name: '{row.patientname}'")
            print(f"  Location ID: '{row.locationid}'")
            print(f"  Company Name: '{row.companyname}'")
            print(f"  Admitted Date: '{row.admitteddate}'")
            print(f"  Closing Date: '{row.closingdate}'")
            print(f"  Validation Status: {row.validation_status}")
            print(f"  Validation Error: {row.validation_error}")
            print(f"  Processing Status: {row.processing_status}")

        print("\n--- Hospital Units in DB ---")
        units = HospitalUnit.query.all()
        for u in units:
            print(f"  Unit ID: {u.unit_id} | Code: '{u.unit_code}' | Name: '{u.hospital_name}'")

        print("\n--- Payer Mappings in DB ---")
        mappings = HISPayerMapping.query.all()
        for m in mappings:
            print(f"  Mapping ID: {m.mapping_id} | Raw HIS Name: '{m.source_company_name}' | Normalized: '{m.normalized_company_name}' | Payer ID: {m.payer_id} | Bill Type: {m.bill_type} | Active: {m.active}")

if __name__ == '__main__':
    inspect_batch()
