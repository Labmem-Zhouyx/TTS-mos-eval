/* MOS Evaluation single-page frontend. */
(() => {
  const STORAGE_KEY = "mos_eval_session";
  const RATING_VALUES = [1, 2, 3, 4, 5];
  const CMOS_VALUES = [-3, -2, -1, 0, 1, 2, 3];

  const state = {
    lang: "zh",
    nickname: "",
    sessionId: null,
    panels: [], // raw from /api/panels
    // ratings: panelName -> sampleId -> { scores: { system -> { dim -> value } }, abx_choice, notes }
    ratings: {},
    panelStatus: {}, // panelName -> 'draft' | 'submitted'
    view: { name: "start", panelName: null, sampleIdx: 0 },
    lastSavedAt: null,
    startupSeed: null,
  };

  const app = document.getElementById("app");
  const langToggle = document.getElementById("lang-toggle");
  const raterBadge = document.getElementById("rater-badge");

  // ------------------------------------------------------------------ //
  // utilities                                                          //
  // ------------------------------------------------------------------ //

  function t(key, ...args) {
    const dict = window.I18N[state.lang] || window.I18N.zh;
    const value = dict[key];
    if (typeof value === "function") return value(...args);
    if (value !== undefined) return value;
    const fallback = window.I18N.zh[key];
    if (typeof fallback === "function") return fallback(...args);
    return fallback || key;
  }

  function el(tag, attrs = {}, ...children) {
    const e = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs || {})) {
      if (v === null || v === undefined) continue;
      if (k === "class") e.className = v;
      else if (k === "html") e.innerHTML = v;
      else if (k.startsWith("on") && typeof v === "function")
        e.addEventListener(k.slice(2).toLowerCase(), v);
      else if (k === "dataset") {
        for (const [dk, dv] of Object.entries(v)) e.dataset[dk] = dv;
      } else e.setAttribute(k, v);
    }
    for (const child of children.flat()) {
      if (child === null || child === undefined || child === false) continue;
      if (typeof child === "string" || typeof child === "number")
        e.appendChild(document.createTextNode(String(child)));
      else e.appendChild(child);
    }
    return e;
  }

  function hashString(str) {
    let h = 2166136261;
    for (let i = 0; i < str.length; i++) {
      h ^= str.charCodeAt(i);
      h = Math.imul(h, 16777619);
    }
    return h >>> 0;
  }

  function seededRandom(seed) {
    let t = seed >>> 0;
    return () => {
      t += 0x6d2b79f5;
      let x = t;
      x = Math.imul(x ^ (x >>> 15), x | 1);
      x ^= x + Math.imul(x ^ (x >>> 7), x | 61);
      return ((x ^ (x >>> 14)) >>> 0) / 4294967296;
    };
  }

  function seededShuffle(arr, seedKey) {
    const a = arr.slice();
    const rand = seededRandom(hashString(seedKey));
    for (let i = a.length - 1; i > 0; i--) {
      const j = Math.floor(rand() * (i + 1));
      [a[i], a[j]] = [a[j], a[i]];
    }
    return a;
  }

  function pickLang(obj) {
    if (!obj) return "";
    if (typeof obj === "string") return obj;
    return obj[state.lang] || obj.zh || obj.en || Object.values(obj)[0] || "";
  }

  function formatSampleLanguage(code) {
    if (!code) return "";
    const normalized = String(code).trim().toLowerCase();
    const names = {
      zh: { zh: "中文", en: "Chinese" },
      en: { zh: "英语", en: "English" },
      de: { zh: "德语", en: "German" },
      fr: { zh: "法语", en: "French" },
      es: { zh: "西班牙语", en: "Spanish" },
      ru: { zh: "俄语", en: "Russian" },
      ja: { zh: "日语", en: "Japanese" },
      ko: { zh: "韩语", en: "Korean" },
    };
    const label = names[normalized];
    if (label) return `${label[state.lang] || label.zh} (${normalized})`;
    return normalized.toUpperCase();
  }

  function fmtTime(d = new Date()) {
    const pad = (n) => String(n).padStart(2, "0");
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
  }

  // ------------------------------------------------------------------ //
  // persistence                                                        //
  // ------------------------------------------------------------------ //

  function persistLocal() {
    try {
      localStorage.setItem(
        STORAGE_KEY,
        JSON.stringify({
          lang: state.lang,
          nickname: state.nickname,
          sessionId: state.sessionId,
          ratings: state.ratings,
          panelStatus: state.panelStatus,
          startupSeed: state.startupSeed,
          view: state.view,
        }),
      );
    } catch (_) {
      /* ignore */
    }
  }

  function restoreLocal() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (!raw) return false;
      const obj = JSON.parse(raw);
      if (!obj || !obj.sessionId) return false;
      state.lang = obj.lang || state.lang;
      state.nickname = obj.nickname || "";
      state.sessionId = obj.sessionId;
      state.ratings = obj.ratings || {};
      state.panelStatus = obj.panelStatus || {};
      state.startupSeed = obj.startupSeed || null;
      state.view = obj.view || state.view;
      return true;
    } catch (_) {
      return false;
    }
  }

  function clearLocal() {
    try {
      localStorage.removeItem(STORAGE_KEY);
    } catch (_) {}
  }

  function resetToStart(clearStorage = false) {
    if (clearStorage) clearLocal();
    state.sessionId = null;
    state.ratings = {};
    state.panelStatus = {};
    state.panels = [];
    state.startupSeed = null;
    state.lastSavedAt = null;
    state.view = { name: "start", panelName: null, sampleIdx: 0 };
  }

  // ------------------------------------------------------------------ //
  // network                                                            //
  // ------------------------------------------------------------------ //

  async function api(path, options = {}) {
    const res = await fetch(path, {
      cache: "no-store",
      headers: { "Content-Type": "application/json" },
      ...options,
    });
    if (!res.ok) {
      let detail = res.statusText;
      try {
        const j = await res.json();
        detail = j.detail || detail;
      } catch (_) {}
      throw new Error(detail);
    }
    return res.json();
  }

  async function ensureSessionValid() {
    if (!state.sessionId) return false;
    await api(`/api/session/${encodeURIComponent(state.sessionId)}`);
    return true;
  }

  function buildPanelSubmission(panelName, status) {
    const panel = state.panels.find((p) => p.name === panelName);
    if (!panel) return null;
    const samples = [];
    const panelRatings = state.ratings[panelName] || {};
    for (const sample of panel.samples) {
      const sr = panelRatings[sample.sample_id];
      if (!sr) continue;
      if (panel.type === "abx") {
        if (sr.abx_choice !== undefined && sr.abx_choice !== null) {
          samples.push({
            sample_id: sample.sample_id,
            ratings: [],
            abx_choice: sr.abx_choice,
            notes: sr.notes || null,
          });
        }
        continue;
      }
      const rows = [];
      const scores = sr.scores || {};
      for (const sys of sample.systems) {
        const dims = scores[sys];
        if (!dims) continue;
        const cleaned = {};
        let any = false;
        for (const [k, v] of Object.entries(dims)) {
          if (v !== null && v !== undefined && v !== "") {
            cleaned[k] = v;
            any = true;
          }
        }
        if (any) rows.push({ system: sys, scores: cleaned });
      }
      if (rows.length) {
        samples.push({
          sample_id: sample.sample_id,
          ratings: rows,
          abx_choice: null,
          notes: sr.notes || null,
        });
      }
    }
    return { panel: panelName, samples, status };
  }

  async function syncSession(panelNames = null, final = false) {
    if (!state.sessionId) return;
    const panelsToSend = (panelNames || Object.keys(state.ratings))
      .map((name) => {
        const status = state.panelStatus[name] || "draft";
        return buildPanelSubmission(name, status);
      })
      .filter(Boolean);
    if (!panelsToSend.length && !final) return;
    try {
      await api("/api/session/update", {
        method: "POST",
        body: JSON.stringify({
          session_id: state.sessionId,
          nickname: state.nickname,
          language: state.lang,
          panels: panelsToSend,
          final,
        }),
      });
    } catch (e) {
      if (e && typeof e.message === "string" && e.message.includes("session not found")) {
        resetToStart(true);
        render();
        throw new Error(t("error_session"));
      }
      throw e;
    }
    state.lastSavedAt = fmtTime();
    persistLocal();
  }

  // ------------------------------------------------------------------ //
  // panel / sample helpers                                             //
  // ------------------------------------------------------------------ //

  function panelDone(panelName) {
    return state.panelStatus[panelName] === "submitted";
  }

  function ratingsForSample(panelName, sampleId) {
    const p = state.ratings[panelName] || (state.ratings[panelName] = {});
    if (!p[sampleId]) p[sampleId] = { scores: {}, abx_choice: null };
    return p[sampleId];
  }

  function dimensionsComplete(panel, sample) {
    if (panel.type === "abx") {
      const r = ratingsForSample(panel.name, sample.sample_id);
      return r.abx_choice !== null && r.abx_choice !== undefined;
    }
    const r = ratingsForSample(panel.name, sample.sample_id).scores;
    for (const sys of sample.systems) {
      const dims = r[sys] || {};
      for (const dim of panel.dimensions) {
        const v = dims[dim.key];
        if (v === null || v === undefined || v === "") return false;
      }
    }
    return true;
  }

  function panelComplete(panel) {
    return panel.samples.every((s) => dimensionsComplete(panel, s));
  }

  function panelProgress(panel) {
    const total = panel.samples.length;
    const done = panel.samples.filter((s) => dimensionsComplete(panel, s)).length;
    return { done, total };
  }

  function collectMissingItems(panel = null) {
    const panels = panel ? [panel] : state.panels;
    const missing = [];
    for (const currentPanel of panels) {
      for (let sampleIdx = 0; sampleIdx < currentPanel.samples.length; sampleIdx++) {
        const sample = currentPanel.samples[sampleIdx];
        if (currentPanel.type === "abx") {
          const r = ratingsForSample(currentPanel.name, sample.sample_id);
          if (r.abx_choice === null || r.abx_choice === undefined) {
            missing.push({
              panelName: currentPanel.name,
              panelTitle: pickLang(currentPanel.title),
              sampleId: sample.sample_id,
              sampleIdx,
              type: "abx",
            });
          }
          continue;
        }
        const scores = ratingsForSample(currentPanel.name, sample.sample_id).scores;
        for (const sys of sample.systems) {
          const dims = scores[sys] || {};
          for (const dim of currentPanel.dimensions) {
            const value = dims[dim.key];
            if (value === null || value === undefined || value === "") {
              missing.push({
                panelName: currentPanel.name,
                panelTitle: pickLang(currentPanel.title),
                sampleId: sample.sample_id,
                sampleIdx,
                system: sys,
                dimName: pickLang(dim.name),
                type: "mos",
              });
            }
          }
        }
      }
    }
    return missing;
  }

  function formatMissingItems(missing, limit = 12) {
    const lines = [t("missing_items_title", missing.length)];
    for (const item of missing.slice(0, limit)) {
      if (item.type === "abx") {
        lines.push(t("missing_item_abx", item.panelTitle, item.sampleId));
      } else {
        lines.push(
          t("missing_item_mos", item.panelTitle, item.sampleId, item.system, item.dimName),
        );
      }
    }
    if (missing.length > limit) {
      lines.push(t("missing_more", missing.length - limit));
    }
    return lines.join("\n");
  }

  function jumpToMissingItem(item) {
    if (!item) return;
    state.view = {
      name: "panel",
      panelName: item.panelName,
      sampleIdx: item.sampleIdx,
    };
    persistLocal();
    render();
  }

  function handleMissingItems(missing) {
    if (!missing.length) return false;
    alert(formatMissingItems(missing));
    if (confirm(t("missing_jump_confirm"))) {
      jumpToMissingItem(missing[0]);
    }
    return true;
  }

  function orderedSystems(panel, sample) {
    const seed = state.startupSeed || "default";
    return seededShuffle(
      sample.systems,
      `systems:${seed}:${panel.name}:${sample.sample_id}`,
    );
  }

  // ------------------------------------------------------------------ //
  // rendering                                                          //
  // ------------------------------------------------------------------ //

  function renderTop() {
    document.documentElement.lang = state.lang === "zh" ? "zh-CN" : "en";
    for (const node of document.querySelectorAll("[data-i18n]")) {
      node.textContent = t(node.dataset.i18n);
    }
    if (state.nickname) {
      raterBadge.hidden = false;
      raterBadge.textContent = `@${state.nickname}`;
    } else {
      raterBadge.hidden = true;
    }
  }

  function render() {
    renderTop();
    app.innerHTML = "";
    const view = state.view;
    if (view.name === "start") return renderStart();
    if (view.name === "panels") return renderPanelList();
    if (view.name === "panel") return renderPanel();
    if (view.name === "all_done") return renderAllDone();
  }

  function renderStart() {
    const nickname = el("input", {
      type: "text",
      id: "nickname",
      placeholder: t("nickname_placeholder"),
      value: state.nickname || "",
    });
    const notes = el("textarea", {
      id: "notes",
      placeholder: t("notes_placeholder"),
      rows: "2",
    });
    const langSelect = el(
      "select",
      { id: "language" },
      el("option", { value: "zh" }, "中文"),
      el("option", { value: "en" }, "English"),
    );
    langSelect.value = state.lang;

    const status = el("div", { class: "status-line" });
    const submit = el(
      "button",
      {
        class: "btn",
        type: "button",
        onclick: async () => {
          const nick = nickname.value.trim();
          if (!nick) {
            status.textContent = t("nickname");
            status.className = "status-line warn";
            return;
          }
          state.lang = langSelect.value || state.lang;
          state.nickname = nick;
          submit.disabled = true;
          try {
            const res = await api("/api/session", {
              method: "POST",
              body: JSON.stringify({
                nickname: nick,
                language: state.lang,
                notes: notes.value.trim() || null,
              }),
            });
            state.sessionId = res.session_id;
            state.ratings = {};
            state.panelStatus = {};
            state.panels = [];
            state.startupSeed = null;
            state.lastSavedAt = null;
            persistLocal();
            await loadPanels();
            state.view = { name: "panels", panelName: null, sampleIdx: 0 };
            render();
          } catch (e) {
            submit.disabled = false;
            status.textContent = `${t("error_network")}: ${e.message}`;
            status.className = "status-line err";
          }
        },
      },
      t("start_btn"),
    );

    const card = el(
      "div",
      { class: "card" },
      el("h1", {}, t("start_title")),
      el("p", { class: "subtle" }, t("start_desc")),
      el(
        "div",
        { class: "form-row" },
        el("label", { for: "nickname" }, t("nickname")),
        nickname,
      ),
      el(
        "div",
        { class: "form-row" },
        el("label", { for: "language" }, t("language_pref")),
        langSelect,
      ),
      el(
        "div",
        { class: "form-row" },
        el("label", { for: "notes" }, t("notes")),
        notes,
      ),
      submit,
      status,
    );
    app.appendChild(card);
  }

  async function loadPanels() {
    const res = await api("/api/panels");
    const startupSeed = String(res.startup_seed || "default");
    state.startupSeed = startupSeed;
    state.panels = (res.panels || []).map((panel) => ({
      ...panel,
      samples: seededShuffle(
        panel.samples || [],
        `samples:${startupSeed}:${panel.name}`,
      ),
    }));
    persistLocal();
  }

  function renderPanelList() {
    const header = el(
      "div",
      { class: "card" },
      el("h1", {}, t("panels_title")),
      el("p", { class: "subtle" }, t("panels_desc")),
    );
    app.appendChild(header);

    if (!state.panels.length) {
      app.appendChild(el("div", { class: "card empty" }, t("error_load")));
      return;
    }

    const grid = el("div", { class: "panel-grid" });
    for (const panel of state.panels) {
      const prog = panelProgress(panel);
      const status = panelDone(panel.name)
        ? "submitted"
        : prog.done > 0
          ? "in_progress"
          : "todo";
      const badges = el(
        "div",
        {},
        el("span", { class: "badge" }, panel.type.toUpperCase()),
        status === "submitted"
          ? el("span", { class: "tag success" }, t("panel_done"))
          : null,
      );
      const card = el(
        "div",
        {
          class: "panel-card",
          onclick: () => {
            state.view = {
              name: "panel",
              panelName: panel.name,
              sampleIdx: 0,
            };
            persistLocal();
            render();
          },
        },
        el("h2", {}, pickLang(panel.title)),
        badges,
        el("p", { class: "subtle" }, pickLang(panel.description)),
        el(
          "div",
          { class: "panel-meta" },
          `${t("panel_samples", panel.samples.length)} · ${t(
            "panel_dims",
            panel.dimensions.length,
          )} · ${t("progress_label", prog.done, prog.total)}`,
        ),
      );
      grid.appendChild(card);
    }
    app.appendChild(grid);

    const missingAll = collectMissingItems();
    const allComplete = missingAll.length === 0;
    const finalCard = el(
      "div",
      { class: "card" },
      el("h2", {}, t("final_submit_title")),
      el(
        "p",
        { class: allComplete ? "subtle" : "status-line warn" },
        allComplete ? t("final_submit_ready") : t("final_submit_incomplete", missingAll.length),
      ),
      el(
        "div",
        { class: "btn-row" },
        !allComplete
          ? el(
              "button",
              {
                class: "btn-secondary btn",
                onclick: () => handleMissingItems(missingAll),
              },
              t("final_check_missing"),
            )
          : null,
        el(
          "button",
          {
            class: "btn",
            onclick: async () => {
              const missingNow = collectMissingItems();
              if (missingNow.length) {
                handleMissingItems(missingNow);
                return;
              }
              if (!confirm(t("confirm_submit_all_ready"))) return;
              for (const panel of state.panels) {
                state.panelStatus[panel.name] = "submitted";
              }
              try {
                await syncSession(null, true);
                state.view = { name: "all_done", panelName: null, sampleIdx: 0 };
                persistLocal();
                render();
              } catch (e) {
                alert(`${t("error_network")}: ${e.message}`);
              }
            },
          },
          t("submit_all"),
        ),
      ),
    );
    app.appendChild(finalCard);
  }

  function renderPanel() {
    const panel = state.panels.find((p) => p.name === state.view.panelName);
    if (!panel) {
      state.view = { name: "panels", panelName: null, sampleIdx: 0 };
      return render();
    }
    if (state.view.sampleIdx >= panel.samples.length) {
      state.view.sampleIdx = panel.samples.length - 1;
    }
    if (state.view.sampleIdx < 0) state.view.sampleIdx = 0;
    const sample = panel.samples[state.view.sampleIdx];

    // Header
    const prog = panelProgress(panel);
    const progressPct = panel.samples.length
      ? Math.round(((state.view.sampleIdx + 1) / panel.samples.length) * 100)
      : 0;
    const header = el(
      "div",
      { class: "card" },
      el(
        "div",
        { class: "sample-banner" },
        el("h2", {}, pickLang(panel.title)),
        el(
          "div",
          { class: "tag" },
          t("sample_label", state.view.sampleIdx + 1, panel.samples.length),
        ),
      ),
      el(
        "div",
        { class: "progress-bar" },
        el("span", { style: `width:${progressPct}%` }),
      ),
      el("p", { class: "subtle" }, pickLang(panel.description)),
      el(
        "div",
        { class: "status-line" },
        t("progress_label", prog.done, prog.total),
      ),
    );
    app.appendChild(header);

    // Sample body
    const body = el("div", { class: "card" });

    if (sample.instruction) {
      body.appendChild(
        el(
          "div",
          { class: "sample-text" },
          el("h3", {}, t("instruction_label")),
          sample.instruction,
        ),
      );
    }
    if (panel.name === "multilingual" && sample.language) {
      body.appendChild(
        el(
          "div",
          { class: "sample-text" },
          el("h3", {}, t("sample_language_label")),
          formatSampleLanguage(sample.language),
        ),
      );
    }
    if (sample.text) {
      body.appendChild(
        el(
          "div",
          { class: "sample-text" },
          el("h3", {}, t("text_label")),
          sample.text,
        ),
      );
    }
    if (sample.reference_url) {
      body.appendChild(
        el(
          "div",
          { class: "audio-strip" },
          el("strong", {}, t("reference_label")),
          el("audio", {
            src: sample.reference_url,
            controls: "",
            controlslist: "nodownload noplaybackrate noremoteplayback",
            oncontextmenu: (e) => e.preventDefault(),
            preload: "none",
          }),
        ),
      );
    }

    if (panel.type === "abx") {
      body.appendChild(renderAbxBody(panel, sample));
    } else if (panel.type === "cmos") {
      body.appendChild(renderCmosBody(panel, sample));
    } else {
      body.appendChild(renderMosBody(panel, sample));
    }

    // Nav bar
    const navBar = el("div", { class: "nav-bar" });
    const leftGroup = el(
      "div",
      { class: "left" },
      el(
        "button",
        {
          class: "btn-secondary btn",
          onclick: () => {
            state.view = { name: "panels", panelName: null, sampleIdx: 0 };
            persistLocal();
            render();
          },
        },
        t("back_to_panels"),
      ),
      el(
        "button",
        {
          class: "btn-secondary btn",
          onclick: async () => {
            try {
              await syncSession([panel.name], false);
              renderSavedStatus(savedSlot);
            } catch (e) {
              savedSlot.textContent = `${t("error_network")}: ${e.message}`;
              savedSlot.className = "status-line err";
            }
          },
        },
        t("save_draft"),
      ),
    );
    const prevDisabled = state.view.sampleIdx === 0;
    const isLast = state.view.sampleIdx === panel.samples.length - 1;
    const rightGroup = el(
      "div",
      { class: "right" },
      el(
        "button",
        {
          class: "btn-secondary btn",
          disabled: prevDisabled ? "" : null,
          onclick: () => {
            if (state.view.sampleIdx > 0) {
              state.view.sampleIdx -= 1;
              persistLocal();
              render();
            }
          },
        },
        t("prev"),
      ),
      el(
        "button",
        {
          class: "btn",
          onclick: async () => {
            if (isLast) {
              const missingInPanel = collectMissingItems(panel);
              if (missingInPanel.length) {
                handleMissingItems(missingInPanel);
                return;
              }
              if (!confirm(t("confirm_submit_panel"))) return;
              state.panelStatus[panel.name] = "submitted";
              try {
                await syncSession([panel.name], false);
                state.view = {
                  name: "panels",
                  panelName: null,
                  sampleIdx: 0,
                };
                persistLocal();
                render();
              } catch (e) {
                alert(`${t("error_network")}: ${e.message}`);
              }
            } else {
              if (!dimensionsComplete(panel, sample)) {
                if (!confirm(t("sample_incomplete") + "\n\n→ skip?")) return;
              }
              state.view.sampleIdx += 1;
              persistLocal();
              try {
                syncSession([panel.name], false);
              } catch (_) {}
              render();
            }
          },
        },
        isLast ? t("submit_panel") : t("next"),
      ),
    );
    navBar.appendChild(leftGroup);
    navBar.appendChild(rightGroup);

    const savedSlot = el("div", { class: "status-line" });
    if (state.lastSavedAt) renderSavedStatus(savedSlot);

    body.appendChild(navBar);
    body.appendChild(savedSlot);
    app.appendChild(body);
  }

  function renderSavedStatus(node) {
    node.textContent = t("saved_at", state.lastSavedAt || fmtTime());
    node.className = "status-line ok";
  }

  function renderMosBody(panel, sample) {
    const wrapper = el("div", {});
    if (sample.ground_truth_url && !sample.systems.includes("ground_truth")) {
      wrapper.appendChild(
        el(
          "div",
          { class: "audio-strip" },
          el("strong", {}, t("ground_truth_label")),
          el("audio", {
            src: sample.ground_truth_url,
            controls: "",
            controlslist: "nodownload noplaybackrate noremoteplayback",
            oncontextmenu: (e) => e.preventDefault(),
            preload: "none",
          }),
        ),
      );
    }
    const order = orderedSystems(panel, sample);
    const grid = el("div", { class: "system-list" });
    const r = ratingsForSample(panel.name, sample.sample_id);
    r.scores = r.scores || {};

    order.forEach((sys, idx) => {
      const audioEntry = sample.audio.find((a) => a.role === sys);
      const audioUrl = audioEntry ? audioEntry.url : null;
      const card = el(
        "div",
        { class: "system-card" },
        el(
          "div",
          { class: "system-card-title" },
          `${t("system_label")} ${idx + 1}`,
        ),
        audioUrl
          ? el("audio", {
              src: audioUrl,
              controls: "",
              controlslist: "nodownload noplaybackrate noremoteplayback",
              oncontextmenu: (e) => e.preventDefault(),
              preload: "none",
            })
          : el("div", { class: "status-line err" }, "missing audio"),
      );
      const scoreFor = r.scores[sys] || (r.scores[sys] = {});
      for (const dim of panel.dimensions) {
        if (dim.type === "choice") {
          card.appendChild(renderChoice(dim, scoreFor, sample, panel));
        } else {
          card.appendChild(renderMosScale(dim, scoreFor, sample, panel));
        }
      }
      grid.appendChild(card);
    });
    wrapper.appendChild(grid);
    return wrapper;
  }

  function renderMosScale(dim, scoreFor, sample, panel) {
    const dimRow = el(
      "div",
      { class: "dim" },
      el(
        "div",
        { class: "dim-label" },
        el("span", {}, pickLang(dim.name)),
        dim.hint
          ? el("span", { class: "dim-hint" }, pickLang(dim.hint))
          : null,
      ),
    );
    const rating = el("div", { class: "rating" });
    for (const v of RATING_VALUES) {
      const pill = el(
        "button",
        {
          class:
            "pill" +
            (Math.abs((scoreFor[dim.key] ?? -1) - v) < 1e-6 ? " active" : ""),
          type: "button",
          onclick: () => {
            scoreFor[dim.key] = v;
            persistLocal();
            // re-render only this row by replacing pills' active class
            for (const child of rating.children) {
              const value = parseFloat(child.dataset.value);
              child.classList.toggle("active", Math.abs(value - v) < 1e-6);
            }
            try {
              syncSession([panel.name], false);
            } catch (_) {}
          },
          dataset: { value: String(v) },
        },
        Number.isInteger(v) ? String(v) : v.toFixed(1),
      );
      rating.appendChild(pill);
    }
    dimRow.appendChild(rating);
    return dimRow;
  }

  function renderChoice(dim, scoreFor, sample, panel) {
    const dimRow = el(
      "div",
      { class: "dim" },
      el(
        "div",
        { class: "dim-label" },
        el("span", {}, pickLang(dim.name)),
        dim.hint
          ? el("span", { class: "dim-hint" }, pickLang(dim.hint))
          : null,
      ),
    );
    const rating = el("div", { class: "rating" });
    for (const c of dim.choices || []) {
      const pill = el(
        "button",
        {
          class:
            "pill" + (scoreFor[dim.key] === c.value ? " active" : ""),
          type: "button",
          onclick: () => {
            scoreFor[dim.key] = c.value;
            persistLocal();
            for (const child of rating.children) {
              child.classList.toggle("active", child.dataset.value === c.value);
            }
            try {
              syncSession([panel.name], false);
            } catch (_) {}
          },
          dataset: { value: c.value },
        },
        pickLang(c.label),
      );
      rating.appendChild(pill);
    }
    dimRow.appendChild(rating);
    return dimRow;
  }

  function renderAbxBody(panel, sample) {
    const r = ratingsForSample(panel.name, sample.sample_id);
    const aEntry = sample.audio.find((a) => a.role.toUpperCase() === "A");
    const bEntry = sample.audio.find((a) => a.role.toUpperCase() === "B");
    const wrapper = el(
      "div",
      {},
      el("h3", {}, t("abx_question")),
      el(
        "div",
        { class: "system-list" },
        el(
          "div",
          { class: "system-card" },
          el("div", { class: "system-card-title" }, t("a_audio")),
          aEntry
            ? el("audio", {
                src: aEntry.url,
                controls: "",
                controlslist: "nodownload noplaybackrate noremoteplayback",
                oncontextmenu: (e) => e.preventDefault(),
                preload: "none",
              })
            : el("div", { class: "status-line err" }, "missing A"),
        ),
        el(
          "div",
          { class: "system-card" },
          el("div", { class: "system-card-title" }, t("b_audio")),
          bEntry
            ? el("audio", {
                src: bEntry.url,
                controls: "",
                controlslist: "nodownload noplaybackrate noremoteplayback",
                oncontextmenu: (e) => e.preventDefault(),
                preload: "none",
              })
            : el("div", { class: "status-line err" }, "missing B"),
        ),
      ),
    );
    const choices = el("div", { class: "abx-choices" });
    const options = [
      { value: "A", label: t("abx_pref_a") },
      { value: "tie", label: t("abx_tie") },
      { value: "B", label: t("abx_pref_b") },
    ];
    for (const opt of options) {
      const pill = el(
        "button",
        {
          class:
            "pill" + (r.abx_choice === opt.value ? " active" : ""),
          type: "button",
          onclick: () => {
            r.abx_choice = opt.value;
            persistLocal();
            for (const child of choices.children) {
              child.classList.toggle("active", child.dataset.value === opt.value);
            }
            try {
              syncSession([panel.name], false);
            } catch (_) {}
          },
          dataset: { value: opt.value },
        },
        opt.label,
      );
      choices.appendChild(pill);
    }
    wrapper.appendChild(el("div", { class: "dim" }, choices));
    return wrapper;
  }

  function renderCmosBody(panel, sample) {
    const wrapper = el("div", {});
    const r = ratingsForSample(panel.name, sample.sample_id);
    r.scores = r.scores || {};

    if (sample.anchor_url) {
      wrapper.appendChild(
        el(
          "div",
          { class: "audio-strip" },
          el("strong", {}, t("cmos_anchor_label")),
          el("span", { class: "subtle" }, sample.anchor_system || ""),
          el("audio", {
            src: sample.anchor_url,
            controls: "",
            controlslist: "nodownload noplaybackrate noremoteplayback",
            oncontextmenu: (e) => e.preventDefault(),
            preload: "none",
          }),
        ),
      );
    }

    wrapper.appendChild(
      el("div", { class: "sample-text subtle" }, t("cmos_question")),
    );

    const order = orderedSystems(panel, sample);
    const grid = el("div", { class: "system-list" });
    const dim = panel.dimensions[0] || {
      key: "cmos",
      name: { zh: "C-MOS", en: "C-MOS" },
      hint: {
        zh: "与基准系统相比：-3 明显更差，0 相近，+3 明显更好。",
        en: "Compared with the anchor system: -3 much worse, 0 similar, +3 much better.",
      },
    };

    order.forEach((sys, idx) => {
      const audioEntry = sample.audio.find((a) => a.role === sys);
      const audioUrl = audioEntry ? audioEntry.url : null;
      const card = el(
        "div",
        { class: "system-card" },
        el(
          "div",
          { class: "system-card-title" },
          `${t("system_label")} ${idx + 1}`,
        ),
        audioUrl
          ? el("audio", {
              src: audioUrl,
              controls: "",
              controlslist: "nodownload noplaybackrate noremoteplayback",
              oncontextmenu: (e) => e.preventDefault(),
              preload: "none",
            })
          : el("div", { class: "status-line err" }, "missing audio"),
      );
      const scoreFor = r.scores[sys] || (r.scores[sys] = {});
      card.appendChild(renderCmosScale(dim, scoreFor, panel));
      grid.appendChild(card);
    });

    wrapper.appendChild(grid);
    return wrapper;
  }

  function renderCmosScale(dim, scoreFor, panel) {
    const dimRow = el(
      "div",
      { class: "dim" },
      el(
        "div",
        { class: "dim-label" },
        el("span", {}, pickLang(dim.name)),
        dim.hint
          ? el("span", { class: "dim-hint" }, pickLang(dim.hint))
          : null,
      ),
    );
    const rating = el("div", { class: "rating cmos-rating" });
    for (const v of CMOS_VALUES) {
      const label = v > 0 ? `+${v}` : `${v}`;
      const pill = el(
        "button",
        {
          class:
            "pill" +
            (Math.abs((scoreFor[dim.key] ?? Number.NaN) - v) < 1e-6 ? " active" : ""),
          type: "button",
          onclick: () => {
            scoreFor[dim.key] = v;
            persistLocal();
            for (const child of rating.children) {
              const value = parseFloat(child.dataset.value);
              child.classList.toggle("active", Math.abs(value - v) < 1e-6);
            }
            try {
              syncSession([panel.name], false);
            } catch (_) {}
          },
          dataset: { value: String(v) },
        },
        label,
      );
      rating.appendChild(pill);
    }
    dimRow.appendChild(rating);
    return dimRow;
  }

  function renderAllDone() {
    app.appendChild(
      el(
        "div",
        { class: "card" },
        el("h1", {}, t("all_done_title")),
        el("p", { class: "subtle" }, t("all_done_desc")),
        el(
          "div",
          { class: "btn-row" },
          el(
            "button",
            {
              class: "btn-secondary btn",
              onclick: () => {
                resetToStart(true);
                render();
              },
            },
            "Restart",
          ),
        ),
      ),
    );
  }

  // ------------------------------------------------------------------ //
  // bootstrap                                                          //
  // ------------------------------------------------------------------ //

  langToggle.addEventListener("click", () => {
    state.lang = state.lang === "zh" ? "en" : "zh";
    persistLocal();
    render();
  });

  (async () => {
    const restored = restoreLocal();
    if (restored) {
      try {
        await ensureSessionValid();
        await loadPanels();
      } catch (_) {
        resetToStart(true);
      }
      render();
    } else {
      resetToStart(false);
      render();
    }
  })();
})();
