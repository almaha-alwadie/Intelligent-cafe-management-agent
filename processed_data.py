from pathlib import Path
import pandas as pd
import pdfplumber
import re


# PATHS

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
CSV_DIR = DATA_DIR / "csv"
PDF_DIR = DATA_DIR / "pdfs"


# LOAD CSV FILES

try:
    sales = pd.read_csv(CSV_DIR / "sales.csv")
    inventory = pd.read_csv(CSV_DIR / "inventory.csv")
    reviews = pd.read_csv(CSV_DIR / "reviews.csv")
    suppliers = pd.read_csv(CSV_DIR / "suppliers.csv")

    print("✅ CSV files loaded successfully.")
    print(f"Sales records: {len(sales)}")
    print(f"Inventory records: {len(inventory)}")
    print(f"Reviews records: {len(reviews)}")
    print(f"Suppliers records: {len(suppliers)}")

except Exception as e:
    print(f"⚠️ Could not load some CSV files: {e}")


# CLEAN TEXT

def clean_text(text):
    if not text:
        return ""

    text = re.sub(r'===== Page \d+ =====', '', text)
    text = re.sub(r'^\s*\d+\s*$', '', text, flags=re.MULTILINE)
    text = text.replace("&amp;", " and ")
    text = re.sub(r'\s+', " ", text)

    return text.strip()


# LOAD PDF PAGES

def load_pdf_pages(pdf_path):
    pages = []

    if not pdf_path.exists():
        print(f"❌ File not found: {pdf_path}")
        return pages

    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""

            if text.strip():
                pages.append({
                    "page_number": i,
                    "text": text
                })

    return pages


# =========================
# 🔥 SMART EMPLOYEE CHUNKING (UPDATED)
# =========================

def chunk_employee_guide(text, max_words=80):
    """
    Production-level semantic chunking for employee guide.
    """

    headings = [
        "Working Hours",
        "Dress Code",
        "Customer Service",
        "Barista Responsibilities",
        "Cashier Responsibilities",
        "Cleaning & Hygiene",
        "Inventory Management",
        "Safety Procedures",
        "General Rules",
        "Employee Role"
    ]

    # Force split before headings even if stuck
    pattern = r'(' + '|'.join(headings) + r')'
    text = re.sub(pattern, r'\n\n\1', text)

    # Split into sections
    sections = re.split(r'\n\s*\n', text)

    chunks = []

    for sec in sections:
        sec = sec.strip()

        if not sec:
            continue

        # normalize spaces
        sec = re.sub(r'\s+', ' ', sec)

        sentences = re.split(r'(?<=[.!?])\s+', sec)

        current_chunk = []
        current_len = 0

        for sent in sentences:
            sent = sent.strip()
            if not sent:
                continue

            sent_len = len(sent.split())

            if current_len + sent_len <= max_words:
                current_chunk.append(sent)
                current_len += sent_len
            else:
                if current_chunk:
                    chunks.append(" ".join(current_chunk))

                current_chunk = [sent]
                current_len = sent_len

        if current_chunk:
            chunks.append(" ".join(current_chunk))

    return chunks


# GENERAL CHUNKING

def chunk_general(text, max_words=50):

    text = re.sub(r'(##?\s*Category:)', r'\n\n\1', text)
    raw_parts = re.split(r'\n\s*\n', text)

    chunks = []

    for part in raw_parts:
        part = part.strip()

        if not part:
            continue

        if len(part.split()) <= max_words:
            chunks.append(part)
        else:
            sentences = re.split(r'(?<=[.!?])\s+', part)

            for sent in sentences:
                sent = sent.strip()

                if not sent:
                    continue

                if len(sent.split()) > max_words:
                    words = sent.split()

                    for i in range(0, len(words), max_words):
                        sub = " ".join(words[i:i + max_words])
                        if sub:
                            chunks.append(sub)
                else:
                    chunks.append(sent)

    return chunks


# FAQ CHUNKING

def chunk_faq(text):

    chunks = []
    qa_pairs = re.split(r'(?=Q:)', text)

    for pair in qa_pairs:
        pair = pair.strip()

        if not pair:
            continue

        pair = re.sub(r'\s+', ' ', pair)

        if "Q:" in pair and "A:" in pair:
            chunks.append(pair)

    return chunks


# PROCESS PDF

def process_pdf(pdf_path, max_words=50, show_raw_preview=False):

    pages = load_pdf_pages(pdf_path)
    all_chunks = []
    global_idx = 0

    file_name = pdf_path.name.lower()

    if "faq" in file_name:
        doc_type = "faq"
        chunk_func = chunk_faq

    elif "menu" in file_name:
        doc_type = "menu"
        chunk_func = chunk_general

    elif "recipe" in file_name:
        doc_type = "recipe"
        chunk_func = chunk_general

    elif "employee" in file_name or "guide" in file_name:
        doc_type = "employee"
        chunk_func = chunk_employee_guide

    else:
        doc_type = "other"
        chunk_func = chunk_general

    current_category = "General"

    useless_titles = {
        "employee guide",
        "cafe menu",
        "cafe recipes",
        "smart cafe faq knowledge base"
    }

    for page in pages:

        if show_raw_preview and page["page_number"] == 1 and "employee" in file_name:
            print(f"\n--- RAW TEXT FROM {pdf_path.name} ---")
            print(repr(page["text"][:500]))

        text = clean_text(page["text"])

        lines = text.split('\n')

        page_blocks = []
        temp_block = []

        for line in lines:

            if re.match(r'^##?\s*Category:', line, re.IGNORECASE):

                if temp_block:
                    page_blocks.append("\n".join(temp_block))
                    temp_block = []

                current_category = re.sub(
                    r'^##?\s*Category:\s*',
                    '',
                    line,
                    flags=re.IGNORECASE
                ).strip()

            else:
                temp_block.append(line)

        if temp_block:
            page_blocks.append("\n".join(temp_block))

        for block in page_blocks:

            raw_chunks = chunk_func(block)

            for chunk in raw_chunks:

                if not chunk or not chunk.strip():
                    continue

                chunk = chunk.strip()

                # FILTER 1: small chunks
                if len(chunk.split()) < 5:
                    continue

                # FILTER 2: useless titles
                if chunk.lower() in useless_titles:
                    continue

                global_idx += 1

                enhanced = chunk

                if doc_type == "menu" and current_category != "General":
                    enhanced = f"[{current_category}] {chunk}"

                all_chunks.append({
                    "text": enhanced,
                    "metadata": {
                        "source_file": pdf_path.name,
                        "page_number": page["page_number"],
                        "chunk_index": len(all_chunks) + 1,
                        "global_chunk_index": global_idx,
                        "doc_type": doc_type,
                        "category": current_category
                    }
                })

    return all_chunks


# PROCESS ALL PDFS

def process_all_pdfs(max_words=50, show_raw_once=True):

    all_pdfs = list(PDF_DIR.glob("*.pdf"))

    if not all_pdfs:
        print("️ No PDF files found in data/pdfs/")
        return {}

    results = {}
    show_raw = show_raw_once

    for pdf_path in all_pdfs:

        chunks = process_pdf(
            pdf_path,
            max_words=max_words,
            show_raw_preview=show_raw
        )

        show_raw = False
        results[pdf_path.name] = chunks

    return results


# MAIN

if __name__ == "__main__":

    print("\n🔄 Processing ALL PDFs...\n")

    results = process_all_pdfs(
        max_words=50,
        show_raw_once=True
    )

    print("\n" + "=" * 50)
    print("📊 FINAL CHUNKS PER FILE")
    print("=" * 50)

    total = 0

    for name, chunks in results.items():
        count = len(chunks)
        total += count
        print(f"{name:35} : {count:4} chunks")

    print("-" * 50)
    print(f"{'TOTAL':35} : {total:4} chunks")
    print("=" * 50)

    if results:
        first_file = list(results.keys())[0]

        if results[first_file]:

            print(f"\n🔎 Sample chunk from '{first_file}':\n")

            sample = results[first_file][0]["text"]

            print(sample[:500] + "..." if len(sample) > 500 else sample)

            print("\n📌 Metadata:")
            print(results[first_file][0]["metadata"])