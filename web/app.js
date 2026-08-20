/* merkmal browser interface.
 *
 * Main-thread WASM: operations are microsecond-fast, so no worker is needed.
 * The module exposes JSON-returning functions; JavaScript parses and renders. */

"use strict";

const $ = id => document.getElementById(id);

/* ---- WASM wrapper ---------------------------------------------------- */

let mk = null;

function call(name, types, ...args) {
  const ptr = mk.ccall(name, "number", types, args);
  const json = mk.UTF8ToString(ptr);
  mk.ccall("merkmal_free", null, ["number"], [ptr]);
  return JSON.parse(json);
}

/* ---- state ----------------------------------------------------------- */

let systems = [];
let activeTab = "features";

/* ---- init ------------------------------------------------------------ */

(async function init() {
  try {
    mk = await createMerkmal();
  } catch (e) {
    document.querySelector(".loading, .status-banner").textContent =
      "Failed to load WebAssembly module: " + e.message;
    return;
  }

  const version = mk.ccall("merkmal_version", "string", [], []);
  $("version").textContent = "v" + version;
  fetch("BUILD_INFO", {cache: "no-cache"}).then(r => r.ok ? r.text() : "").then(text => {
    const m = text.match(/^git_commit\s+(\S+)/m);
    if (m) $("version").textContent += " (" + m[1] + ")";
  });

  refreshSystems();
  enableInputs();
  bindEvents();
})();

function refreshSystems() {
  const result = call("merkmal_list_systems", []);
  if (!result.ok) return;
  systems = result.systems;

  const sel = $("system");
  const prev = sel.value;
  sel.innerHTML = "";
  for (const s of systems) {
    const opt = document.createElement("option");
    opt.value = s.name;
    opt.textContent = s.name;
    sel.appendChild(opt);
  }
  if (prev && systems.some(s => s.name === prev)) {
    sel.value = prev;
  }
  sel.disabled = false;
  updateSystemKind();
}

function updateSystemKind() {
  const sys = systems.find(s => s.name === $("system").value);
  $("system-kind").textContent = sys ? sys.kind : "";
}

function enableInputs() {
  for (const el of document.querySelectorAll(
    ".tool-input input, #register-model"
  )) {
    el.disabled = false;
  }
}

function selectedSystem() {
  return $("system").value;
}

/* ---- events ---------------------------------------------------------- */

function bindEvents() {
  $("system").addEventListener("change", () => {
    updateSystemKind();
    rerunActiveTab();
  });

  /* Tabs */
  for (const btn of document.querySelectorAll(".tab")) {
    btn.addEventListener("click", () => {
      document.querySelector(".tab.on").classList.remove("on");
      btn.classList.add("on");
      const tab = btn.dataset.tab;
      document.querySelector(".tab-content:not([hidden])").hidden = true;
      $("tab-" + tab).hidden = false;
      activeTab = tab;
    });
  }

  /* Features */
  $("feat-grapheme").addEventListener("input", debounce(runFeatures, 150));

  /* Distance */
  $("dist-a").addEventListener("input", debounce(runDistance, 150));
  $("dist-b").addEventListener("input", debounce(runDistance, 150));

  /* Tokenizer */
  $("tok-input").addEventListener("input", debounce(runTokenizer, 150));
  $("tok-system").addEventListener("change", runTokenizer);
  $("tok-merge").addEventListener("change", runTokenizer);

  /* Matrix */
  $("mat-input").addEventListener("input", debounce(runMatrix, 300));

  /* Custom model */
  $("register-model").addEventListener("click", registerModel);

  /* IPA keyboard */
  let lastInput = null;
  for (const el of document.querySelectorAll(".tool-input input")) {
    el.addEventListener("focus", () => { lastInput = el; });
  }
  $("ipa-grid").addEventListener("mousedown", (e) => {
    const btn = e.target.closest("button");
    if (!btn) return;
    e.preventDefault();
    const ch = btn.dataset.char || btn.textContent.replace("◌", "");
    if (!lastInput) lastInput = document.querySelector(".tool-input input:not([disabled])");
    if (!lastInput) return;
    const start = lastInput.selectionStart;
    const end = lastInput.selectionEnd;
    const val = lastInput.value;
    lastInput.value = val.slice(0, start) + ch + val.slice(end);
    const pos = start + ch.length;
    lastInput.setSelectionRange(pos, pos);
    lastInput.focus();
    lastInput.dispatchEvent(new Event("input", {bubbles: true}));
  });
}

function rerunActiveTab() {
  switch (activeTab) {
    case "features":  runFeatures();  break;
    case "distance":  runDistance();   break;
    case "tokenizer": runTokenizer(); break;
    case "matrix":    runMatrix();    break;
  }
}

/* ---- features tab ---------------------------------------------------- */

function runFeatures() {
  const el = $("feat-result");
  const g = $("feat-grapheme").value.trim();
  if (!g) { el.innerHTML = ""; return; }

  const r = call("merkmal_grapheme_features", ["string", "string"],
                 selectedSystem(), g);
  if (!r.ok) {
    el.innerHTML = renderError(r);
    return;
  }

  let html = '<div class="feature-list">';
  for (const f of r.features) {
    html += '<span class="feature-chip">' + esc(f) + '</span>';
  }
  html += '</div>';

  if (r.vector) {
    html += '<div class="vector-section"><h3>Feature vector</h3>';
    html += '<div class="scroll"><table class="vector">';
    html += '<thead><tr><th>Label</th><th>Value</th></tr></thead><tbody>';
    for (let i = 0; i < r.vector.labels.length; i++) {
      const v = r.vector.values[i];
      const cls = v > 0 ? "pos" : v < 0 ? "neg" : "zero";
      html += '<tr><td>' + esc(r.vector.labels[i]) + '</td>';
      html += '<td class="' + cls + '">' + formatValue(v) + '</td></tr>';
    }
    html += '</tbody></table></div></div>';
  }

  el.innerHTML = html;
}

/* ---- distance tab ---------------------------------------------------- */

function runDistance() {
  const el = $("dist-result");
  const a = $("dist-a").value.trim();
  const b = $("dist-b").value.trim();
  if (!a || !b) { el.innerHTML = ""; return; }

  const r = call("merkmal_segment_distance", ["string", "string", "string"],
                 selectedSystem(), a, b);
  if (!r.ok) {
    el.innerHTML = renderError(r);
    return;
  }

  const covPct = (r.coverage * 100).toFixed(0);
  const covW = (r.coverage * 100).toFixed(0);
  let cmpText = "";
  if (r.comparability === "cross_tier") {
    cmpText = '<span style="color:var(--warn)">cross-tier (tone vs. segment)</span>';
  } else if (r.comparability === "no_shared_dimension") {
    cmpText = '<span style="color:var(--warn)">no shared dimension</span>';
  }

  let html = '<div class="distance-display">';
  html += '<div class="distance-value">' + r.distance.toFixed(4) + '</div>';
  html += '<div class="distance-meta">';
  html += '<span>coverage <b>' + covPct + '%</b>';
  html += '<span class="coverage-bar"><span class="coverage-fill" style="width:' + covW + '%"></span></span>';
  html += '</span>';
  if (cmpText) html += '<span>' + cmpText + '</span>';
  html += '</div></div>';
  el.innerHTML = html;
}

/* ---- tokenizer tab --------------------------------------------------- */

function runTokenizer() {
  const el = $("tok-result");
  const input = $("tok-input").value.trim();
  if (!input) { el.innerHTML = ""; return; }

  const sysAware = $("tok-system").checked ? 1 : 0;
  const merge = $("tok-merge").checked ? 1 : 0;
  const r = call("merkmal_tokenize",
                 ["string", "string", "number", "number"],
                 selectedSystem(), input, merge, sysAware);
  if (!r.ok) {
    el.innerHTML = renderError(r);
    return;
  }

  let html = '<div class="segment-preview">';
  for (const seg of r.segments) {
    const cls = seg.recognized ? "grapheme" : "grapheme unknown";
    html += '<span class="' + cls + '">' + esc(seg.grapheme) + '</span>';
  }
  html += '</div>';
  el.innerHTML = html;
}

/* ---- matrix tab ------------------------------------------------------ */

function runMatrix() {
  const el = $("mat-result");
  const input = $("mat-input").value.trim();
  if (!input) { el.innerHTML = ""; return; }

  const csv = input.replace(/\s*,\s*/g, ",").replace(/\s+/g, ",");
  const r = call("merkmal_distance_matrix", ["string", "string"],
                 selectedSystem(), csv);
  if (!r.ok) {
    el.innerHTML = renderError(r);
    return;
  }
  if (r.segments.length < 2) {
    el.innerHTML = '<div class="result-error"><span class="detail">Enter at least two segments.</span></div>';
    return;
  }

  let html = '<div class="matrix-scroll"><table class="matrix"><thead><tr>';
  html += '<th class="corner"></th>';
  for (let i = 0; i < r.segments.length; i++) {
    const cls = r.recognized[i] ? "" : " unknown";
    html += '<th class="' + cls + '">' + esc(r.segments[i]) + '</th>';
  }
  html += '</tr></thead><tbody>';

  for (let i = 0; i < r.segments.length; i++) {
    html += '<tr>';
    const rhCls = r.recognized[i] ? "" : " unknown";
    html += '<th class="' + rhCls + '">' + esc(r.segments[i]) + '</th>';
    for (let j = 0; j < r.segments.length; j++) {
      const v = r.matrix[i][j];
      if (v === null) {
        html += '<td class="null">—</td>';
      } else if (v === 0) {
        html += '<td class="zero">0</td>';
      } else {
        html += '<td>' + v.toFixed(4) + '</td>';
      }
    }
    html += '</tr>';
  }
  html += '</tbody></table></div>';
  el.innerHTML = html;
}

/* ---- custom model ---------------------------------------------------- */

function registerModel() {
  const text = $("model-text").value.trim();
  const status = $("model-status");
  if (!text) {
    status.textContent = "empty model";
    status.className = "model-status err";
    return;
  }

  const r = call("merkmal_register_model", ["string"], text);
  if (!r.ok) {
    status.textContent = r.detail || r.error || "registration failed";
    status.className = "model-status err";
    return;
  }

  status.textContent = "registered: " + r.name;
  status.className = "model-status ok";
  refreshSystems();
  $("system").value = r.name;
  updateSystemKind();
}

/* ---- rendering helpers ----------------------------------------------- */

function renderError(r) {
  let html = '<div class="result-error">';
  html += '<span class="what">' + esc(r.error || "error") + '</span>';
  if (r.detail) {
    html += '<div class="detail">' + esc(r.detail) + '</div>';
  }
  if (r.diagnosis) {
    let hint = "";
    if (r.diagnosis.valid_prefix) {
      hint += "valid prefix: " + r.diagnosis.valid_prefix;
    }
    if (r.diagnosis.offending) {
      hint += (hint ? " — " : "") + "offending: " + r.diagnosis.offending;
    }
    if (hint) {
      html += '<div class="hint">' + esc(hint) + '</div>';
    }
  }
  if (r.normalized) {
    html += '<div class="hint">normalized form ' + esc(r.normalized) +
            ' is recognized</div>';
  }
  html += '</div>';
  return html;
}

function esc(s) {
  const d = document.createElement("div");
  d.textContent = s;
  return d.innerHTML;
}

function formatValue(v) {
  if (v === 1) return "+1";
  if (v === -1) return "−1";
  if (v === 0) return "0";
  return v.toFixed(4);
}

function debounce(fn, ms) {
  let t;
  return function () {
    clearTimeout(t);
    t = setTimeout(fn, ms);
  };
}

/* ---- guide ------------------------------------------------------------- */

let guideStep = 0;

function showGuideStep(index) {
  guideStep = index;
  const step = GUIDE_STEPS[index];
  $("guide-title").textContent = step.title;
  $("guide-body").innerHTML = step.content;
  $("guide-body").scrollTop = 0;
  const tryBtn = $("guide-try");
  tryBtn.hidden = !step.example;
  tryBtn.onclick = () => {
    const ex = step.example;
    const tabBtn = document.querySelector('.tab[data-tab="' + ex.tab + '"]');
    if (tabBtn) tabBtn.click();
    for (const [id, val] of Object.entries(ex.inputs)) {
      const el = $(id);
      if (el) {
        el.value = val;
        el.dispatchEvent(new Event("input", {bubbles: true}));
      }
    }
    $("guide").classList.remove("open");
  };
  for (const button of $("guide-steps").children) {
    button.classList.toggle("current", Number(button.dataset.step) === index);
  }
}

function buildGuide() {
  const steps = $("guide-steps");
  GUIDE_STEPS.forEach((step, index) => {
    const button = document.createElement("button");
    button.textContent = String(index + 1);
    button.title = step.title;
    button.dataset.step = String(index);
    button.addEventListener("click", () => showGuideStep(index));
    steps.appendChild(button);
  });
  showGuideStep(0);
}

buildGuide();
$("guide-open").addEventListener("click", () => $("guide").classList.add("open"));
$("guide-close").addEventListener("click", () => $("guide").classList.remove("open"));
