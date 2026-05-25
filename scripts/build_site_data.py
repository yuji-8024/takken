#!/usr/bin/env python3
"""サイト用 JSON を生成する。"""
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from generate_problem_bank import (  # noqa: E402
    DATA,
    EXAM_LABEL,
    EXAM_ORDER,
    TOPICS,
    classify_question,
)
from parse_question import parse_question  # noqa: E402
from generate_explanation import explanation_to_html, generate_explanation  # noqa: E402

OUT = ROOT / "site" / "data" / "bank.json"
ANSWERS_PATH = ROOT / "data" / "answers.json"


def md_to_html(text: str) -> str:
    """簡易マークダウン→HTML。"""
    lines = text.strip().split("\n")
    html = []
    in_list = False
    for line in lines:
        s = line.strip()
        if not s:
            if in_list:
                html.append("</ul>")
                in_list = False
            continue
        s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
        if s.startswith("- "):
            if not in_list:
                html.append("<ul>")
                in_list = True
            html.append(f"<li>{s[2:]}</li>")
        else:
            if in_list:
                html.append("</ul>")
                in_list = False
            html.append(f"<p>{s}</p>")
    if in_list:
        html.append("</ul>")
    return "\n".join(html)


def lookup_answer(answers_db: dict, exam: str, qnum: int):
    exam_ans = answers_db.get(exam, {})
    a = exam_ans.get(str(qnum))
    if a in ("none", "なし"):
        return "none"
    if a in ("any", "all"):
        return "any"
    if a in ("1", "2", "3", "4"):
        return a
    return None


def main():
    raw = json.loads(DATA.read_text(encoding="utf-8"))
    answers_db = {}
    if ANSWERS_PATH.exists():
        answers_db = json.loads(ANSWERS_PATH.read_text(encoding="utf-8"))

    by_topic = defaultdict(list)
    parsed_count = 0
    answer_count = 0

    for ex in EXAM_ORDER:
        if ex not in raw:
            continue
        for qn, text in raw[ex]["questions"].items():
            tid = classify_question(qn, text)
            qid = f"{ex}_Q{qn}"
            parsed = parse_question(text.strip())
            correct = lookup_answer(answers_db, ex, int(qn))
            # 令和4問48など「全解答正解」注記
            if ex == "R4" and int(qn) == 48 and not correct:
                correct = "any"
            if parsed.get("choices"):
                parsed_count += 1
            if correct:
                answer_count += 1
            topic_name = next(t[1] for t in TOPICS if t[0] == tid)
            exp = generate_explanation(
                {"stem": parsed["stem"], "text": text.strip(), "choices": parsed["choices"],
                 "subStatements": parsed["subStatements"], "correctAnswer": correct},
                tid,
                topic_name,
            )
            by_topic[tid].append({
                "id": qid,
                "topicId": tid,
                "exam": ex,
                "examLabel": EXAM_LABEL[ex],
                "qnum": int(qn),
                "text": text.strip(),
                "stem": parsed["stem"],
                "subStatements": parsed["subStatements"],
                "choices": parsed["choices"],
                "choiceType": parsed["choiceType"],
                "correctAnswer": correct,
                "explanationHtml": explanation_to_html(exp),
            })

    tier_info = {
        "A": {
            "label": "第I部",
            "title": "ほぼ出る問題",
            "subtitle": "必須・合格の土台",
            "color": "#0d6e4f",
            "desc": "毎年〜10/12回以上。ここを落とすと不合格リスク大。",
        },
        "B": {
            "label": "第II部",
            "title": "合格点対策",
            "subtitle": "33〜37点を安定させる",
            "color": "#1a56db",
            "desc": "第I部の後に優先。弱点論点を反復。",
        },
        "C": {
            "label": "第III部",
            "title": "満点・高得点",
            "subtitle": "38点以上狙い",
            "color": "#7c3aed",
            "desc": "計算・判例・難問。余力で。",
        },
    }

    topics = []
    for tid, name, tier, *_rest in TOPICS:
        meta = next(t for t in TOPICS if t[0] == tid)
        qs = sorted(
            by_topic.get(tid, []),
            key=lambda q: (EXAM_ORDER.index(q["exam"]), q["qnum"]),
        )
        if not qs:
            continue
        topics.append({
            "id": tid,
            "name": name,
            "tier": tier,
            "questionCount": len(qs),
            "descriptionHtml": md_to_html(meta[4]),
            "tipsHtml": md_to_html(meta[5].replace("💡 **Tips**", "").replace("💡", "").strip()),
            "questions": qs,
        })

    formulas = [
        {"title": "媒介報酬（46条）", "items": [
            "売買・交換: 代金 × 3% ＋ 6万円",
            "賃貸: 1か月賃料 × 1.08",
            "権利金付き賃貸: 権利金を売買代金とみなして 3%+6万",
        ]},
        {"title": "印紙税", "items": [
            "課税標準 = 契約書の記載金額（交換は高い方）",
            "過少申告: 本税 + 10%",
            "領収書3万円未満は非課税",
        ]},
        {"title": "クーリング・オフ（37条の2）", "items": [
            "告知から8日以内・書面で解除",
            "損害賠償・違約金請求不可・受領金全額返還",
        ]},
        {"title": "抵当権配当", "items": [
            "売却代金 → 費用 → 第一順位 → 第二順位…",
            "順位譲渡・放棄で配当額が変わる（過去問の数値練習）",
        ]},
    ]

    payload = {
        "meta": {
            "title": "宅建 過去10年 問題バンク",
            "source": "RETIO公式過去問（平成28〜令和7）",
            "sourceUrl": "https://www.retio.or.jp/exam/past_ques_ans/other/",
            "totalQuestions": sum(t["questionCount"] for t in topics),
            "passLine": "近年 33〜37点 / 50問（45問換算で約30〜33点）",
            "examOrder": EXAM_ORDER,
            "examLabels": EXAM_LABEL,
            "tierInfo": tier_info,
            "parsedWithChoices": parsed_count,
            "withAnswers": answer_count,
        },
        "formulas": formulas,
        "topics": topics,
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {OUT} ({OUT.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
