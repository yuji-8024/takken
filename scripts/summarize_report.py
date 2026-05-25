#!/usr/bin/env python3
"""分析結果を人間向けMarkdownにまとめる。"""
import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
report = json.loads((ROOT / "data" / "analysis_report.json").read_text(encoding="utf-8"))
all_data = json.loads((ROOT / "data" / "extracted" / "all.json").read_text(encoding="utf-8"))

EXAM_ORDER = [
    "H28", "H29", "H30", "R1", "R2_10", "R2_12", "R3_10", "R3_12",
    "R4", "R5", "R6", "R7",
]
EXAM_LABEL = {
    "H28": "平成28", "H29": "平成29", "H30": "平成30", "R1": "令和元",
    "R2_10": "令和2(10月)", "R2_12": "令和2(12月)", "R3_10": "令和3(10月)",
    "R3_12": "令和3(12月)", "R4": "令和4", "R5": "令和5", "R6": "令和6", "R7": "令和7",
}


def band(q: int) -> str:
    if 1 <= q <= 14:
        return "権利関係"
    if 15 <= q <= 22:
        return "法令上の制限"
    if 23 <= q <= 32:
        return "宅建業法"
    if 33 <= q <= 38:
        return "税・その他"
    if q >= 46:
        return "登録講習免除"
    return "その他"


lines = []
lines.append("# 宅建過去問 10年分 類似・傾向分析レポート\n")
lines.append("データ出典: [RETIO公式過去問](https://www.retio.or.jp/exam/past_ques_ans/other/)（平成28〜令和7、計12回分）\n")
lines.append("## 概要\n")
s = report["summary"]
lines.append(f"- 分析対象: **{s['exam_count']}回分** / 抽出問題数 **{s['total_questions']}問**（OCR・テキスト抽出）\n")
lines.append(f"- 高類似ペア（TF-IDF・文字列類似の複合スコア）: **{s['high_similarity_pairs']}組**\n")
lines.append("\n> 注: 平成28〜令和4のPDFは画像主体のためOCR抽出。誤認識により類似度が過小・過大になる場合があります。\n")

lines.append("\n## 科目別の頻出キーワード（全年度）\n")
for kw, cnt in report["top_keywords"][:15]:
    lines.append(f"- **{kw}**: {cnt}問に出現\n")

lines.append("\n## 類似・反復が強い問題ペア（上位20）\n")
lines.append("| スコア | 年度A | 問A | 年度B | 問B | 科目帯 | 共通キーワード |\n")
lines.append("|---:|---|---:|---|---:|---|---|\n")
for p in report["top_similar_pairs"][:20]:
    qa, qb = p["qnums"]
    ba, bb = band(qa), band(qb)
    subj = ba if ba == bb else f"{ba}/{bb}"
    kw = "、".join(p["shared_keywords"][:4]) or "—"
    lines.append(
        f"| {p['score']:.2f} | {EXAM_LABEL.get(p['exams'][0], p['exams'][0])} | {qa} | "
        f"{EXAM_LABEL.get(p['exams'][1], p['exams'][1])} | {qb} | {subj} | {kw} |\n"
    )

# 同じ問番号帯での類似（例: 業法23-32同士）
same_band_pairs = [
    p for p in report["top_similar_pairs"]
    if band(p["qnums"][0]) == band(p["qnums"][1]) and band(p["qnums"][0]) != "その他"
]
lines.append("\n## 同一科目帯内の類似ペア（上位10）\n")
for p in same_band_pairs[:10]:
    lines.append(
        f"- **{EXAM_LABEL.get(p['exams'][0])} 問{p['qnums'][0]}** ↔ "
        f"**{EXAM_LABEL.get(p['exams'][1])} 問{p['qnums'][1]}** "
        f"(score={p['score']:.2f}, seq={p['seq']:.2f})\n"
    )
    lines.append(f"  - A: {p['text_a_preview'][:120]}…\n")
    lines.append(f"  - B: {p['text_b_preview'][:120]}…\n")

# キーワードの年度推移
lines.append("\n## キーワードの年度別出現（上位テーマ）\n")
track_kws = ["重要事項説明", "37条書面", "35条書面", "営業保証金", "媒介契約", "用途地域", "借地借家法", "抵当権"]
kw_year = {kw: Counter() for kw in track_kws}
import re
for exam, blob in all_data.items():
    for qn, text in blob["questions"].items():
        for kw in track_kws:
            if kw in text or (kw == "37条書面" and re.search(r"37条", text)):
                kw_year[kw][exam] += 1

lines.append("| キーワード | " + " | ".join(EXAM_LABEL[e] for e in EXAM_ORDER) + " |\n")
lines.append("|---|" + "|".join(["---:"] * len(EXAM_ORDER)) + "|\n")
for kw in track_kws:
    row = [str(kw_year[kw].get(e, 0)) for e in EXAM_ORDER]
    lines.append(f"| {kw} | " + " | ".join(row) + " |\n")

lines.append("\n## 傾向のまとめ\n")
lines.append("""
1. **宅建業法・契約実務**（重要事項説明、37条書面、媒介契約、報酬、営業保証金）が最も反復しやすい領域です。年度をまたいだ「文言差し替え型」の類似が多く見られます。
2. **権利関係**（登記、抵当権、借地借家法、売買・賃貸借）も定番テーマが繰り返されますが、具体事例（人名・金額・順序）が変わるため、暗記より「パターン理解」向きです。
3. **法令制限**（用途地域、容積率、建ぺい率、開発許可、農地法）はキーワード出現は安定していますが、数値・区域の設定が毎回異なるため、類似スコアは業法より低めになりがちです。
4. **令和2・3の追試**（10月/12月）を含めても、出題枠（問1-14権利、15-22法令、23-32業法、33-38税）の構造は一貫しています。
5. 法改正の影響で、**旧年度の正解が現在と一致しない**問題があります（RETIO注記どおり）。類似問題を学習する際は条文の施行日を必ず確認してください。
""")

out = ROOT / "data" / "ANALYSIS_REPORT.md"
out.write_text("".join(lines), encoding="utf-8")
print(f"wrote {out}")
