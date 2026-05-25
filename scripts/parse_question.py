#!/usr/bin/env python3
"""問題文を設問本体と選択肢に分割する。"""
import re


def zen_to_int(s: str) -> int:
    trans = str.maketrans("０１２３４５６７８９", "0123456789")
    return int(str(s).translate(trans))


def normalize_spaces(text: str) -> str:
    text = text.replace("\u3000", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def extract_sub_statements(text: str) -> list[dict]:
    """ア〜エの記述を抽出。"""
    subs = []
    for m in re.finditer(
        r"([アイウエ])[　 ](.+?)(?=\s[アイウエ][　 ]|\s[1-4１-４][　 ]|$)",
        text,
    ):
        subs.append({"id": m.group(1), "text": m.group(2).strip()})
    return subs


def extract_numbered_choices(text: str) -> list[dict]:
    """1〜4 の選択肢を抽出。"""
    choices = []
    for m in re.finditer(
        r"(?:^|\s)([1-4１-４])[　\s]*(.+?)(?=(?:\s[1-4１-４][　\s])|$)",
        text,
    ):
        cid = str(zen_to_int(m.group(1)))
        ctext = m.group(2).strip()
        if len(ctext) >= 2:
            choices.append({"id": cid, "label": f"{cid}", "text": ctext})
    # id 重複は先勝ち
    seen = set()
    out = []
    for c in choices:
        if c["id"] in ("1", "2", "3", "4") and c["id"] not in seen:
            seen.add(c["id"])
            out.append(c)
    return sorted(out, key=lambda x: int(x["id"]))


def parse_question(text: str) -> dict:
    raw = normalize_spaces(text)
    if len(raw) < 20:
        return {"stem": raw, "subStatements": [], "choices": [], "choiceType": "unknown"}

    sub_statements = extract_sub_statements(raw)

    # 選択肢ブロック: 最後の「1 」から始まる4択を優先
    choice_region = raw
    if sub_statements:
        last_sub = sub_statements[-1]
        pos = raw.rfind(last_sub["text"])
        if pos >= 0:
            choice_region = raw[pos + len(last_sub["text"]) :]

    choices = extract_numbered_choices(choice_region)
    if len(choices) < 2:
        choices = extract_numbered_choices(raw)

    # 設問文: 選択肢・サブ記述を除いた部分
    stem = raw
    if choices:
        first = re.search(r"\s[1-4１-４][　 ]", raw)
        if first and (not sub_statements or first.start() < raw.rfind(sub_statements[0]["id"])):
            # サブ記述がある場合は「どれか」の後まで
            pass
    # stem = 問いの冒頭からサブ記述前、または最初の選択肢前
    cut_pos = len(raw)
    if choices:
        m0 = re.search(r"\s" + re.escape(choices[0]["id"]) + r"[　 ]", raw)
        if m0:
            cut_pos = min(cut_pos, m0.start())
    if sub_statements:
        m1 = raw.find(sub_statements[0]["id"] + " ")
        if m1 > 0:
            stem = raw[:m1].strip()
        else:
            stem = raw[:cut_pos].strip()
    else:
        stem = raw[:cut_pos].strip()

    stem = normalize_spaces(stem)
    if not stem:
        stem = raw[:400]

    choice_type = "single"
    if sub_statements:
        if any("いくつ" in raw or "一つ" in c["text"] for c in choices):
            choice_type = "combo_count"
        else:
            choice_type = "combo_set"

    return {
        "stem": stem,
        "subStatements": sub_statements,
        "choices": choices,
        "choiceType": choice_type,
    }


if __name__ == "__main__":
    import json
    from pathlib import Path

    sample = Path(__file__).parents[1] / "data" / "extracted" / "R7.json"
    data = json.loads(sample.read_text())
    for qn in ["1", "3", "5"]:
        p = parse_question(data["questions"][qn])
        print("=== Q", qn, p["choiceType"], "===")
        print("STEM:", p["stem"][:100])
        for s in p["subStatements"]:
            print(f"  {s['id']}: {s['text'][:50]}...")
        for c in p["choices"]:
            print(f"  [{c['id']}] {c['text'][:50]}...")
