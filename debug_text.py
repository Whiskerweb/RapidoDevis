import pdfplumber

pdf_path = "/Users/communication2/Desktop/RapidoPython/estimationdebase.pdf"

with pdfplumber.open(pdf_path) as pdf:
    for page in pdf.pages:
        words = page.extract_words()
        # Find words around where the number usually is
        for w in words:
            if "D202512" in w['text'] or "N°" in w['text']:
                print(f"Word: {repr(w['text'])}")
                
        # Also check full line text
        text = page.extract_text()
        for line in text.split('\n'):
            if "D202512" in line:
                print(f"Line raw: {repr(line)}")
