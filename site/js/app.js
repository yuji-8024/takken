const STORAGE_KEY = "takken-studied-v1";
const ATTEMPTS_KEY = "takken-attempts-v1";

let bank = null;
let studied = loadStudied();
let attempts = loadAttempts();

function loadStudied() {
  try {
    return new Set(JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]"));
  } catch {
    return new Set();
  }
}

function saveStudied() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify([...studied]));
}

function loadAttempts() {
  try {
    return JSON.parse(localStorage.getItem(ATTEMPTS_KEY) || "{}");
  } catch {
    return {};
  }
}

function saveAttempts() {
  localStorage.setItem(ATTEMPTS_KEY, JSON.stringify(attempts));
}

const CHOICE_DIGIT_RE = /(?<![0-9０-９])(?<![条第年])([1-4１-４])/gu;
const UNIT_AFTER = /^[月年日時分秒歳円万㎡％%\d]/;
const STEM_END_RE = /(どれか|どれ|いくつ|一つ|組合せ|掲げ|ものは|ものを|記述のうち)[。．？！\s]*$/;

function zenToInt(s) {
  const map = { "０": 0, "１": 1, "２": 2, "３": 3, "４": 4 };
  return map[s] ?? parseInt(s, 10);
}

function contentStart(raw, afterDigitEnd) {
  let i = afterDigitEnd;
  const skip = " ．.、-ー—'\"＇''「」[]】]";
  while (i < raw.length && skip.includes(raw[i])) i++;
  return i;
}

function isFalsePositive(raw, digitStart, cs) {
  if (cs >= raw.length) return true;
  if (UNIT_AFTER.test(raw.slice(cs))) return true;
  const before = raw.slice(Math.max(0, digitStart - 4), digitStart);
  return /[条第年]$/.test(before);
}

function collectChoiceCandidates(raw) {
  const out = [];
  CHOICE_DIGIT_RE.lastIndex = 0;
  let m;
  while ((m = CHOICE_DIGIT_RE.exec(raw)) !== null) {
    const id = String(zenToInt(m[1]));
    const digitStart = m.index;
    const cs = contentStart(raw, m.index + m[1].length);
    if (isFalsePositive(raw, digitStart, cs)) continue;
    out.push({ id, markerStart: m.index, contentStart: cs });
  }
  return out;
}

function buildChoiceChain(candidates) {
  if (!candidates.length) return [];
  const order = ["1", "2", "3", "4"];
  let startIdx = 0;
  if (candidates[0].id !== "1") {
    const idx = order.findIndex((w) => candidates.some((c) => c.id === w));
    if (idx >= 0) startIdx = idx;
  }
  const chain = [];
  let pos = 0;
  for (const want of order.slice(startIdx)) {
    const pick = candidates.find((c) => c.id === want && c.markerStart >= pos);
    if (!pick) break;
    chain.push(pick);
    pos = pick.markerStart + 1;
  }
  return chain.length >= 2 ? chain : [];
}

function inferStemEnd(raw, firstMarker) {
  const head = raw.slice(0, firstMarker);
  const m = head.match(STEM_END_RE);
  if (m) return m.index + m[0].length;
  const lastPunc = head.search(/[。．？！](?=[^。．？！]*$)/);
  return lastPunc >= 0 ? lastPunc + 1 : firstMarker;
}

function chainToChoices(raw, chain) {
  const choices = [];
  if (chain[0].id !== "1") {
    const stemEnd = inferStemEnd(raw, chain[0].markerStart);
    let c1 = raw.slice(stemEnd, chain[0].markerStart).trim().replace(/^[\]】\s]+/, "");
    if (c1.length >= 4) choices.push({ id: "1", label: "1", text: c1 });
  }
  chain.forEach((node, i) => {
    const end = i + 1 < chain.length ? chain[i + 1].markerStart : raw.length;
    const ctext = raw.slice(node.contentStart, end).trim();
    if (ctext.length >= 2 && !choices.some((c) => c.id === node.id)) {
      choices.push({ id: node.id, label: node.id, text: ctext });
    }
  });
  return choices.sort((a, b) => Number(a.id) - Number(b.id));
}

function extractSubStatements(raw) {
  const subs = [];
  const re = /([アイウエ])[　 ](.+?)(?=\s[アイウエ][　 ]|\s[1-4１-４][　 ]|$)/g;
  let m;
  while ((m = re.exec(raw)) !== null) {
    subs.push({ id: m[1], text: m[2].trim() });
  }
  return subs;
}

/** 原文テキストから設問・選択肢を分割（Python版と同じロジック） */
function parseQuestionText(text) {
  const raw = text.replace(/\u3000/g, " ").replace(/\s+/g, " ").trim();
  if (raw.length < 20) return { stem: raw, choices: [], subStatements: [] };

  const subStatements = extractSubStatements(raw);
  let region = raw;
  if (subStatements.length) {
    const last = subStatements[subStatements.length - 1];
    const pos = raw.lastIndexOf(last.text);
    if (pos >= 0) region = raw.slice(pos + last.text.length);
  }

  let chain = buildChoiceChain(collectChoiceCandidates(region));
  let choices = chainToChoices(region, chain);
  if (choices.length < 2) {
    chain = buildChoiceChain(collectChoiceCandidates(raw));
    choices = chainToChoices(raw, chain);
  }

  let stem = raw;
  if (choices.length >= 2 && chain.length) {
    const cut =
      chain[0].id !== "1" ? inferStemEnd(raw, chain[0].markerStart) : chain[0].markerStart;
    if (subStatements.length) {
      const m1 = raw.indexOf(subStatements[0].id + " ");
      stem = m1 > 0 ? raw.slice(0, m1).trim() : raw.slice(0, cut).trim();
    } else {
      stem = raw.slice(0, cut).trim();
    }
  }
  if (!stem) stem = raw.slice(0, 400);

  return { stem, choices, subStatements };
}

function ensureQuestionParsed(q) {
  if (!q.text) return q;
  const parsed = parseQuestionText(q.text);
  if (parsed.choices.length >= 2) {
    q.stem = parsed.stem;
    q.choices = parsed.choices;
    if (parsed.subStatements.length) q.subStatements = parsed.subStatements;
  }
  return q;
}

function renderQuestionBody(q) {
  q = ensureQuestionParsed({ ...q });
  const hasChoices = q.choices && q.choices.length >= 2;
  const prev = attempts[q.id];

  let subsHtml = "";
  if (q.subStatements && q.subStatements.length) {
    subsHtml = `<div class="q-subs"><p class="q-subs-title">各記述（ア〜エ）</p><ol class="q-subs-list">`;
    q.subStatements.forEach((s) => {
      subsHtml += `<li><span class="sub-id">${escapeHtml(s.id)}</span> ${escapeHtml(s.text)}</li>`;
    });
    subsHtml += `</ol></div>`;
  }

  let choicesHtml = "";
  if (hasChoices) {
    choicesHtml = `<div class="q-choices" role="group" aria-label="選択肢">`;
    q.choices.forEach((c) => {
      let cls = "choice-btn";
      if (prev && prev.selected === c.id) cls += prev.correct ? " selected-correct" : " selected-wrong";
      if (prev && q.correctAnswer && c.id === q.correctAnswer) cls += " is-answer";
      choicesHtml += `<button type="button" class="${cls}" data-choice="${c.id}" data-qid="${q.id}">
        <span class="choice-num">${escapeHtml(c.id)}</span>
        <span class="choice-text">${escapeHtml(c.text)}</span>
      </button>`;
    });
    choicesHtml += `</div>`;
  } else {
    choicesHtml = `<div class="q-raw-fallback"><p class="warn">選択肢を自動分割できませんでした。原文を確認してください。</p><pre class="q-raw">${escapeHtml(q.text)}</pre></div>`;
  }

  let feedback = "";
  const showExplanation = prev && q.explanationHtml;
  const explanationBlock = q.explanationHtml
    ? `<div class="q-explanation${showExplanation ? " visible" : ""}" ${showExplanation ? "" : 'hidden'}>${showExplanation ? q.explanationHtml : "解答後に解説が表示されます"}</div>`
    : "";
  if (prev) {
    if (prev.correct) {
      feedback = `<div class="q-feedback correct">✓ 正解です（正解: ${formatAnswer(q.correctAnswer)}）</div>`;
    } else {
      feedback = `<div class="q-feedback wrong">✗ 不正解です（正解: ${formatAnswer(q.correctAnswer)}）</div>`;
    }
  } else if (!q.correctAnswer && hasChoices) {
    feedback = `<div class="q-feedback neutral">この年度は正解データがありません。公式PDFで確認してください。</div>`;
  }

  return `
    <div class="q-stem">${escapeHtml(q.stem || q.text.slice(0, 300))}</div>
    ${subsHtml}
    ${choicesHtml}
    ${feedback}
    ${explanationBlock}
    <details class="q-original"><summary>原文（OCR）を表示</summary><pre class="q-raw">${escapeHtml(q.text)}</pre></details>
  `;
}

function formatAnswer(a) {
  if (!a) return "—";
  if (a === "none") return "なし（該当肢なし）";
  if (a === "any") return "全選択肢正解（試験上の特例）";
  return `選択肢 ${a}`;
}

function handleChoiceClick(btn) {
  const qid = btn.dataset.qid;
  const selected = btn.dataset.choice;
  let q = bank.topics.flatMap((t) => t.questions).find((x) => x.id === qid);
  if (!q) return;
  q = ensureQuestionParsed({ ...q });

  const card = btn.closest(".question-card");
  const correctAnswer = q.correctAnswer;
  let correct = false;
  if (correctAnswer === "any") correct = true;
  else if (correctAnswer === "none") correct = selected === "none";
  else if (correctAnswer) correct = selected === correctAnswer;

  attempts[qid] = { selected, correct, at: Date.now() };
  saveAttempts();

  card.querySelectorAll(".choice-btn").forEach((b) => {
    b.classList.remove("selected-correct", "selected-wrong", "is-answer");
    if (b.dataset.choice === selected) {
      b.classList.add(correct ? "selected-correct" : "selected-wrong");
    }
    if (correctAnswer && b.dataset.choice === correctAnswer) {
      b.classList.add("is-answer");
    }
    if (correctAnswer === "any") {
      b.classList.add("is-answer");
    }
  });

  let fb = card.querySelector(".q-feedback");
  if (!fb) {
    fb = document.createElement("div");
    card.querySelector(".q-body").appendChild(fb);
  }
  fb.className = `q-feedback ${correct ? "correct" : "wrong"}`;
  fb.textContent = correct
    ? `✓ 正解です（正解: ${formatAnswer(correctAnswer)}）`
    : `✗ 不正解です（正解: ${formatAnswer(correctAnswer)}）`;

  if (!correctAnswer) {
    fb.className = "q-feedback neutral";
    fb.textContent = "正解データがありません。公式PDFで確認してください。";
  }

  showExplanationPanel(card, q);
}

function showExplanationPanel(card, q) {
  if (!q.explanationHtml) return;
  let panel = card.querySelector(".q-explanation");
  if (!panel) {
    panel = document.createElement("div");
    panel.className = "q-explanation";
    const body = card.querySelector(".q-body");
    const details = body.querySelector(".q-original");
    body.insertBefore(panel, details);
  }
  panel.innerHTML = q.explanationHtml;
  panel.hidden = false;
  panel.classList.add("visible");
  panel.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

function escapeHtml(s) {
  const d = document.createElement("div");
  d.textContent = s;
  return d.innerHTML;
}

function tierColor(tier, meta) {
  return meta.tierInfo[tier]?.color || "#333";
}

function parseRoute() {
  const hash = location.hash.slice(1) || "/";
  const parts = hash.split("/").filter(Boolean);
  if (parts.length === 0) return { view: "home" };
  if (parts[0] === "tier" && parts[1]) return { view: "tier", tier: parts[1] };
  if (parts[0] === "topic" && parts[1]) return { view: "topic", topicId: parts[1] };
  if (parts[0] === "formulas") return { view: "formulas" };
  if (parts[0] === "search" && parts[1])
    return { view: "search", q: decodeURIComponent(parts[1]) };
  return { view: "home" };
}

function navigate(path) {
  location.hash = path;
}

async function loadBank() {
  const res = await fetch("/data/bank.json");
  if (!res.ok) throw new Error("データの読み込みに失敗しました");
  return res.json();
}

function renderSidebar(activeTopicId = null, filterTier = null) {
  const el = document.getElementById("sidebarContent");
  const { meta, topics } = bank;
  const tiers = ["A", "B", "C"];
  let html = "";

  for (const tier of tiers) {
    if (filterTier && filterTier !== tier) continue;
    const info = meta.tierInfo[tier];
    const list = topics.filter((t) => t.tier === tier);
    if (!list.length) continue;
    html += `<div class="sidebar-section">
      <h3><span class="tier-badge" style="background:${info.color}"></span>${info.label}</h3>`;
    for (const t of list) {
      const active = t.id === activeTopicId ? " active" : "";
      html += `<a href="#/topic/${t.id}" class="topic-link${active}" data-topic="${t.id}">
        ${escapeHtml(t.name)}<span class="count">${t.questionCount}</span>
      </a>`;
    }
    html += `</div>`;
  }
  el.innerHTML = html;
}

function renderHome() {
  const { meta, topics, formulas } = bank;
  const byTier = { A: 0, B: 0, C: 0 };
  topics.forEach((t) => {
    byTier[t.tier] += t.questionCount;
  });

  let cards = "";
  for (const tier of ["A", "B", "C"]) {
    const info = meta.tierInfo[tier];
    const count = topics.filter((t) => t.tier === tier).length;
    cards += `<button type="button" class="tier-card" data-goto-tier="${tier}">
      <h2 style="color:${info.color}">${info.label}：${info.title}</h2>
      <div class="sub">${info.subtitle}</div>
      <div class="stat">${byTier[tier]}問</div>
      <div class="sub">${count}論点 · ${info.desc}</div>
    </button>`;
  }

  let formulaPreview = "";
  for (const f of formulas.slice(0, 3)) {
    formulaPreview += `<div class="formula-card"><h3>${escapeHtml(f.title)}</h3><ul>`;
    f.items.forEach((i) => {
      formulaPreview += `<li>${escapeHtml(i)}</li>`;
    });
    formulaPreview += `</ul></div>`;
  }

  return `
    <div class="hero">
      <h1>${escapeHtml(meta.title)}</h1>
      <p>${escapeHtml(meta.source)} · 全${meta.totalQuestions}問 · 合格目安 ${escapeHtml(meta.passLine)}</p>
    </div>
    <div class="tier-cards">${cards}</div>
    <div class="panel">
      <h2>使い方</h2>
      <ul>
        <li><strong>第I部</strong>：ほぼ毎年出る論点。全問1回以上・正解率90%を目標</li>
        <li><strong>第II部</strong>：合格点安定。第I部の後に弱点だけ反復</li>
        <li><strong>第III部</strong>：満点狙い。計算・判例・難問</li>
      </ul>
      <p>チェックボックスで学習済みを記録（ブラウザに保存）。</p>
    </div>
    <div class="panel">
      <h2>公式早見（抜粋）</h2>
      <div class="formula-grid">${formulaPreview}</div>
      <p><a href="#/formulas">→ 公式一覧を見る</a></p>
    </div>
  `;
}

function renderTier(tier) {
  const info = bank.meta.tierInfo[tier];
  if (!info) return renderHome();
  const list = bank.topics.filter((t) => t.tier === tier);
  const totalQ = list.reduce((s, t) => s + t.questionCount, 0);

  let items = "";
  for (const t of list) {
    const done = t.questions.filter((q) => studied.has(q.id)).length;
    const pct = t.questionCount ? Math.round((done / t.questionCount) * 100) : 0;
    items += `<a href="#/topic/${t.id}" class="topic-link" style="display:block;margin-bottom:0.5rem;padding:1rem;background:var(--surface);border-radius:8px;border:1px solid var(--border);text-decoration:none;color:inherit">
      <strong>${escapeHtml(t.name)}</strong>
      <span style="float:right;color:var(--muted)">${t.questionCount}問 · 済${done} (${pct}%)</span>
      <div class="progress-bar"><div class="progress-fill" style="width:${pct}%"></div></div>
    </a>`;
  }

  return `
    <div class="topic-header">
      <span class="tier-tag" style="background:${info.color}">${info.label}</span>
      <h1>${escapeHtml(info.title)}</h1>
      <p class="meta">${escapeHtml(info.desc)} · ${list.length}論点 · ${totalQ}問</p>
    </div>
    ${items}
  `;
}

function renderTopic(topicId) {
  const topic = bank.topics.find((t) => t.id === topicId);
  if (!topic) return `<div class="empty-state">論点が見つかりません</div>`;

  const info = bank.meta.tierInfo[topic.tier];
  const done = topic.questions.filter((q) => studied.has(q.id)).length;
  const pct = topic.questionCount
    ? Math.round((done / topic.questionCount) * 100)
    : 0;

  const exams = [...new Set(topic.questions.map((q) => q.exam))];

  let questionsHtml = "";
  topic.questions.forEach((q, idx) => {
    const isDone = studied.has(q.id);
    const openByDefault = idx < 3 ? " open" : "";
    questionsHtml += `
      <div class="question-card${isDone ? " done" : ""}${openByDefault}" data-qid="${q.id}" data-exam="${q.exam}">
        <div class="q-head">
          <input type="checkbox" ${isDone ? "checked" : ""} data-check="${q.id}" aria-label="学習済み" />
          <span class="q-title">【${idx + 1}】${escapeHtml(q.examLabel)} 問${q.qnum}</span>
          <span class="q-toggle"></span>
        </div>
        <div class="q-body">${renderQuestionBody(q)}</div>
      </div>`;
  });

  return `
    <div class="topic-header">
      <span class="tier-tag" style="background:${info.color}">${info.label}</span>
      <h1>${escapeHtml(topic.name)}</h1>
      <p class="meta">${topic.questionCount}問 · 学習済み ${done}/${topic.questionCount} (${pct}%)</p>
      <div class="progress-bar"><div class="progress-fill" style="width:${pct}%"></div></div>
    </div>
    <div class="panel">
      <h2>法律・ルールの説明</h2>
      <div>${topic.descriptionHtml}</div>
    </div>
    <div class="panel">
      <h2>勉強のTips</h2>
      <div>${topic.tipsHtml}</div>
    </div>
    <div class="panel">
      <h2>過去問一覧</h2>
      <p class="quiz-hint">選択肢をタップすると正誤と<strong>正解の理由（解説）</strong>が表示されます（何度でも選び直せます）。OCRの誤字は原文表示で確認してください。</p>
      <div class="question-filters">
        <label>年度 <select id="examFilter">
          <option value="">すべて</option>
          ${exams.map((e) => `<option value="${e}">${escapeHtml(bank.meta.examLabels[e] || e)}</option>`).join("")}
        </select></label>
      </div>
      <div class="question-list" id="questionList">${questionsHtml}</div>
    </div>
  `;
}

function renderFormulas() {
  let html = `<div class="topic-header"><h1>公式・数値早見表</h1>
    <p class="meta">試験当日は最新の法令集で税率・面積を必ず確認</p></div>`;
  for (const f of bank.formulas) {
    html += `<div class="formula-card"><h3>${escapeHtml(f.title)}</h3><ul>`;
    f.items.forEach((i) => {
      html += `<li>${escapeHtml(i)}</li>`;
    });
    html += `</ul></div>`;
  }
  return html;
}

function renderSearch(query) {
  const q = query.toLowerCase().trim();
  if (!q) return renderHome();

  const results = [];
  for (const topic of bank.topics) {
    for (const question of topic.questions) {
      if (
        question.text.toLowerCase().includes(q) ||
        topic.name.toLowerCase().includes(q) ||
        question.examLabel.includes(q)
      ) {
        results.push({ topic, question });
      }
    }
  }

  let html = `<div class="topic-header"><h1>検索結果</h1>
    <p class="meta">「${escapeHtml(query)}」— ${results.length}件</p></div>`;

  if (!results.length) {
    html += `<div class="empty-state">該当する問題がありません</div>`;
    return html;
  }

  results.slice(0, 80).forEach(({ topic, question }) => {
    const snippet = question.text.slice(0, 200) + (question.text.length > 200 ? "…" : "");
    html += `<a href="#/topic/${topic.id}" class="topic-link" style="display:block;margin-bottom:0.5rem;padding:1rem;background:var(--surface);border-radius:8px;border:1px solid var(--border)">
      <strong>${escapeHtml(topic.name)}</strong> — ${escapeHtml(question.examLabel)} 問${question.qnum}
      <div style="font-size:0.85rem;color:var(--muted);margin-top:0.35rem">${escapeHtml(snippet)}</div>
    </a>`;
  });
  if (results.length > 80) {
    html += `<p class="meta">他 ${results.length - 80} 件（論点ページで全文を確認）</p>`;
  }
  return html;
}

function bindMainEvents(route) {
  document.querySelectorAll("[data-goto-tier]").forEach((btn) => {
    btn.addEventListener("click", () => navigate(`/tier/${btn.dataset.gotoTier}`));
  });

  document.querySelectorAll(".q-head").forEach((head) => {
    head.addEventListener("click", (e) => {
      if (e.target.type === "checkbox") return;
      if (e.target.closest(".choice-btn")) return;
      head.closest(".question-card").classList.toggle("open");
    });
  });

  document.querySelectorAll(".choice-btn").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      handleChoiceClick(btn);
    });
  });

  document.querySelectorAll("[data-check]").forEach((cb) => {
    cb.addEventListener("change", () => {
      const id = cb.dataset.check;
      if (cb.checked) studied.add(id);
      else studied.delete(id);
      saveStudied();
      const card = cb.closest(".question-card");
      card.classList.toggle("done", cb.checked);
    });
  });

  const examFilter = document.getElementById("examFilter");
  if (examFilter && route.view === "topic") {
    examFilter.addEventListener("change", () => {
      const val = examFilter.value;
      document.querySelectorAll(".question-card").forEach((card) => {
        card.classList.toggle("hidden", val && card.dataset.exam !== val);
      });
    });
  }
}

function render() {
  const route = parseRoute();
  const main = document.getElementById("main");
  if (!bank) return;

  let content = "";
  let sidebarTier = null;
  let activeTopic = null;

  switch (route.view) {
    case "tier":
      content = renderTier(route.tier);
      sidebarTier = route.tier;
      break;
    case "topic":
      content = renderTopic(route.topicId);
      activeTopic = route.topicId;
      break;
    case "formulas":
      content = renderFormulas();
      break;
    case "search":
      content = renderSearch(route.q);
      break;
    default:
      content = renderHome();
  }

  main.innerHTML = content;
  renderSidebar(activeTopic, sidebarTier);
  bindMainEvents(route);

  document.querySelectorAll(".header-nav a, .logo").forEach((a) => {
    a.classList.toggle("active", a.dataset.nav === route.view || (route.view === "home" && a.dataset.nav === "home"));
  });
}

function setupMobileMenu() {
  const btn = document.getElementById("menuBtn");
  const sidebar = document.getElementById("sidebar");
  const overlay = document.getElementById("overlay");
  const close = () => {
    sidebar.classList.remove("open");
    overlay.classList.remove("show");
  };
  btn.addEventListener("click", () => {
    sidebar.classList.toggle("open");
    overlay.classList.toggle("show");
  });
  overlay.addEventListener("click", close);
  document.getElementById("sidebar").addEventListener("click", (e) => {
    if (e.target.closest(".topic-link")) close();
  });
}

function setupSearch() {
  const input = document.getElementById("globalSearch");
  let timer;
  input.addEventListener("input", () => {
    clearTimeout(timer);
    timer = setTimeout(() => {
      const v = input.value.trim();
      if (v.length >= 2) navigate(`/search/${encodeURIComponent(v)}`);
      else if (parseRoute().view === "search") navigate("/");
    }, 350);
  });
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      const v = input.value.trim();
      if (v) navigate(`/search/${encodeURIComponent(v)}`);
    }
  });
}

async function init() {
  setupMobileMenu();
  setupSearch();
  window.addEventListener("hashchange", render);

  try {
    bank = await loadBank();
    document.getElementById("loading")?.remove();
    render();
  } catch (err) {
    document.getElementById("main").innerHTML = `<div class="empty-state">
      <p>データを読み込めませんでした。</p>
      <p>${escapeHtml(err.message)}</p>
      <p>Netlifyデプロイ前に <code>python3 scripts/build_site_data.py</code> を実行してください。</p>
    </div>`;
  }
}

init();
