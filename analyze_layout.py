import pdfplumber

pdf_path = "/Users/communication2/Desktop/RapidoPython/estimationdebase.pdf"

print(f"--- ANALYSE DETAILLEE DE {pdf_path} ---")

with pdfplumber.open(pdf_path) as pdf:
    for i, page in enumerate(pdf.pages):
        print(f"\n=== PAGE {i+1} ===")
        # Extract words with detailed info
        words = page.extract_words(keep_blank_chars=True, x_tolerance=3, y_tolerance=3, extra_attrs=["fontname", "size"])
        
        # Group by line (approximate Y)
        lines = {}
        for w in words:
            y = round(w['top'])
            if y not in lines: lines[y] = []
            lines[y].append(w)
            
        # Print first few lines to see structure
        for y in sorted(lines.keys())[:20]: # Show first 20 lines
            line_words = lines[y]
            text = " ".join([w['text'] for w in line_words])
            first_x = line_words[0]['x0']
            font = line_words[0]['fontname']
            size = line_words[0]['size']
            print(f"Y={y:<4} X={first_x:<6.1f} Size={size:<4.1f} Font={font[:20]:<20} | {text}")
