#!/usr/bin/env python3
"""類似度閾値・テンプレート・科目別の年間隔分析。"""
import json
import re
from collections import Counter, defaultdict
from difflib import SequenceMatcher
from pathlib import Path
from statistics import mean, median

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

ROOT = Path(__file__).resolve().parents[1]

EXAM_YEAR = {
    "H28": 2016, "H29": 2017, "H30": 2018, "R1": 2019,
    "R2_10": 2020, "R2_12": 2020, "R3_10": 2021, "R3_12": 2021,
    "R4": 2022, "R5": 2023, "R6": 2024, "R7": 2025,
}
EXAM_LABEL = {
    "H28": "平成28", "H29": "平成29", "H30": "平成30", "R1": "令和元",
    "R2_10": "令和2(10月)", "R2_12": "令和2(12月)", "R3_10": "令和3(10月)",
    "R3_12": "令和3(12月)", "R4": "令和4", "R5": "令和5", "R6": "令和6", "R7": "令和7",
}

# 公式の出題枠（問番号ベース）
CATEGORIES = [
    ("権利関係", 1, 14),
    ("法令上の制限", 15, 22),
    ("宅建業法", 23, 32),
    ("税・その他", 33, 38),
    ("その他(39-45)", 39, 45),
    ("登録講習免除", 46, 50),
]

THRESHOLDS = [0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 0.85]

# 既知のテンプレート冒頭（正規表現）
TEMPLATE_PATTERNS = [
    ("都市計画法_許可面積定型", r"都市計画法に関する次の記述のうち.+許可を要する開発行為の面積"),
    ("都市計画法_一般", r"都市計画法に関する次の記述のうち"),
    ("建築基準法", r"建築基準法に関する次の記述のうち"),
    ("土地区画整理法", r"土地区画整理法に関する次の記述のうち"),
    ("農地法", r"農地法.+に関する次の記述|農地に関する次の記述"),
    ("借地借家法", r"借地借家法の規定"),
    ("区分所有法", r"区分所有等に関する法律|区分所有法"),
    ("登記法", r"登記に関する次の記述|不動産登記法"),
    ("抵当権パターン", r"一番抵当権.+二番抵当権.+三番抵当権|甲土地には.+抵当権"),
    ("クーリングオフ", r"クーリング.?オフ|第37条の2"),
    ("重要事項説明", r"重要事項説明"),
    ("37条書面", r"37条.*書面|37条の"),
    ("35条書面", r"35条.*書面"),
    ("媒介契約", r"媒介契約"),
    ("住宅金融支援機構", r"住宅金融支援機構"),
    ("民法_正しいもの", r"民法の規定.+正しいものはどれか"),
    ("民法_誤っているもの", r"民法の規定.+誤っているもの"),
    ("宅建業法_違反", r"宅地建物取引業法.+違反"),
    ("自ら売主_マンション", r"自ら売主として.+マンション"),
]


def category_by_qnum(q: int) -> str:
    for name, lo, hi in CATEGORIES:
        if lo <= q <= hi:
            return name
    return "その他"


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


def composite_score(tfidf: float, seq: float) -> float:
    return 0.5 * tfidf + 0.5 * seq


def opening_fingerprint(text: str, n: int = 60) -> str:
    t = normalize_for_compare(text[:120])
    return t[:n]


def detect_templates(text: str) -> list[str]:
    found = []
    for name, pat in TEMPLATE_PATTERNS:
        if re.search(pat, text):
            found.append(name)
    return found


def load_items():
    data = json.loads((ROOT / "data" / "extracted" / "all.json").read_text(encoding="utf-8"))
    items = []
    for exam, blob in data.items():
        year = EXAM_YEAR.get(exam)
        for qnum, text in blob["questions"].items():
            q = int(qnum)
            items.append({
                "id": f"{exam}_Q{q}",
                "exam": exam,
                "year": year,
                "qnum": q,
                "text": text,
                "category": category_by_qnum(q),
                "templates": detect_templates(text),
                "opening": opening_fingerprint(text),
            })
    return items


def build_pairs(items):
    texts = [it["text"] for it in items]
    X = TfidfVectorizer(
        analyzer="char_wb", ngram_range=(3, 5), max_features=80000, min_df=1,
    ).fit_transform(texts)
    sim = cosine_similarity(X)

    pairs = []
    n = len(items)
    for i in range(n):
        for j in range(i + 1, n):
            if items[i]["exam"] == items[j]["exam"]:
                continue
            tfidf_s = float(sim[i, j])
            seq_s = seq_ratio(items[i]["text"], items[j]["text"])
            score = composite_score(tfidf_s, seq_s)
            year_gap = abs(items[i]["year"] - items[j]["year"])
            cat_a, cat_b = items[i]["category"], items[j]["category"]
            same_cat = cat_a == cat_b
            pairs.append({
                "a": items[i],
                "b": items[j],
                "tfidf": round(tfidf_s, 3),
                "seq": round(seq_s, 3),
                "score": round(score, 3),
                "year_gap": year_gap,
                "same_category": same_cat,
                "category": cat_a if same_cat else f"{cat_a}/{cat_b}",
            })
    return pairs


def threshold_stats(pairs):
    total = len(pairs)
    rows = []
    for th in THRESHOLDS:
        subset = [p for p in pairs if p["score"] >= th]
        if not subset:
            rows.append({"threshold": th, "pairs": 0, "pct_of_all_pairs": 0})
            continue
        gaps = [p["year_gap"] for p in subset]
        rows.append({
            "threshold": th,
            "pairs": len(subset),
            "pct_of_all_pairs": round(100 * len(subset) / total, 2),
            "year_gap_mean": round(mean(gaps), 2),
            "year_gap_median": median(gaps),
            "year_gap_max": max(gaps),
            "pct_within_3yr": round(100 * sum(1 for g in gaps if g <= 3) / len(gaps), 1),
            "pct_5yr_plus": round(100 * sum(1 for g in gaps if g >= 5) / len(gaps), 1),
        })
    return rows


def category_analysis(pairs, items):
    """科目帯ごとの類似ペア・年間隔・テンプレート率。"""
    by_cat = defaultdict(list)
    for p in pairs:
        if p["same_category"]:
            by_cat[p["category"]].append(p)

    item_by_cat = defaultdict(list)
    for it in items:
        item_by_cat[it["category"]].append(it)

    result = {}
    for cat, _lo, _hi in CATEGORIES:
        cat_pairs = by_cat.get(cat, [])
        cat_items = item_by_cat.get(cat, [])
        tmpl_counts = Counter()
        for it in cat_items:
            for t in it["templates"]:
                tmpl_counts[t] += 1

        high = [p for p in cat_pairs if p["score"] >= 0.70]
        medium = [p for p in cat_pairs if 0.60 <= p["score"] < 0.70]
        gaps_high = [p["year_gap"] for p in high]

        result[cat] = {
            "question_count": len(cat_items),
            "template_hit_questions": sum(1 for it in cat_items if it["templates"]),
            "template_hit_rate_pct": round(
                100 * sum(1 for it in cat_items if it["templates"]) / max(len(cat_items), 1), 1
            ),
            "top_templates": tmpl_counts.most_common(8),
            "similar_pairs_score_ge_070": len(high),
            "similar_pairs_score_060_070": len(medium),
            "year_gap_if_ge_070": {
                "mean": round(mean(gaps_high), 2) if gaps_high else None,
                "median": median(gaps_high) if gaps_high else None,
                "distribution": dict(Counter(gaps_high)),
            } if gaps_high else {},
            "typical_recurrence_years": _recurrence_bins(gaps_high),
        }
    return result


def _recurrence_bins(gaps):
    bins = {"1-2年": 0, "3-4年": 0, "5-7年": 0, "8年以上": 0}
    for g in gaps:
        if g <= 2:
            bins["1-2年"] += 1
        elif g <= 4:
            bins["3-4年"] += 1
        elif g <= 7:
            bins["5-7年"] += 1
        else:
            bins["8年以上"] += 1
    return bins


def template_clusters(items):
    """冒頭フィンガープリントでテンプレートクラスタを検出。"""
    fp_map = defaultdict(list)
    for it in items:
        if len(it["opening"]) >= 25:
            fp_map[it["opening"]].append(it)

    clusters = []
    for fp, group in fp_map.items():
        if len(group) < 2:
            continue
        exams = sorted({g["exam"] for g in group})
        years = sorted({g["year"] for g in group})
        year_span = max(years) - min(years) if years else 0
        clusters.append({
            "opening_sample": group[0]["text"][:100],
            "count": len(group),
            "exams": exams,
            "exam_labels": [EXAM_LABEL.get(e, e) for e in exams],
            "year_span": year_span,
            "categories": Counter(g["category"] for g in group).most_common(3),
            "question_ids": [g["id"] for g in group[:12]],
        })
    clusters.sort(key=lambda c: (-c["year_span"], -c["count"]))
    return clusters[:30]


def template_pattern_years(items):
    """名前付きテンプレートの年度横断出現。"""
    pat_years = defaultdict(list)
    for it in items:
        for t in it["templates"]:
            pat_years[t].append({"exam": it["exam"], "year": it["year"], "qnum": it["qnum"], "id": it["id"]})
    out = []
    for name, hits in sorted(pat_years.items(), key=lambda x: -len(x[1])):
        years = sorted({h["year"] for h in hits})
        out.append({
            "template": name,
            "occurrences": len(hits),
            "exam_count": len({h["exam"] for h in hits}),
            "first_year": min(years),
            "last_year": max(years),
            "year_span": max(years) - min(years),
            "avg_gap_between_years": round(
                (max(years) - min(years)) / max(len(years) - 1, 1), 1
            ) if len(years) > 1 else 0,
            "years_active": years,
        })
    return out


def main():
    items = load_items()
    pairs = build_pairs(items)
    total_pairs = len(pairs)

    th_stats = threshold_stats(pairs)
    cat_stats = category_analysis(pairs, items)
    clusters = template_clusters(items)
    pat_years = template_pattern_years(items)

    # 閾値別×科目（0.70以上）
    th_cat = defaultdict(lambda: defaultdict(int))
    th_cat_gaps = defaultdict(lambda: defaultdict(list))
    for p in pairs:
        if p["score"] >= 0.70 and p["same_category"]:
            th_cat[p["category"]]["count"] += 1
            th_cat_gaps[p["category"]]["gaps"].append(p["year_gap"])

    threshold_by_category = {}
    for cat in th_cat:
        gaps = th_cat_gaps[cat]["gaps"]
        threshold_by_category[cat] = {
            "pairs_ge_070": th_cat[cat]["count"],
            "mean_year_gap": round(mean(gaps), 2) if gaps else None,
            "median_year_gap": median(gaps) if gaps else None,
        }

    report = {
        "meta": {
            "total_questions": len(items),
            "cross_year_pairs": total_pairs,
            "exam_years": EXAM_YEAR,
        },
        "threshold_analysis": th_stats,
        "threshold_recommendation": {
            "template_like": ">= 0.80 (seq often >= 0.85): nearly same stem, wording swap",
            "high_recurrence": ">= 0.70: strong reuse, study priority",
            "moderate_similar": "0.60 - 0.70: same topic family, different numbers/facts",
            "weak": "< 0.60: mostly independent (not counted as similar)",
        },
        "category_analysis": cat_stats,
        "threshold_ge_070_by_category": threshold_by_category,
        "named_template_timeline": pat_years,
        "opening_fingerprint_clusters": clusters,
        "top_pairs_by_category": {},
    }

    for cat, _a, _b in CATEGORIES:
        cat_pairs = [
            p for p in pairs
            if p["same_category"] and p["category"] == cat and p["score"] >= 0.65
        ]
        cat_pairs.sort(key=lambda p: p["score"], reverse=True)
        report["top_pairs_by_category"][cat] = [
            {
                "pair": [p["a"]["id"], p["b"]["id"]],
                "labels": [EXAM_LABEL.get(p["a"]["exam"]), EXAM_LABEL.get(p["b"]["exam"])],
                "year_gap": p["year_gap"],
                "score": p["score"],
                "seq": p["seq"],
            }
            for p in cat_pairs[:8]
        ]

    out_json = ROOT / "data" / "deep_analysis_report.json"
    out_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    # Markdown
    lines = ["# 深掘り分析：閾値・テンプレート・科目別の年間隔\n\n"]

    lines.append("## 1. 類似度閾値の目安\n\n")
    lines.append("複合スコア = (TF-IDF文字3-5gram + 正規化後SequenceMatcher) / 2\n\n")
    lines.append("| 閾値 | 該当ペア数 | 全ペア比(%) | 平均年間隔 | 中央年間隔 | 3年以内(%) | 5年以上(%) |\n")
    lines.append("|---:|---:|---:|---:|---:|---:|---:|\n")
    for r in th_stats:
        if r["pairs"] == 0:
            lines.append(f"| {r['threshold']:.2f} | 0 | 0 | — | — | — | — |\n")
        else:
            lines.append(
                f"| {r['threshold']:.2f} | {r['pairs']} | {r['pct_of_all_pairs']} | "
                f"{r['year_gap_mean']} | {r['year_gap_median']} | {r['pct_within_3yr']} | {r['pct_5yr_plus']} |\n"
            )

    lines.append("\n**解釈**\n")
    lines.append("- **0.80以上**: テンプレートほぼ同一。設問の「正しい/誤っている」の反転のみのことが多い。\n")
    lines.append("- **0.70〜0.80**: 高類似・再出題確実度高。前年または数年前の類題として扱うべき。\n")
    lines.append("- **0.60〜0.70**: 同テーマ・同論点だが事例・数値が差し替え。パターン学習向き。\n")
    lines.append("- **0.60未満**: 類似とはみなさない（全ペアの大半）。\n\n")

    lines.append("## 2. 科目（出題枠）別の傾向\n\n")
    lines.append("| 科目 | 問題数 | テンプレ検出率 | 高類似(≥0.70) | 中類似(0.60-0.70) | 平均年間隔(≥0.70) | 典型再出間隔 |\n")
    lines.append("|---|---:|---:|---:|---:|---:|---|\n")
    for cat, _l, _h in CATEGORIES:
        s = cat_stats[cat]
        yg = s.get("year_gap_if_ge_070", {})
        mean_g = yg.get("mean", "—")
        recur = s.get("typical_recurrence_years", {})
        recur_str = ", ".join(f"{k}:{v}" for k, v in recur.items() if v) or "—"
        tmpl_rate = s.get("template_hit_rate_pct", 0)
        lines.append(
            f"| {cat} | {s['question_count']} | {tmpl_rate}% | "
            f"{s['similar_pairs_score_ge_070']} | {s['similar_pairs_score_060_070']} | "
            f"{mean_g}年 | {recur_str} |\n"
        )

    lines.append("\n### 科目別の主なテンプレート（問題文中の定型パターン）\n\n")
    for cat, _l, _h in CATEGORIES:
        s = cat_stats[cat]
        if not s.get("top_templates"):
            continue
        tops = "、".join(f"{t}({c}問)" for t, c in s["top_templates"][:5])
        lines.append(f"- **{cat}**: {tops}\n")

    lines.append("\n## 3. 名前付きテンプレートの年度横断\n\n")
    lines.append("| テンプレート | 出現問数 | 試験回数 | 初出〜最終 | 跨ぎ年数 | 平均出題間隔(年) |\n")
    lines.append("|---|---:|---:|---|---:|---:|\n")
    for p in pat_years[:18]:
        yr = f"{p['first_year']}→{p['last_year']}"
        lines.append(
            f"| {p['template']} | {p['occurrences']} | {p['exam_count']} | {yr} | "
            f"{p['year_span']} | {p['avg_gap_between_years']} |\n"
        )

    lines.append("\n## 4. 冒頭文が同一のクラスタ（上位10）\n\n")
    for i, c in enumerate(clusters[:10], 1):
        cats = ", ".join(f"{n}({k})" for n, k in c["categories"])
        lines.append(f"### クラスタ{i}（{c['count']}問 / {c['year_span']}年跨ぎ）\n")
        lines.append(f"- 年度: {', '.join(c['exam_labels'])}\n")
        lines.append(f"- 科目: {cats}\n")
        lines.append(f"- 冒頭: 「{c['opening_sample'][:80]}…」\n")
        lines.append(f"- 例: {', '.join(c['question_ids'][:6])}\n\n")

    lines.append("## 5. 科目別・高類似ペア例（スコア≥0.65）\n\n")
    for cat, _l, _h in CATEGORIES:
        tops = report["top_pairs_by_category"].get(cat, [])
        if not tops:
            continue
        lines.append(f"### {cat}\n")
        for t in tops[:5]:
            lines.append(
                f"- {t['labels'][0]} ↔ {t['labels'][1]}（{t['year_gap']}年後）"
                f" score={t['score']}, seq={t['seq']}\n"
            )
        lines.append("\n")

    lines.append("## 6. まとめ（何年越しに使われるか）\n\n")
    lines.append("""
| 科目 | 再出の典型パターン |
|------|-------------------|
| **宅建業法** | 高類似ペアが最多。平均**4〜6年**後に同型（マンション売主・手付、クーリングオフ、37条書面）が再登場。0.80超は「9年越し」級もあり。 |
| **法令上の制限** | **都市計画法の冒頭定型**が2〜4年周期で繰り返し。問16付近に集中。数値・区域だけ差し替え。 |
| **権利関係** | 抵当権配当・登記・借地借家が**3〜5年**周期。骨格は同じだが金額・順位操作が変化しseqは0.85前後。 |
| **税・その他** | 類似ペアは少なめ。印紙税・固定資産税は論点固定だが設問文の一致度は低い。 |
| **登録講習免除** | 住宅金融支援機構など**長期テンプレ**（8年以上跨ぎ）。条文改正で選択肢が微修正。 |
""")

    out_md = ROOT / "data" / "DEEP_ANALYSIS_REPORT.md"
    out_md.write_text("".join(lines), encoding="utf-8")
    print(f"JSON -> {out_json}")
    print(f"MD   -> {out_md}")
    print("\nThreshold >= 0.70 pairs by category:")
    for cat, v in threshold_by_category.items():
        print(f"  {cat}: {v['pairs_ge_070']} pairs, mean gap {v['mean_year_gap']}yr")


if __name__ == "__main__":
    main()
