from app import extract_data_from_pdf
import os

pdf_path = "/Users/communication2/Desktop/RapidoPython/estimationdebase.pdf"

if not os.path.exists(pdf_path):
    print("PDF not found!")
    exit()

print(f"Extracting from {pdf_path}...")
try:
    data = extract_data_from_pdf(pdf_path)
except Exception as e:
    print(f"Error extracting: {e}")
    exit()

content = data.get('content', [])
print(f"Found {len(content)} nodes.")

print("-" * 60)
for i, item in enumerate(content):
    if item['type'] == 'section':
        print(f"SECTION: {item['text']}")
    elif item['type'] == 'item':
        d = item['data']
        # Truncate description for display
        desc = d['description'].replace('\n', ' ')[:60]
        print(f"ITEM: {desc:<60} | Qté: {str(d['quantite']):<6} | Total: {d['total_ligne']}")
print("-" * 60)
