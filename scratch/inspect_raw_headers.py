import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app import app
from models import HISIPStaging

def inspect_raw_payload():
    with app.app_context():
        row = HISIPStaging.query.filter_by(batch_id=11).first()
        if not row:
            row = HISIPStaging.query.order_by(HISIPStaging.staging_id.desc()).first()
        
        if row and row.raw_payload:
            payload = json.loads(row.raw_payload)
            print("==================================================")
            print(f"RAW PAYLOAD KEYS FOR STAGING ROW #{row.staging_id}:")
            print("==================================================")
            for k, v in payload.items():
                print(f"  '{k}': '{v}'")
        else:
            print("No raw_payload found!")

if __name__ == '__main__':
    inspect_raw_payload()

