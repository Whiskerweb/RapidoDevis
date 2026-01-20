import pdfplumber

pdf_path = "/Users/communication2/Desktop/RapidoPython/estimationdebase.pdf"

print(f"--- ANALYSE DE {pdf_path} ---")

try:
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages):
            print(f"\n--- PAGE {i+1} ---")
            text = page.extract_text()
            print(text)
            print("\n--- TABLES ---")
            tables = page.extract_tables()
            for table in tables:
                print(table)
except Exception as e:
    print(f"Erreur : {e}")
