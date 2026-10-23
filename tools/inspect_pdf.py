"""Inspect a bank statement PDF: dump text layer + tables page by page."""
import sys
import pdfplumber

path = sys.argv[1]
with pdfplumber.open(path) as pdf:
    print(f"PAGES: {len(pdf.pages)}")
    for i, page in enumerate(pdf.pages):
        print(f"\n{'='*70}\nPAGE {i+1}  (size {page.width}x{page.height})\n{'='*70}")
        text = page.extract_text() or "(no text layer)"
        print("--- TEXT ---")
        print(text[:3000])
        tables = page.extract_tables()
        print(f"--- TABLES: {len(tables)} ---")
        for ti, t in enumerate(tables):
            print(f"[table {ti}] {len(t)} rows x {len(t[0]) if t else 0} cols")
            for row in t[:15]:
                print("  ", row)
