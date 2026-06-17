import pdfplumber


def parse_pdf(file_path: str) -> str:
    text = []
    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text.append(page_text)
            for table in page.extract_tables():
                if table:
                    for row in table:
                        if any(row):
                            text.append(' | '.join(str(cell) for cell in row if cell))
    return '\n'.join(text)
