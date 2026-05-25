#!/usr/bin/env python3
"""PDFから各問の本文を抽出する（テキスト層が無いPDFはOCR）。"""
import json
import re
from pathlib import Path

import fitz  # pymupdf

OCR_DPI = 150
MIN_PAGE_CHARS = 80  # これ未満なら画像ページとみなしてOCR


def normalize_text(s: str) -> str:
    s = s.replace("\u3000", " ")
    s = re.sub(r"\s+", " ", s)
    s = s.strip()
    return s


def page_text(page: fitz.Page) -> str:
    t = page.get_text("text")
    if len(t.strip()) >= MIN_PAGE_CHARS:
        return t
    try:
        tp = page.get_textpage_ocr(language="jpn", dpi=OCR_DPI)
        return page.get_text(textpage=tp)
    except Exception:
        return t


def split_questions(full_text: str) -> dict[int, str]:
    """問1〜問50（または45）に分割。"""
    pattern = re.compile(
        r"【?\s*問\s*([0-9０-９]{1,2})\s*】?",
        re.MULTILINE,
    )

    def zen_to_int(t: str) -> int:
        trans = str.maketrans("０１２３４５６７８９", "0123456789")
        return int(t.translate(trans))

    matches = list(pattern.finditer(full_text))
    if not matches:
        return {}

    questions = {}
    for i, m in enumerate(matches):
        qnum = zen_to_int(m.group(1))
        if qnum < 1 or qnum > 50:
            continue
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(full_text)
        body = normalize_text(full_text[start:end])
        if len(body) > 40:
            questions[qnum] = body
    return questions


def extract_pdf(path: Path, use_cache: bool = True) -> dict:
    cache_dir = path.parent.parent / "ocr_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file = cache_dir / f"{path.stem}.txt"

    if use_cache and cache_file.exists():
        full = cache_file.read_text(encoding="utf-8")
    else:
        doc = fitz.open(path)
        pages_text = []
        for i in range(doc.page_count):
            pages_text.append(page_text(doc[i]))
            if (i + 1) % 5 == 0:
                print(f"    page {i+1}/{doc.page_count}")
        doc.close()
        full = "\n".join(pages_text)
        cache_file.write_text(full, encoding="utf-8")

    cut = re.search(r"正解番号", full)
    if cut:
        full = full[: cut.start()]

    questions = split_questions(full)
    return {
        "source": path.name,
        "question_count": len(questions),
        "ocr_cached": cache_file.exists(),
        "questions": {str(k): v for k, v in sorted(questions.items())},
    }


def main():
    pdf_dir = Path(__file__).resolve().parents[1] / "data" / "pdfs"
    out_dir = Path(__file__).resolve().parents[1] / "data" / "extracted"
    out_dir.mkdir(parents=True, exist_ok=True)

    all_data = {}
    for pdf in sorted(pdf_dir.glob("*.pdf")):
        print(f"extract {pdf.name} ...")
        data = extract_pdf(pdf)
        label = pdf.stem
        all_data[label] = data
        (out_dir / f"{label}.json").write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"  -> {data['question_count']} questions")

    (out_dir / "all.json").write_text(
        json.dumps(all_data, ensure_ascii=False, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
