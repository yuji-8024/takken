const STORAGE_KEY = "takken-studied-v1";

let bank = null;
let studied = loadStudied();

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
    questionsHtml += `
      <div class="question-card ${isDone ? "done" : ""}" data-qid="${q.id}">
        <div class="q-head">
          <input type="checkbox" ${isDone ? "checked" : ""} data-check="${q.id}" aria-label="学習済み" />
          <span class="q-title">【${idx + 1}】${escapeHtml(q.examLabel)} 問${q.qnum}</span>
          <span class="q-toggle"></span>
        </div>
        <div class="q-body">${escapeHtml(q.text)}</div>
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
      head.closest(".question-card").classList.toggle("open");
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
        const qid = card.dataset.qid;
        const q = bank.topics
          .flatMap((t) => t.questions)
          .find((x) => x.id === qid);
        card.classList.toggle("hidden", val && q?.exam !== val);
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
