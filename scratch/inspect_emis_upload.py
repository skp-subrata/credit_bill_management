import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app import app
from models import SyncBatch, HISIPStaging

def inspect_emis():
    with app.app_context():
        batches = SyncBatch.query.filter(SyncBatch.source_file_name.ilike("%eMIS%")).order_by(SyncBatch.batch_id.desc()).all()
        print("==================================================")
        print("INSPECTING eMIS UPLOAD BATCHES IN DATABASE")
        print("==================================================")
        print(f"Total eMIS batches found: {len(batches)}")
        for b in batches:
            print(f"Batch #{b.batch_id} | File: '{b.source_file_name}' | Status: {b.batch_status} | Total Rows: {b.total_records} | Uploaded: {b.uploaded_at}")

        latest_batch = SyncBatch.query.order_by(SyncBatch.batch_id.desc()).first()
        if latest_batch:
            print(f"\nLatest Batch #{latest_batch.batch_id} | File: '{latest_batch.source_file_name}' | Total Records: {latest_batch.total_records} | Status: {latest_batch.batch_status}")
            stg_count = HISIPStaging.query.filter_by(batch_id=latest_batch.batch_id).count()
            print(f"Staging Count: {stg_count}")

if __name__ == '__main__':
    inspect_emis()
