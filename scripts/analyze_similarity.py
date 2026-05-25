#!/usr/bin/env python3
"""過去問間の類似・反復出題を分析する。"""
import json
import re
from collections import Counter, defaultdict
from difflib import SequenceMatcher
from pathlib import Path

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


def normalize_for_compare(s: str) -> str:
    s = s.lower()
    s = re.sub(r"[０-９]", lambda m: str(ord(m.group()) - ord("０")), s)
    s = re.sub(r"\d+", "#", s)
    s = re.sub(r"[Ａ-Ｚａ-ｚA-Za-z]+", "A", s)
    s = re.sub(r"\s+", "", s)
    s = re.sub(r"[、。．，,.・「」『』（）()【】\[\]：:；;？?！!\-—―]", "", s)
    return s


def seq_ratio(a: str, b: str) -> float:
    na, nb = normalize_for_compare(a), normalize_for_compare(b)
    if len(na) < 40 or len(nb) < 40:
        return 0.0
    return SequenceMatcher(None, na, nb).ratio()


def keyword_set(text: str) -> set:
    """法律・制度キーワードの粗い抽出。"""
    patterns = [
        r"宅地建物取引業法",
        r"宅建業法",
        r"都市計画法",
        r"建築基準法",
        r"借地借家法",
        r"区分所有法",
        r"登記",
        r"抵当権",
        r"地上権",
        r"賃借権",
        r"37条書面",
        r"35条書面",
        r"重要事項説明",
        r"業務上の規制",
        r"免許",
        r"営業保証金",
        r"報酬",
        r"媒介契約",
        r"売買契約",
        r"消費税",
        r"印紙税",
        r"固定資産税",
        r"相続税",
        r"所得税",
        r"農地法",
        r"土地区画整理",
        r"開発許可",
        r"用途地域",
        r"建ぺい率",
        r"容積率",
        r"防火地域",
        r"景観法",
        r"土砂災害",
    ]
    found = set()
    for p in patterns:
        if re.search(p, text):
            found.add(p)
    return found


def subject_guess(text: str) -> str:
    """科目の推定（問番号なしの場合用）。"""
    if re.search(r"宅建業|業務上|35条|37条|重要事項|営業保証|免許", text):
        return "宅建業法"
    if re.search(r"都市計画|建築基準|用途地域|建ぺい|容積|開発許可|農地", text):
        return "法令制限"
    if re.search(r"登記|抵当|地上権|賃借|相続|共有|時効|物権", text):
        return "権利関係"
    if re.search(r"税|印紙|固定資産|所得税|消費税", text):
        return "税その他"
    return "不明"


def main():
    root = Path(__file__).resolve().parents[1]
    data_path = root / "data" / "extracted" / "all.json"
    if not data_path.exists():
        raise SystemExit("Run extract_questions.py first")

    all_data = json.loads(data_path.read_text(encoding="utf-8"))

    # フラット化: (exam, qnum) -> text
    items = []
    for exam, blob in all_data.items():
        for qnum, text in blob["questions"].items():
            items.append(
                {
                    "id": f"{exam}_Q{qnum}",
                    "exam": exam,
                    "qnum": int(qnum),
                    "text": text,
                    "subject": subject_guess(text),
                    "keywords": keyword_set(text),
                }
            )

    texts = [it["text"] for it in items]
    vectorizer = TfidfVectorizer(
        analyzer="char_wb",
        ngram_range=(3, 5),
        max_features=80000,
        min_df=1,
    )
    X = vectorizer.fit_transform(texts)
    sim = cosine_similarity(X)

    # 高類似ペア
    pairs = []
    n = len(items)
    for i in range(n):
        for j in range(i + 1, n):
            if items[i]["exam"] == items[j]["exam"]:
                continue
            tfidf_s = float(sim[i, j])
            seq_s = seq_ratio(items[i]["text"], items[j]["text"])
            if tfidf_s >= 0.55 or seq_s >= 0.72:
                pairs.append(
                    {
                        "a": items[i],
                        "b": items[j],
                        "tfidf": round(tfidf_s, 3),
                        "seq": round(seq_s, 3),
                        "score": round(0.5 * tfidf_s + 0.5 * seq_s, 3),
                    }
                )

    pairs.sort(key=lambda p: p["score"], reverse=True)

    # キーワード反復（年度横断）
    kw_counter = Counter()
    kw_by_exam = defaultdict(lambda: defaultdict(int))
    for it in items:
        for kw in it["keywords"]:
            kw_counter[kw] += 1
            kw_by_exam[kw][it["exam"]] += 1

    # 科目別問数
    subj_by_exam = defaultdict(Counter)
    for it in items:
        subj_by_exam[it["exam"]][it["subject"]] += 1

    report = {
        "summary": {
            "exam_count": len(all_data),
            "total_questions": len(items),
            "high_similarity_pairs": len(pairs),
        },
        "subject_by_exam": {k: dict(v) for k, v in subj_by_exam.items()},
        "top_keywords": kw_counter.most_common(25),
        "top_similar_pairs": [],
    }

    for p in pairs[:80]:
        shared_kw = sorted(p["a"]["keywords"] & p["b"]["keywords"])
        report["top_similar_pairs"].append(
            {
                "pair": [p["a"]["id"], p["b"]["id"]],
                "exams": [p["a"]["exam"], p["b"]["exam"]],
                "qnums": [p["a"]["qnum"], p["b"]["qnum"]],
                "subjects": [p["a"]["subject"], p["b"]["subject"]],
                "tfidf": p["tfidf"],
                "seq": p["seq"],
                "score": p["score"],
                "shared_keywords": shared_kw,
                "text_a_preview": p["a"]["text"][:220],
                "text_b_preview": p["b"]["text"][:220],
            }
        )

    out = root / "data" / "analysis_report.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    print(f"report -> {out}")


if __name__ == "__main__":
    main()
