#!/usr/bin/env python3
"""PDF末尾から正解番号表を抽出する。"""
import json
import re
from pathlib import Path

import fitz

ROOT = Path(__file__).resolve().parents[1]
PDF_DIR = ROOT / "data" / "pdfs"
CACHE_DIR = ROOT / "data" / "ocr_cache"
OUT = ROOT / "data" / "answers.json"

EXAMS = [
    "H28", "H29", "H30", "R1", "R2_10", "R2_12", "R3_10", "R3_12",
    "R4", "R5", "R6", "R7",
]


def zen_to_int(s: str) -> int:
    trans = str.maketrans("０１２３４５６７８９", "0123456789")
    s = str(s).translate(trans).strip()
    if s.isdigit():
        return int(s)
    if s and s[0] in "1234":
        return int(s[0])
    return 0


def page_text(exam: str, page: fitz.Page, page_idx: int) -> str:
    t = page.get_text("text")
    if len(t.strip()) >= 80:
        return t
    cache = CACHE_DIR / f"{exam}.txt"
    if cache.exists():
        # キャッシュは全文; ページ境界なし → フォールバックOCRこのページのみ
        pass
    try:
        tp = page.get_textpage_ocr(language="jpn", dpi=150)
        return page.get_text(textpage=tp)
    except Exception:
        return t


def extract_grid_answers(section: str) -> dict[int, str]:
    """正解番号表グリッド形式（問1-10 + 10個の数字 ×5行）。"""
    m_start = re.search(r"問\s*[　\s]*[１1１]", section)
    if not m_start:
        m_start = re.search(r"問\s*1\s", section)
    if not m_start:
        return {}

    block = section[m_start.start() :]
    # 正解番号表の終わり
    end = re.search(r"合格判定|合否判定|試験問題の正解", block)
    if end:
        block = block[: end.start()]

    qnums = []
    for m in re.finditer(r"問\s*([0-9０-９]{1,2})", block):
        qn = zen_to_int(m.group(1))
        if 1 <= qn <= 50:
            qnums.append(qn)

    digits = []
    for line in block.split("\n"):
        line = line.strip().replace("　", "").replace(" ", "")
        if re.fullmatch(r"[1-4１-４]", line):
            digits.append(str(zen_to_int(line)))

    if len(digits) < 40:
        # 問ラベル直後の単独数字列
        after_labels = re.split(r"問\s*[0-9０-９]{1,2}\s*", block)[1:]
        for part in after_labels:
            for line in part.split("\n"):
                line = line.strip().replace("　", "")
                if re.fullmatch(r"[1-4１-４]", line):
                    digits.append(str(zen_to_int(line)))
            if len(digits) >= 50:
                break

    if len(qnums) >= 45 and len(digits) >= 45:
        n = min(len(qnums), len(digits), 50)
        return {qnums[i]: digits[i] for i in range(n)}

    if len(digits) >= 45 and not qnums:
        return {i + 1: digits[i] for i in range(min(50, len(digits)))}

    return {}


def extract_answers_from_text(full_text: str) -> dict[int, str]:
    answers = extract_grid_answers(full_text)

    if len(answers) < 40:
        idx = full_text.rfind("正解番号")
        section = full_text[idx:] if idx >= 0 else full_text[-5000:]
        for m in re.finditer(
            r"問\s*([0-9０-９]{1,2})\s*[\s\n]*([1-4１-４]|なし|無し)",
            section,
        ):
            qn = zen_to_int(m.group(1))
            if 1 <= qn <= 50:
                ans = m.group(2)
                answers[qn] = "none" if ans in ("なし", "無し") else str(zen_to_int(ans))

    return dict(sorted(answers.items()))


def main():
    all_answers = {}
    for exam in EXAMS:
        pdf = PDF_DIR / f"{exam}.pdf"
        if not pdf.exists():
            continue
        cache = CACHE_DIR / f"{exam}.txt"
        doc = fitz.open(pdf)
        start = max(0, doc.page_count - 8)
        full = "\n".join(page_text(exam, doc[i], i) for i in range(start, doc.page_count))
        doc.close()

        ans = extract_answers_from_text(full)
        if len(ans) < 40 and cache.exists():
            cache_text = cache.read_text(encoding="utf-8")
            for marker in ("年度問題", "正解番号", "問　１", "問 １"):
                pos = cache_text.rfind(marker)
                if pos >= 0:
                    ans2 = extract_answers_from_text(cache_text[pos : pos + 6000])
                    if len(ans2) > len(ans):
                        ans = ans2
            if len(ans) < 40:
                ans2 = extract_answers_from_text(cache_text[-12000:])
                if len(ans2) > len(ans):
                    ans = ans2
        all_answers[exam] = {str(k): v for k, v in ans.items()}
        print(f"{exam}: {len(ans)} answers")

    OUT.write_text(json.dumps(all_answers, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
