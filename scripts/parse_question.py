#!/usr/bin/env python3
"""問題文を設問本体と選択肢に分割する。"""
import re

# 数量・条文参照直後の数字は除外
UNIT_AFTER_DIGIT = re.compile(r"^[月年日時分秒歳円万㎡％%\d]")
CHOICE_DIGIT = re.compile(
    r"(?<![0-9０-９])(?<![条第年])([1-4１-４])"
    r"(?:[　\s]+|[\.．、\-ー—\'\"＇''「」\[\]】\]\]]*)",
    re.UNICODE,
)
STEM_END_MARKERS = re.compile(
    r"(どれか|どれ|いくつ|一つ|組合せ|掲げ|ものは|ものを|記述のうち)[。．？！\s]*$",
)


def zen_to_int(s: str) -> int:
    trans = str.maketrans("０１２３４５６７８９", "0123456789")
    return int(str(s).translate(trans))


def normalize_spaces(text: str) -> str:
    text = text.replace("\u3000", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _content_start(text: str, after_digit_end: int) -> int:
    i = after_digit_end
    while i < len(text) and text[i] in " \u3000．.、-ー—'\"＇''「」[]】]":
        i += 1
    return i


def _is_false_positive(text: str, digit_start: int, content_start: int) -> bool:
    if content_start >= len(text):
        return True
    if UNIT_AFTER_DIGIT.match(text[content_start:]):
        return True
    before = text[max(0, digit_start - 4):digit_start]
    if before.endswith("第") or before.endswith("条") or before.endswith("年"):
        return True
    return False


def collect_choice_candidates(text: str) -> list[tuple[str, int, int]]:
    """(id, marker_start, content_start)"""
    out = []
    for m in CHOICE_DIGIT.finditer(text):
        cid = str(zen_to_int(m.group(1)))
        cs = _content_start(text, m.end())
        if _is_false_positive(text, m.start(1), cs):
            continue
        out.append((cid, m.start(), cs))
    return out


def build_choice_chain(candidates: list[tuple[str, int, int]]) -> list[tuple[str, int, int]]:
    """出現順で 1→2→3→4 の鎖を組み立てる（1欠落時は2から開始可）。"""
    if not candidates:
        return []
    order = ["1", "2", "3", "4"]
    chain = []
    pos = 0
    start_idx = 0
    if candidates[0][0] != "1":
        for i, want in enumerate(order):
            if any(c[0] == want for c in candidates):
                start_idx = order.index(want)
                break
    for want in order[start_idx:]:
        pick = None
        for c in candidates:
            if c[0] == want and c[1] >= pos:
                pick = c
                break
        if not pick:
            break
        chain.append(pick)
        pos = pick[1] + 1
    return chain if len(chain) >= 2 else []


def _infer_stem_end(text: str, first_marker: int) -> int:
    head = text[:first_marker]
    m = STEM_END_MARKERS.search(head)
    if m:
        return m.end()
    m2 = re.search(r"[。．？！]", head[::-1])
    if m2:
        return len(head) - m2.start()
    return first_marker


def chain_to_choices(text: str, chain: list[tuple[str, int, int]]) -> list[dict]:
    if len(chain) < 2:
        return []
    choices = []
    if chain[0][0] != "1":
        stem_end = _infer_stem_end(text, chain[0][1])
        c1_text = text[stem_end:chain[0][1]].strip(" ．.、-ー—'\"[]】\]]")
        c1_text = re.sub(r"^[\]】\s]+", "", c1_text).strip()
        if len(c1_text) >= 4:
            choices.append({"id": "1", "label": "1", "text": c1_text})
    for i, (cid, _ms, cs) in enumerate(chain):
        end = chain[i + 1][1] if i + 1 < len(chain) else len(text)
        ctext = text[cs:end].strip()
        if len(ctext) >= 2 and not any(c["id"] == cid for c in choices):
            choices.append({"id": cid, "label": cid, "text": ctext})
        elif any(c["id"] == cid for c in choices):
            pass
        else:
            choices.append({"id": cid, "label": cid, "text": ctext})
    # 重複idは先勝ち、並べ替え
    seen = set()
    uniq = []
    for c in sorted(choices, key=lambda x: int(x["id"])):
        if c["id"] not in seen:
            seen.add(c["id"])
            uniq.append(c)
    return uniq


def extract_sub_statements(text: str) -> list[dict]:
    subs = []
    for m in re.finditer(
        r"([アイウエ])[　 ](.+?)(?=\s[アイウエ][　 ]|\s[1-4１-４][　 ]|$)",
        text,
    ):
        subs.append({"id": m.group(1), "text": m.group(2).strip()})
    return subs


def extract_numbered_choices(text: str) -> list[dict]:
    cands = collect_choice_candidates(text)
    chain = build_choice_chain(cands)
    return chain_to_choices(text, chain)


def first_choice_marker_pos(text: str):
    cands = collect_choice_candidates(text)
    chain = build_choice_chain(cands)
    if not chain:
        return None
    if chain[0][0] != "1":
        return _infer_stem_end(text, chain[0][1])
    return chain[0][1]


def parse_question(text: str) -> dict:
    raw = normalize_spaces(text)
    if len(raw) < 20:
        return {"stem": raw, "subStatements": [], "choices": [], "choiceType": "unknown"}

    sub_statements = extract_sub_statements(raw)

    choice_region = raw
    if sub_statements:
        last_sub = sub_statements[-1]
        pos = raw.rfind(last_sub["text"])
        if pos >= 0:
            choice_region = raw[pos + len(last_sub["text"]) :]

    choices = extract_numbered_choices(choice_region)
    if len(choices) < 2:
        choices = extract_numbered_choices(raw)

    cut_pos = len(raw)
    if choices:
        pos = first_choice_marker_pos(raw)
        if pos is not None:
            cut_pos = pos
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
        if "いくつ" in raw or any("一つ" in c["text"] for c in choices):
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

    all_data = json.loads(
        (Path(__file__).parents[1] / "data" / "extracted" / "all.json").read_text()
    )
    fail = 0
    for ex, d in all_data.items():
        for qn, t in d["questions"].items():
            if len(parse_question(t)["choices"]) < 2:
                fail += 1
    print("fail", fail, "/ 560")
    for qn in ["14", "1", "12"]:
        p = parse_question(all_data["H29"]["questions"].get(qn) or all_data["H28"]["questions"][qn])
        print(f"Q{qn}:", len(p["choices"]), [c["id"] for c in p["choices"]])
