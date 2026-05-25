#!/usr/bin/env python3
"""問題ごとの正解理由・解説を生成する。"""
import re
from typing import Any


def _choice_map(q: dict) -> dict[str, str]:
    return {c["id"]: c["text"] for c in q.get("choices", [])}


def _stem(q: dict) -> str:
    return q.get("stem") or q.get("text", "")


def _ask_style(q: dict) -> str:
    s = _stem(q)
    if "誤っている" in s or "誤り" in s:
        return "wrong"
    if "いくつ" in s:
        return "count"
    if "組合せ" in s or "掲げ" in s:
        return "combo"
    if "最も不適当" in s:
        return "least"
    return "correct"


def _wrong_hints(q: dict, correct_id: str) -> list[str]:
    hints = []
    for c in q.get("choices", []):
        if c["id"] == correct_id:
            continue
        t = c["text"][:80] + ("…" if len(c["text"]) > 80 else "")
        hints.append(f"選択肢{c['id']}は要件・数値・主体のいずれかが条文と合わないことが多いです。（{t}）")
        if len(hints) >= 2:
            break
    return hints


# 論点別の解説テンプレート
TOPIC_EXPLAINERS: dict[str, Any] = {}


def _register(tid: str):
    def deco(fn):
        TOPIC_EXPLAINERS[tid] = fn
        return fn
    return deco


@_register("touki_14")
def _ex_touki(q, correct, cmap):
    why = (
        "不動産登記法は、権利の得喪を第三者に対抗するための公示手段です。"
        "保存登記・変更登記・抹消登記の申請義務者・期限、登記できる権利の範囲が定番です。"
    )
    if correct in cmap:
        why += f" 本問の正解肢（選択肢{correct}）は、この要件に合致します：{cmap[correct][:100]}…"
    return why, ["登記原因と申請人の組み合わせ", "1ヶ月以内の申請期限", "区分建物の表題登記→専有部分"]


@_register("kubun_13")
def _ex_kubun(q, correct, cmap):
    why = "区分所有法は、マンションの共用部分・専有部分・管理組合・管理者の権限が中心です。"
    if correct in cmap:
        why += f" 選択肢{correct}が正しい理由は、規約・集会・管理者の記述が区分所有法の条文どおりだからです。"
    return why, ["管理者の報告義務", "規約の効力", "共用部分の持分"]


@_register("toshi_keikaku")
def _ex_toshi(q, correct, cmap):
    why = (
        "都市計画法は、開発許可・用途地域・区域区分（市街化区域/調整区域）の可否が問われます。"
        "許可を要する開発行為の面積・目的（住宅・店舗・工場等）と区域の組み合わせに注意してください。"
    )
    return why, ["開発許可の要否", "都道府県知事（指定都市は市長）", "面積の数値差し替え"]


@_register("juyou_jikou")
def _ex_juyou(q, correct, cmap):
    why = (
        "宅建業法35条の重要事項説明は、**契約締結前**に**宅地建物取引士**が行い、"
        "説明書面を交付します。相手方が宅建業者の場合も説明が必要なことがあります。"
    )
    return why, ["説明のタイミング", "宅建士の関与", "35条書面・37条書面との区別"]


@_register("cooling_off")
def _ex_cooling(q, correct, cmap):
    why = (
        "37条の2（クーリング・オフ）は、一定の場所で申込み・契約した買主が、"
        "**告知を受けた日から8日以内**に**書面**で解除でき、手付等は**全額返還**、"
        "損害賠償・違約金の請求はできません。"
    )
    return why, ["8日以内", "書面による解除", "喫茶店契約の引っかけ"]


@_register("tezuke_41")
def _ex_teuke(q, correct, cmap):
    why = (
        "41条は自ら売主業者が受領する手付・中間金の保全（供託・保証委託等）がテーマです。"
        "建築中のマンションでは、手付・中間金の合計について保全が必要になる場面が多いです。"
    )
    return why, ["保全措置なし→支払拒絶", "手付の上限（引渡し前）", "自ら売主か媒介か"]


@_register("hosyu")
def _ex_hosyu(q, correct, cmap):
    why = (
        "媒介報酬の限度：売買・交換は**代金×3%＋6万円**、賃貸は**1か月賃料×1.08**。"
        "権利金がある賃貸は権利金を売買代金とみなして計算。広告料を報酬に上乗せできません。"
    )
    return why, ["3%+6万", "1.08", "消費税・両手仲介の計算"]


@_register("inshi")
def _ex_inshi(q, correct, cmap):
    why = "印紙税は課税文書の**記載金額**が課税標準。交換は**高い方**、贈与は贈与額。領収書3万円未満は非課税。"
    return why, ["記載金額", "過少申告+10%", "仲介手数料の領収書"]


@_register("fudosan_shutoku")
def _ex_shutoku(q, correct, cmap):
    why = "不動産取得税は取得時に課税。住宅には控除・軽減税率あり。**相続は非課税**が頻出。"
    return why, ["税率3%/4%", "1,200万円控除", "相続非課税"]


@_register("shakuchi")
def _ex_shakuchi(q, correct, cmap):
    why = "借地借家法は、更新・正当事由・立退料・買取請求、定期借家の特約が中心です。"
    return why, ["更新申込み・拒絶", "正当事由", "借地権の対抗力"]


@_register("nouchi")
def _ex_nouchi(q, correct, cmap):
    why = "農地法は、売買・貸借・転用の**許可要否**と、契約の効力（無効ではない等）が問われます。"
    return why, ["売買許可", "転用・農地法人和"]


@_register("minpo_general")
def _ex_minpo(q, correct, cmap):
    style = _ask_style(q)
    if "背信的" in _stem(q):
        why = "判例の背信的悪意者：知っていた第三者は取得者に対抗できない。登記・引渡しの問題とセットで整理。"
    elif "抵当" in _stem(q) or "配当" in _stem(q):
        why = "抵当権の配当は**順位の先**に従い、売却代金から順に満額配当。順位放棄・譲渡で配分が変わります。"
    elif "意思表示" in _stem(q):
        why = "意思表示の瑕疵（錯誤・詐欺・強迫・虚偽表示）と第三者の保護のバランスがポイントです。"
    elif style == "count" and q.get("subStatements"):
        why = (
            "ア〜エの各記述を条文・判例と照合し、誤っているものの個数を数えます。"
            f"正解は「{cmap.get(correct, '')}」の組合せです。"
        )
    else:
        why = "民法の条文・判例の定義と、事例の事実関係を一つずつ対応させて判断します。"
    return why, ["条文の文言", "判例の要件", "第三者の保護"]


@_register("kenchiku")
def _ex_kenchiku(q, correct, cmap):
    why = "建築基準法は、用途地域ごとの建ぺい率・容積率、前面道路12m未満の制限、耐火・防火が定番です。"
    return why, ["建ぺい・容積", "前面道路", "12m未満の緩和"]


@_register("gyomu_kisei")
def _ex_gyomu(q, correct, cmap):
    why = "47条等の業務規制：誇大広告、手付の貸付・減額による誘引、虚偽説明は禁止。契約締結の不当誘引も違反。"
    return why, ["手付の誘引", "誇大・虚偽広告", "47条の2"]


@_register("baikai")
def _ex_baikai(q, correct, cmap):
    why = "媒介契約は一般・専任・専属専任があり、レインズ登録・有効期間・報酬との関係が問われます。"
    return why, ["専任の登録", "契約期間3ヶ月", "依頼の専属性"]


@_register("37jou_shomen")
def _ex_37jou(q, correct, cmap):
    why = "37条書面は契約時の交付書面（代金・引渡し・瑕疵担保・手付保全等）。35条（重説）と混同しないこと。"
    return why, ["交付義務", "記載事項", "37条の2との違い"]


@_register("teitou_haitou")
def _ex_teitou(q, correct, cmap):
    why = (
        "競売配当：費用控除後、第一順位から順に配当。順位放棄は後順位者の利益のため。"
        "具体金額は毎回変わるため、表を書いて計算する練習が有効です。"
    )
    return why, ["配当の順序", "順位放棄・譲渡", "売却代金の配分"]


def generate_explanation(q: dict, topic_id: str, topic_name: str) -> dict:
    """解説オブジェクトを返す。"""
    correct = q.get("correctAnswer")
    cmap = _choice_map(q)
    style = _ask_style(q)

    if correct == "any":
        return {
            "summary": "本試験年度では、この問題は出題上の特例により**すべての選択肢が正解**として扱われます（法改正・データ訂正等）。",
            "whyCorrect": "試験実施機関の注記に基づき、どの肢を選んでも正解扱いとなりました。",
            "checkPoints": ["試験年度の注記を確認", "法改正後の学習では最新法令で再確認"],
            "wrongHints": [],
        }

    if not correct or correct == "none":
        return {
            "summary": "正解データがない、または「該当なし」形式の問題です。",
            "whyCorrect": "公式PDFの正解番号表・解説書で確認してください。",
            "checkPoints": [topic_name],
            "wrongHints": [],
        }

    explainer = TOPIC_EXPLAINERS.get(topic_id)
    if explainer:
        why, points = explainer(q, correct, cmap)
    else:
        why = f"{topic_name}の出題です。条文の定義と問題文の事実を照合して判断します。"
        points = ["論点ページの法律説明", "試験当日の法令集"]

    correct_text = cmap.get(correct, "")
    why_correct = (
        f"**正解は選択肢{correct}**です。\n\n"
        f"{why}\n\n"
        f"正解肢の内容：「{correct_text[:200]}{'…' if len(correct_text) > 200 else ''}」"
    )

    if style == "count" and q.get("subStatements"):
        why_correct += (
            "\n\n**解き方**：ア〜エをそれぞれ「正しい記述か」判定し、誤りの個数を数えます。"
            "「誤っているものはいくつ」の設問では、正しい記述の数を引いて答えを選びます。"
        )
    elif style == "combo" and q.get("subStatements"):
        why_correct += (
            f"\n\n**解き方**：ア〜エの正誤を整理し、正しいものの組合せが選択肢{correct}と一致するか確認します。"
        )
    elif style == "wrong":
        why_correct += "\n\n**解き方**：「誤っているもの」を選ぶ設問なので、3肢が正しく1肢だけが条文違反、という形が多いです。"
    else:
        why_correct += "\n\n**解き方**：各選択肢を条文・判例の要件リストと照合し、要件をすべて満たす肢だけが正解になります。"

    return {
        "summary": f"{topic_name}に関する問題。正解は選択肢{correct}。",
        "whyCorrect": why_correct,
        "checkPoints": points,
        "wrongHints": _wrong_hints(q, correct) if len(cmap) >= 3 else [],
    }


def explanation_to_html(exp: dict) -> str:
    parts = [f'<p class="exp-summary">{_md(exp["summary"])}</p>']
    parts.append(f'<div class="exp-why"><h4>正解の理由</h4>{_md(exp["whyCorrect"])}</div>')
    if exp.get("checkPoints"):
        items = "".join(f"<li>{_md(p)}</li>" for p in exp["checkPoints"])
        parts.append(f'<div class="exp-points"><h4>確認ポイント</h4><ul>{items}</ul></div>')
    if exp.get("wrongHints"):
        items = "".join(f"<li>{_md(p)}</li>" for p in exp["wrongHints"])
        parts.append(f'<div class="exp-wrong"><h4>他の選択肢を外すコツ</h4><ul>{items}</ul></div>')
    parts.append(
        '<p class="exp-note">※ OCR・自動生成の解説です。'
        "法改正により現在と異なる場合があります。迷ったら公式過去問・法令集で確認してください。</p>"
    )
    return "\n".join(parts)


def _md(s: str) -> str:
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = s.replace("\n\n", "</p><p>")
    s = s.replace("\n", "<br>")
    if not s.startswith("<"):
        s = f"<p>{s}</p>"
    return s
