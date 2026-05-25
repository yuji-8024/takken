#!/usr/bin/env python3
"""RETIO公式サイトから宅建過去問PDFをダウンロードする。"""
import urllib.parse
import urllib.request
from pathlib import Path

BASE = "https://www.retio.or.jp"

# 平成28年度〜令和7年度（10試験年度）+ 令和2・3の追加試験
EXAMS = [
    ("H28", f"{BASE}/wp-content/uploads/2024/10/H28-q_a.pdf"),
    ("H29", f"{BASE}/wp-content/uploads/2024/10/H29-q_a.pdf"),
    ("H30", f"{BASE}/wp-content/uploads/2024/10/H30-q_a.pdf"),
    ("R1", f"{BASE}/wp-content/uploads/2024/10/R1-q_a.pdf"),
    ("R2_10", f"{BASE}/wp-content/uploads/2024/10/R2-question.pdf"),
    ("R2_12", f"{BASE}/wp-content/uploads/2024/10/R2-question_002.pdf"),
    ("R3_10", f"{BASE}/wp-content/uploads/2024/12/R3-question.pdf"),
    ("R3_12", f"{BASE}/wp-content/uploads/2024/12/R3-question_002.pdf"),
    ("R4", f"{BASE}/wp-content/uploads/2024/10/R4-q_a.pdf"),
    ("R5", f"{BASE}/wp-content/uploads/2025/03/R5_qestion_answer%E3%80%80.pdf"),
    ("R6", f"{BASE}/wp-content/uploads/2025/03/R6_question_answer.pdf"),
    ("R7", f"{BASE}/wp-content/uploads/2025/12/R7_question_answer.pdf"),
]


def main():
    out_dir = Path(__file__).resolve().parents[1] / "data" / "pdfs"
    out_dir.mkdir(parents=True, exist_ok=True)

    for label, url in EXAMS:
        dest = out_dir / f"{label}.pdf"
        if dest.exists() and dest.stat().st_size > 10000:
            print(f"skip {label} (exists)")
            continue
        print(f"download {label} ...")
        req = urllib.request.Request(url, headers={"User-Agent": "takken-analysis/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = resp.read()
        except Exception as e:
            # R5 URL has fullwidth space — try encoded variants
            alt = url.replace("%E3%80%80", "　")
            print(f"  retry: {e}")
            req = urllib.request.Request(alt, headers={"User-Agent": "takken-analysis/1.0"})
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = resp.read()
        dest.write_bytes(data)
        print(f"  -> {dest} ({len(data)} bytes)")


if __name__ == "__main__":
    main()
