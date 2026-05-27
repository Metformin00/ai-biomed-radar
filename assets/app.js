const state = {
  articles: [],
  filtered: [],
  favorites: new Set(JSON.parse(localStorage.getItem("favorites") || "[]"))
};

const $ = (id) => document.getElementById(id);

const els = {
  search: $("searchInput"),
  journal: $("journalFilter"),
  tag: $("tagFilter"),
  date: $("dateFilter"),
  onlyFavorites: $("onlyFavorites"),
  reset: $("resetBtn"),
  sort: $("sortMode"),
  articles: $("articles"),
  empty: $("emptyState"),
  totalCount: $("totalCount"),
  journalCount: $("journalCount"),
  tagCount: $("tagCount"),
  latestDate: $("latestDate"),
  tagCloud: $("tagCloud"),
  trendBars: $("trendBars"),
  trendCaption: $("trendCaption"),
  themeToggle: $("themeToggle")
};

function normalizeDate(value) {
  if (!value) return null;
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? null : d;
}

function unique(arr) {
  return [...new Set(arr.filter(Boolean))];
}

function getAllTags(article) {
  return unique([...(article.ai_tags || []), ...(article.bio_tags || []), ...(article.disease_tags || []), ...(article.tags || [])]);
}

function saveFavorites() {
  localStorage.setItem("favorites", JSON.stringify([...state.favorites]));
}

function articleId(article) {
  return article.doi || article.url || article.title;
}

async function loadData() {
  try {
    const res = await fetch("data/articles.json", { cache: "no-store" });
    const data = await res.json();
    state.articles = Array.isArray(data.articles) ? data.articles : data;
  } catch (error) {
    console.error(error);
    state.articles = [];
  }

  buildFilters();
  applyFilters();
}

function buildFilters() {
  const journals = unique(state.articles.map(a => a.journal || a.source_name)).sort();
  const tags = unique(state.articles.flatMap(getAllTags)).sort();

  for (const journal of journals) {
    const opt = document.createElement("option");
    opt.value = journal;
    opt.textContent = journal;
    els.journal.appendChild(opt);
  }

  for (const tag of tags) {
    const opt = document.createElement("option");
    opt.value = tag;
    opt.textContent = tag;
    els.tag.appendChild(opt);
  }

  renderTagCloud(tags);
}

function renderTagCloud(tags) {
  const counts = {};
  for (const a of state.articles) {
    for (const t of getAllTags(a)) counts[t] = (counts[t] || 0) + 1;
  }

  els.tagCloud.innerHTML = "";
  Object.entries(counts)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 28)
    .forEach(([tag, count]) => {
      const btn = document.createElement("button");
      btn.className = "chip";
      btn.textContent = `${tag} ${count}`;
      btn.addEventListener("click", () => {
        els.tag.value = tag;
        applyFilters();
      });
      els.tagCloud.appendChild(btn);
    });
}

function applyFilters() {
  const q = els.search.value.trim().toLowerCase();
  const journal = els.journal.value;
  const tag = els.tag.value;
  const days = els.date.value;
  const onlyFav = els.onlyFavorites.checked;
  const cutoff = days === "all" ? null : new Date(Date.now() - Number(days) * 24 * 3600 * 1000);

  let list = state.articles.filter(a => {
    const text = [
      a.title, a.title_zh, a.abstract, a.abstract_zh,
      a.journal, a.source_name, ...(getAllTags(a))
    ].join(" ").toLowerCase();

    if (q && !text.includes(q)) return false;
    if (journal && (a.journal || a.source_name) !== journal) return false;
    if (tag && !getAllTags(a).includes(tag)) return false;
    if (onlyFav && !state.favorites.has(articleId(a))) return false;
    if (cutoff) {
      const d = normalizeDate(a.published_date || a.updated_date);
      if (!d || d < cutoff) return false;
    }
    return true;
  });

  const sortMode = els.sort.value;
  list.sort((a, b) => {
    if (sortMode === "date_asc") return new Date(a.published_date || 0) - new Date(b.published_date || 0);
    if (sortMode === "title_asc") return (a.title || "").localeCompare(b.title || "");
    return new Date(b.published_date || 0) - new Date(a.published_date || 0);
  });

  state.filtered = list;
  renderStats();
  renderTrends();
  renderArticles();
}

function renderStats() {
  const journals = unique(state.filtered.map(a => a.journal || a.source_name));
  const tags = unique(state.filtered.flatMap(getAllTags));
  const dates = state.filtered.map(a => normalizeDate(a.published_date)).filter(Boolean).sort((a, b) => b - a);

  els.totalCount.textContent = state.filtered.length;
  els.journalCount.textContent = journals.length;
  els.tagCount.textContent = tags.length;
  els.latestDate.textContent = dates[0] ? dates[0].toISOString().slice(0, 10) : "—";
}

function renderTrends() {
  const counts = {};
  for (const a of state.filtered) {
    for (const t of getAllTags(a)) counts[t] = (counts[t] || 0) + 1;
  }
  const rows = Object.entries(counts).sort((a, b) => b[1] - a[1]).slice(0, 12);
  const max = rows.length ? rows[0][1] : 1;
  els.trendCaption.textContent = rows.length ? "按当前筛选结果统计" : "";
  els.trendBars.innerHTML = "";

  for (const [tag, count] of rows) {
    const row = document.createElement("div");
    row.className = "trend-row";
    row.innerHTML = `
      <div class="trend-label" title="${tag}">${tag}</div>
      <div class="trend-track"><div class="trend-fill" style="width:${Math.max(4, count / max * 100)}%"></div></div>
      <div>${count}</div>
    `;
    els.trendBars.appendChild(row);
  }
}

function renderArticles() {
  els.articles.innerHTML = "";
  els.empty.style.display = state.filtered.length ? "none" : "block";

  for (const a of state.filtered) {
    const id = articleId(a);
    const tags = getAllTags(a);
    const card = document.createElement("article");
    card.className = "article-card";
    card.innerHTML = `
      <div class="article-meta">
        <span>${a.published_date || "未知日期"}</span>
        <span>·</span>
        <span>${a.journal || a.source_name || "Unknown source"}</span>
        ${a.is_preprint ? "<span>· Preprint</span>" : ""}
        <button class="favorite ${state.favorites.has(id) ? "active" : ""}" title="收藏">★</button>
      </div>
      <h3 class="article-title"><a href="${a.url || "#"}" target="_blank" rel="noreferrer">${escapeHtml(a.title || "Untitled")}</a></h3>
      ${a.title_zh ? `<p class="article-title-zh">${escapeHtml(a.title_zh)}</p>` : ""}
      <p class="abstract">${escapeHtml(shorten(a.abstract_zh || a.abstract || "", 520))}</p>
      <div class="tags">${tags.map(t => `<button class="tag" data-tag="${escapeAttr(t)}">${escapeHtml(t)}</button>`).join("")}</div>
    `;

    card.querySelector(".favorite").addEventListener("click", (e) => {
      e.preventDefault();
      if (state.favorites.has(id)) state.favorites.delete(id);
      else state.favorites.add(id);
      saveFavorites();
      applyFilters();
    });

    card.querySelectorAll("[data-tag]").forEach(btn => {
      btn.addEventListener("click", () => {
        els.tag.value = btn.dataset.tag;
        applyFilters();
      });
    });

    els.articles.appendChild(card);
  }
}

function shorten(text, n) {
  if (!text) return "暂无摘要。";
  return text.length > n ? text.slice(0, n) + "…" : text;
}

function escapeHtml(text) {
  return String(text).replace(/[&<>"']/g, m => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;"
  }[m]));
}

function escapeAttr(text) {
  return escapeHtml(text).replace(/"/g, "&quot;");
}

[els.search, els.journal, els.tag, els.date, els.onlyFavorites, els.sort].forEach(el => {
  el.addEventListener("input", applyFilters);
  el.addEventListener("change", applyFilters);
});

els.reset.addEventListener("click", () => {
  els.search.value = "";
  els.journal.value = "";
  els.tag.value = "";
  els.date.value = "30";
  els.onlyFavorites.checked = false;
  els.sort.value = "date_desc";
  applyFilters();
});

els.themeToggle.addEventListener("click", () => {
  document.body.classList.toggle("dark");
  localStorage.setItem("theme", document.body.classList.contains("dark") ? "dark" : "light");
});

if (localStorage.getItem("theme") === "dark") {
  document.body.classList.add("dark");
}

loadData();
