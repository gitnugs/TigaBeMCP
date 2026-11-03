import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from storage import buat_document_url

for key in ["SK-2026-014.pdf", "SK-2026-021.pdf", "JADWAL-2026-27.pdf",
            "ANN-SCH-0077.pdf", "SOP-PA-01.pdf"]:
    print(key)
    print(buat_document_url(key))
    print()
