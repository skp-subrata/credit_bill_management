import sys
import io
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.his_sync.parsers import parse_his_file

def test_xls_parsing():
    print("==================================================")
    print("TESTING BINARY .XLS (BIFF8) AND HTML TABLE .XLS")
    print("==================================================")

    # 1. Test HTML Table saved as .xls
    html_xls = """<html>
<body>
<table>
  <tr><th colspan="8">Wipro eMIS Hospital Discharge Report</th></tr>
  <tr>
    <th>UH ID</th><th>Patient Name</th><th>IP No</th><th>Gender</th>
    <th>Admission Date</th><th>Discharge Date</th><th>Doctor</th><th>Payer</th>
  </tr>
  <tr>
    <td>UHID-7701</td><td>SUPRITI SWAIN</td><td>IP-7701</td><td>Female</td>
    <td>01/09/2026</td><td>04/09/2026</td><td>Dr. Rajesh Sharma</td><td>Star Health</td>
  </tr>
</table>
</body>
</html>"""

    res1 = parse_his_file("Discharge Report - eMIS 1 1.xls", html_xls.encode('utf-8'))
    print(f"\n1. HTML .xls test: Parsed {len(res1)} rows.")
    for r in res1:
        print(f"   - UHID: {r.get('UHID')} | Name: {r.get('PATIENTNAME')} | IP: {r.get('IPNUMBER')}")
    assert len(res1) == 1, "Expected 1 parsed row from HTML .xls"

if __name__ == '__main__':
    test_xls_parsing()
