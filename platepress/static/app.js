const $ = (id) => document.getElementById(id);
const banner = $("banner");
let book = {};
let settings = {};
let pollTimer = null;

function showBanner(text, kind) {
  banner.textContent = text || "";
  banner.className = text ? kind || "err" : "";
}

async function j(url, opts) {
  const r = await fetch(url, opts);
  const data = await r.json().catch(() => ({}));
  if (!r.ok) {
    const msg = data.detail || data.error || r.statusText;
    throw new Error(typeof msg === "string" ? msg : JSON.stringify(msg));
  }
  return data;
}

async function withBusy(el, busyLabel, fn) {
  if (!el || el.disabled) return;
  const label = el.textContent;
  el.disabled = true;
  el.textContent = busyLabel;
  try {
    await fn();
  } finally {
    el.disabled = false;
    el.textContent = label;
  }
}

function setView(name) {
  document.querySelectorAll("nav button").forEach((b) => {
    b.classList.toggle("on", b.dataset.view === name);
  });
  document.querySelectorAll(".view").forEach((v) => {
    v.classList.toggle("on", v.id === "view-" + name);
  });
  showCurrentBook();
  if (name === "queue") refreshRuns();
  if (name === "settings") loadBooks();
}

document.querySelectorAll("nav button").forEach((b) => {
  b.addEventListener("click", () => setView(b.dataset.view));
});

const SET_KEYS = [
  "host", "port", "workflow_text", "workflow_ref",
  "models_dir", "loras_dir", "unet_name",
  "style", "layout", "layout_text", "tail", "neg", "ref_cutout_text",
  "images_per_plate", "output_root",
  "steps", "cfg", "sampler_name", "scheduler",
];
const LORA_SLOTS = 4;
let weightLists = { models: [], loras: [] };

function krea2Name(name) {
  return /krea/i.test(name || "");
}

function resolveCombo(wanted, available) {
  const name = String(wanted || "").trim();
  const list = available || [];
  if (!name || !list.length) return name;
  if (list.indexOf(name) >= 0) return name;
  const base = name.split("/").pop();
  const hits = list.filter((n) => String(n).split("/").pop() === base);
  if (hits.length === 1) return hits[0];
  return name;
}

function updateUnetWarn() {
  const el = $("unet-warn");
  if (!el) return;
  const name = ($("unet_name") && $("unet_name").value) || "";
  const models = weightLists.models || [];
  const resolved = resolveCombo(name, models);
  const inList = !models.length || !name || models.indexOf(resolved) >= 0;
  const krea = !name || krea2Name(resolved);
  if (name && models.length && !inList) {
    el.textContent = name + " is not in Comfy’s UNETLoader list. Load lists from Comfy and pick the exact name.";
    el.classList.remove("off");
    return;
  }
  el.textContent = "Must be a Krea 2 UNET. Pick the exact Comfy name (e.g. KREA2/krea2_turbo_bf16.safetensors). Bare filenames fail. This app does not download models.";
  el.classList.toggle("off", krea);
}

function fillDatalist(id, names, extra) {
  const dl = $(id);
  if (!dl) return;
  const seen = new Set();
  dl.innerHTML = "";
  [extra, ...(names || [])].forEach((n) => {
    if (!n || seen.has(n)) return;
    seen.add(n);
    const o = document.createElement("option");
    o.value = n;
    dl.appendChild(o);
  });
}

function readLoras() {
  const box = $("lora-stack");
  if (!box) return [];
  const out = [];
  box.querySelectorAll(".lora-row").forEach((row) => {
    const name = String((row.querySelector(".lora-name") || {}).value || "").trim();
    if (!name) return;
    const strength = Number((row.querySelector(".lora-strength") || {}).value);
    out.push({ name, strength: Number.isFinite(strength) ? strength : 0.8 });
  });
  return out.slice(0, LORA_SLOTS);
}

function renderLoras(slots) {
  const box = $("lora-stack");
  if (!box) return;
  const list = (slots && slots.length) ? slots.slice(0, LORA_SLOTS) : [{ name: "", strength: 0.8 }];
  box.innerHTML = "";
  list.forEach((slot, i) => {
    const row = document.createElement("div");
    row.className = "lora-row";
    row.innerHTML = `
      <div class="row">
        <div>
          <label>LoRA ${i + 1}</label>
          <input class="lora-name" type="text" list="lora-list" />
        </div>
        <div style="max-width:7rem">
          <label>strength</label>
          <input class="lora-strength" type="number" step="0.05" />
        </div>
        <div style="max-width:5.5rem">
          <label>&nbsp;</label>
          <button type="button" class="act ghost lora-remove">Remove</button>
        </div>
      </div>`;
    row.querySelector(".lora-name").value = slot.name || "";
    row.querySelector(".lora-strength").value = slot.strength ?? 0.8;
    row.querySelector(".lora-remove").onclick = () => {
      const next = [...box.querySelectorAll(".lora-row")]
        .map((r, j) => ({
          name: String((r.querySelector(".lora-name") || {}).value || "").trim(),
          strength: Number((r.querySelector(".lora-strength") || {}).value) || 0.8,
          drop: j === i,
        }))
        .filter((x) => !x.drop)
        .map(({ name, strength }) => ({ name, strength }));
      renderLoras(next);
    };
    box.appendChild(row);
  });
  const add = $("add-lora");
  if (add) add.disabled = list.length >= LORA_SLOTS;
}

function layoutValue() {
  return ($("layout") && $("layout").value) || (settings.layout) || "one";
}

function updateAssemblePreview() {
  const box = $("assemble-preview");
  if (!box) return;
  const bits = [
    ($("style") && $("style").value.trim()) || "",
    ($("layout_text") && $("layout_text").value.trim()) || "",
    layoutValue() === "split"
      ? "Left pane: (first slug). Right pane: (next slug)."
      : "",
    ($("tail") && $("tail").value.trim()) || "",
    ($("send_refs") && $("send_refs").checked) ? "" : "(Cast lock)",
    "(Book wall)",
  ].filter(Boolean);
  box.textContent = bits.join(" ");
}

function renderExamples(examples) {
  const box = $("examples");
  if (!box) return;
  box.innerHTML = "";
  const list = examples && typeof examples === "object"
    ? Object.values(examples)
    : [];
  list.forEach((ex) => {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "example";
    btn.dataset.exid = ex.id || "";
    btn.innerHTML = `<strong>${ex.label || ex.id}</strong><span>${ex.blurb || ""}</span>`;
    btn.addEventListener("click", () => applyExample(ex));
    box.appendChild(btn);
  });
  markActiveExample();
}

function markActiveExample() {
  const layout = layoutValue();
  const style = ($("style") && $("style").value) || "";
  document.querySelectorAll("#examples .example").forEach((btn) => {
    const ex = (settings.examples || {})[btn.dataset.exid] || {};
    btn.classList.toggle("on", ex.layout === layout && ex.style === style);
  });
}

function applyExample(ex) {
  if (!ex) return;
  $("style").value = ex.style || "";
  $("layout_text").value = ex.layout_text || "";
  $("tail").value = ex.tail || "";
  $("neg").value = ex.neg || "";
  if ($("layout")) $("layout").value = ex.layout || "one";
  settings.layout = ex.layout || "one";
  markActiveExample();
  updateAssemblePreview();
}

function fillSettings(s) {
  settings = s;
  SET_KEYS.forEach((k) => {
    const el = $(k);
    if (el) el.value = s[k] ?? "";
  });
  const sr = $("send_refs");
  if (sr) sr.checked = !!s.send_refs;
  const rc = $("ref_cutout");
  if (rc) rc.checked = !!s.ref_cutout;
  if ($("layout")) $("layout").value = s.layout || "one";
  renderLoras(s.loras);
  fillDatalist("unet-list", weightLists.models, s.unet_name);
  fillDatalist("lora-list", weightLists.loras, (s.loras && s.loras[0] && s.loras[0].name) || s.lora_name);
  updateUnetWarn();
  renderExamples(s.examples);
  updateAssemblePreview();
}

function readSettings() {
  const body = {};
  SET_KEYS.forEach((k) => {
    const el = $(k);
    if (!el) return;
    const v = el.value;
    body[k] = el.type === "number" ? Number(v) : v;
  });
  const sr = $("send_refs");
  if (sr) body.send_refs = sr.checked;
  const rc = $("ref_cutout");
  if (rc) body.ref_cutout = rc.checked;
  body.loras = readLoras();
  return body;
}

function bookLabel() {
  const id = book.id || "";
  const title = (book.title || "").trim();
  if (title && id && title !== id) return `${id} · ${title}`;
  return id || title || "no book";
}

function showCurrentBook() {
  const label = bookLabel();
  const header = $("current-book");
  if (header) header.textContent = "this book · " + label;
  document.querySelectorAll("[data-book-heading]").forEach((el) => {
    const prefix = el.getAttribute("data-book-heading") || "";
    el.textContent = prefix ? `${prefix} · ${label}` : label;
  });
  const bookId = $("book-id");
  if (bookId) bookId.textContent = book.id ? `folder ${book.id} — cast, story, and plates live here` : "";
}

function renderCast() {
  showCurrentBook();
  const box = $("cast");
  box.innerHTML = "";
  (book.characters || []).forEach((c, i) => {
    const div = document.createElement("div");
    div.className = "card";
    const slots = (c.ref_slots || []).map((slot) => {
      const on = slot.active ? "on" : "off";
      const label = slot.active ? "active" : "disabled";
      const img = slot.url ? `<img src="${slot.url}" alt="${slot.name}" />` : "";
      return `<div class="ref-slot ${on}">
        ${img}
        <div class="tiny">${slot.name} · ${label}</div>
        <button type="button" class="act ghost" data-useref="${c.name}" data-cid="${c.id}" data-refpath="${encodeURIComponent(slot.path)}" ${slot.active ? "disabled" : ""}>Use this</button>
        <button type="button" class="act ghost" data-rmref="${c.name}" data-cid="${c.id}" data-rmpath="${encodeURIComponent(slot.path)}">Remove</button>
      </div>`;
    }).join("");
    div.innerHTML = `
      <label>Name (token)</label>
      <input type="text" data-k="name" data-i="${i}" value="${c.name || ""}" />
      <label>Lock</label>
      <textarea data-k="lock_text" data-i="${i}">${c.lock_text || ""}</textarea>
      <p class="tiny">Locked seed: ${c.locked_seed ?? "none"}</p>
      <button class="act ghost" data-clear="${c.name}">Clear seed</button>
      <label>Still — one body. Optional: cutout with background removed (see Settings).</label>
      <div class="ref-row">${slots || '<p class="tiny">no still</p>'}</div>
      <label class="tiny">Replace still</label>
      <input type="file" accept="image/*" data-upload="${c.name}" data-cid="${c.id}" />
      <button type="button" class="act ghost" data-del-id="${c.id || ""}" data-del-name="${c.name || ""}">Delete character</button>
    `;
    box.appendChild(div);
  });
  box.querySelectorAll("input[data-k], textarea[data-k]").forEach((el) => {
    el.addEventListener("change", () => {
      const i = Number(el.dataset.i);
      if (el.dataset.k === "name") {
        const token = el.value.trim();
        const clash = (book.characters || []).some((c, j) => j !== i && c.name === token);
        if (clash) {
          showBanner(`${token} already exists. Replace the still on that card.`, "err");
          el.value = book.characters[i].name;
          return;
        }
      }
      book.characters[i][el.dataset.k] = el.value;
      saveBookSilent().catch((e) => {
        showBanner(e.message, "err");
        loadBook();
      });
    });
  });
  function bindDelete(el) {
    el.addEventListener("click", async (ev) => {
      ev.preventDefault();
      ev.stopPropagation();
      const id = el.getAttribute("data-del-id") || "";
      const name = el.getAttribute("data-del-name") || "";
      try {
        const r = await j("/api/character/delete", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ id, name }),
        });
        book = r.book;
        renderCast();
        showBanner("character removed", "ok");
      } catch (e) {
        showBanner(e.message, "err");
      }
    });
  }
  box.querySelectorAll("[data-del-id], [data-del]").forEach(bindDelete);
  box.querySelectorAll("[data-clear]").forEach((el) => {
    el.addEventListener("click", async () => {
      await j("/api/lock-seed", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ character: el.dataset.clear, clear: true }),
      });
      await loadBook();
    });
  });
  box.querySelectorAll("[data-upload]").forEach((el) => {
    el.addEventListener("change", async () => {
      if (!el.files[0]) return;
      const fd = new FormData();
      fd.append("character", el.dataset.upload);
      fd.append("character_id", el.dataset.cid || "");
      fd.append("file", el.files[0]);
      const r = await fetch("/api/upload-ref", { method: "POST", body: fd });
      const data = await r.json();
      if (!r.ok) { showBanner(data.detail || "upload failed", "err"); return; }
      book = data.book;
      renderCast();
    });
  });
  box.querySelectorAll("[data-rmref]").forEach((el) => {
    el.addEventListener("click", async () => {
      const r = await j("/api/remove-ref", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          id: el.dataset.cid,
          character: el.dataset.rmref,
          path: decodeURIComponent(el.dataset.rmpath),
        }),
      });
      book = r.book;
      renderCast();
    });
  });
  box.querySelectorAll("[data-useref]").forEach((el) => {
    el.addEventListener("click", async () => {
      const r = await j("/api/activate-ref", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          id: el.dataset.cid,
          character: el.dataset.useref,
          path: decodeURIComponent(el.dataset.refpath),
        }),
      });
      book = r.book;
      renderCast();
    });
  });
}

async function copyAssembled(text, slug) {
  try {
    await navigator.clipboard.writeText(text || "");
    showBanner(slug ? "copied " + slug : "copied prompt", "ok");
  } catch (e) {
    showBanner(e.message, "err");
  }
}

function renderPreview(plates, warnings, checkedSlugs) {
  const tb = $("preview");
  tb.innerHTML = "";
  (plates || []).forEach((p) => {
    const tr = document.createElement("tr");
    const pane = p.pane ? `${p.pane}${p.pair_with ? " · " + p.pair_with : ""}` : "";
    const warn = [pane, p.risky_twoshot ? "two-shot" : "", (p.warnings || []).join("; ")]
      .filter(Boolean).join("; ");
    const on = !checkedSlugs || checkedSlugs.some((s) => s === p.slug);
    const assembled = p.assembled || "";

    const tdCheck = document.createElement("td");
    const cb = document.createElement("input");
    cb.type = "checkbox";
    cb.dataset.slug = p.slug;
    if (on) cb.checked = true;
    tdCheck.appendChild(cb);

    const tdSlug = document.createElement("td");
    const code = document.createElement("code");
    code.textContent = p.slug;
    tdSlug.appendChild(code);

    const tdCast = document.createElement("td");
    tdCast.textContent = (p.character_ids || []).join(", ");

    const tdMeta = document.createElement("td");
    tdMeta.textContent = p.metaphor || "";

    const tdWarn = document.createElement("td");
    tdWarn.textContent = warn;
    if (p.risky_twoshot) tdWarn.className = "risky";

    const tdPrompt = document.createElement("td");
    tdPrompt.className = "preview" + (assembled ? " copy-prompt" : "");
    const snippet = document.createElement("span");
    snippet.textContent = assembled.slice(0, 180);
    tdPrompt.appendChild(snippet);
    if (assembled) {
      tdPrompt.title = "Click to copy the full assembled prompt";
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "act ghost copy-assembled";
      btn.textContent = "Copy";
      btn.addEventListener("click", (e) => {
        e.stopPropagation();
        copyAssembled(assembled, p.slug);
      });
      tdPrompt.appendChild(btn);
      tdPrompt.addEventListener("click", () => copyAssembled(assembled, p.slug));
    }

    tr.append(tdCheck, tdSlug, tdCast, tdMeta, tdWarn, tdPrompt);
    tb.appendChild(tr);
  });
  slugBoxes().forEach((el) => el.addEventListener("change", syncSlugAll));
  syncSlugAll();
  if (warnings && warnings.length) showBanner(warnings.join(" · "), "warn");
}

function slugBoxes() {
  return [...document.querySelectorAll("#preview input[data-slug]")];
}

function selectedSlugs() {
  return slugBoxes().filter((el) => el.checked).map((el) => el.dataset.slug);
}

function syncSlugAll() {
  const head = $("slug-all");
  if (!head) return;
  const boxes = slugBoxes();
  const n = boxes.filter((el) => el.checked).length;
  head.indeterminate = n > 0 && n < boxes.length;
  head.checked = boxes.length > 0 && n === boxes.length;
}

function setAllSlugs(on) {
  slugBoxes().forEach((el) => { el.checked = on; });
  syncSlugAll();
}

async function saveBookSilent() {
  book.title = $("title").value;
  book.prompts_raw = $("prompts_raw").value;
  book.captions_raw = $("captions_raw").value;
  const wf = $("book-workflow");
  if (wf) book.workflow = wf.value || null;
  const r = await j("/api/book", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(book),
  });
  book = r.book;
  showCurrentBook();
}

async function fillWorkflowSelect() {
  const sel = $("book-workflow");
  if (!sel) return;
  const r = await j("/api/workflows");
  const selected = book.workflow || r.selected || "";
  const items = r.workflows || [];
  sel.innerHTML = "";
  const def = document.createElement("option");
  def.value = "";
  def.textContent = "Default (Settings V3)";
  sel.appendChild(def);
  items.forEach((w) => {
    const o = document.createElement("option");
    o.value = w.path;
    const tag = w.source === "book" ? "this book" : w.source === "settings" ? "settings" : "shared";
    o.textContent = w.name + " (" + tag + ")";
    sel.appendChild(o);
  });
  const paths = items.map((w) => w.path);
  if (selected && paths.indexOf(selected) < 0) {
    const o = document.createElement("option");
    o.value = selected;
    o.textContent = selected;
    sel.appendChild(o);
  }
  sel.value = selected || "";
}

async function loadBook() {
  const r = await j("/api/book");
  book = r.book;
  $("title").value = book.title || "";
  $("prompts_raw").value = book.prompts_raw || "";
  $("captions_raw").value = book.captions_raw || "";
  await fillWorkflowSelect();
  renderCast();
  renderPreview(book.plates || [], []);
  if (r.notice) showBanner(r.notice, "warn");
}

function slugFromName(name) {
  const m = String(name || "").match(/(?:^|_)((?:p|t)\d+_[A-Za-z0-9]+)/i);
  if (m) return m[1];
  const stem = name.replace(/\.[a-z]+$/i, "");
  return stem.replace(/_\d+$/, "");
}

function thumbFigure(t, names) {
  const slug = t.slug || slugFromName(t.name);
  const seed = t.seed != null && t.seed !== "" ? String(t.seed) : "";
  const bid = t.book_id || "";
  const fig = document.createElement("figure");
  const opts = names.map((n) => `<option value="${n}">${n}</option>`).join("");
  const lockBtn = seed
    ? `<button class="act ghost" data-lock="${seed}">Lock seed</button>`
    : "";
  fig.innerHTML = `
    <img src="${t.url}" alt="${t.name}" />
    <figcaption>${t.name || ""}</figcaption>
    <select data-char>${opts}</select>
    ${lockBtn}
    <button class="act ghost" data-reroll="${slug}">Reroll</button>
    <button class="act ghost" data-asref="${t.path}">Use as ref</button>
    <button class="act ghost" data-letter="${slug}">Letter this</button>
    <button class="act ghost" data-rmfile="${encodeURIComponent(t.path)}" data-bookid="${bid}">Delete file</button>
  `;
  return fig;
}

async function refreshRuns() {
  const r = await j("/api/runs");
  $("qstatus").textContent = `queue ${r.queue_depth} · ${r.comfy.ok ? "Comfy up" : r.comfy.message} · ${r.current || ""}`;
  if (!r.comfy.ok) showBanner(r.comfy.message, "err");
  const fallbackNames = (book.characters || []).map((c) => c.name);
  const box = $("thumbs");
  box.innerHTML = "";
  const current = (r.books || []).find((b) => b.current)
    || (r.books || []).find((b) => b.id === r.current)
    || { id: r.current || "", title: "This book", thumbs: r.thumbs || [], names: fallbackNames, n: (r.thumbs || []).length };
  const names = current.names && current.names.length ? current.names : fallbackNames;
  const thumbs = current.thumbs || [];
  const batches = (current.batches && current.batches.length)
    ? current.batches
    : (thumbs.length ? [{ id: "all", label: "", thumbs, n: thumbs.length }] : []);
  const sec = document.createElement("section");
  sec.className = "book-block latest";
  const h = document.createElement("h3");
  const n = current.n != null ? current.n : thumbs.length;
  h.textContent = [current.id || r.current, current.title && current.title !== current.id ? current.title : "", n]
    .filter((x) => x !== "" && x != null)
    .join(" · ");
  sec.appendChild(h);
  if (!batches.length) {
    const p = document.createElement("p");
    p.className = "tiny";
    p.textContent = "No plates in this book yet.";
    sec.appendChild(p);
  } else {
    batches.forEach((b, i) => {
      const block = document.createElement("section");
      block.className = "version-block" + (i === 0 ? " latest" : "");
      const vh = document.createElement("h4");
      const vn = b.n != null ? b.n : (b.thumbs || []).length;
      vh.textContent = [b.label, vn].filter((x) => x !== "" && x != null).join(" · ");
      block.appendChild(vh);
      const grid = document.createElement("div");
      grid.className = "thumbs";
      (b.thumbs || []).forEach((t) => grid.appendChild(thumbFigure(t, names)));
      block.appendChild(grid);
      sec.appendChild(block);
    });
  }
  box.appendChild(sec);
  box.querySelectorAll("[data-lock]").forEach((el) => {
    el.addEventListener("click", async () => {
      const sel = el.parentElement.querySelector("[data-char]");
      await j("/api/lock-seed", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ character: sel.value, seed: Number(el.dataset.lock) }),
      });
      showBanner(`locked ${el.dataset.lock} to ${sel.value}`, "ok");
      loadBook();
    });
  });
  box.querySelectorAll("[data-reroll]").forEach((el) => {
    el.addEventListener("click", async () => {
      try {
        await saveBookSilent();
        const r = await j("/api/reroll", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ slug: el.dataset.reroll }),
        });
        if (!r.ok) { showBanner(r.error || "reroll failed", "err"); return; }
        if (!r.queued) {
          showBanner(`nothing queued${r.notice ? " · " + r.notice : ""}`, "warn");
          return;
        }
        showBanner(`queued ${r.queued}${r.notice ? " · " + r.notice : ""}`, "ok");
        startPoll();
      } catch (e) { showBanner(e.message, "err"); }
    });
  });
  box.querySelectorAll("[data-asref]").forEach((el) => {
    el.addEventListener("click", async () => {
      const sel = el.parentElement.querySelector("[data-char]");
      await j("/api/use-as-ref", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ character: sel.value, path: el.dataset.asref }),
      });
      showBanner(`ref → ${sel.value}`, "ok");
      loadBook();
    });
  });
  box.querySelectorAll("[data-letter]").forEach((el) => {
    el.addEventListener("click", async () => {
      const slug = el.dataset.letter;
      showBanner(`lettering ${slug}…`, "ok");
      try {
        await withBusy(el, "Lettering…", async () => {
          const r = await j("/api/letter", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ slug }),
          });
          showBanner(`lettered ${r.lettered}`, "ok");
        });
      } catch (e) { showBanner(e.message, "err"); }
    });
  });
  box.querySelectorAll("[data-rmfile]").forEach((el) => {
    el.addEventListener("click", async () => {
      if (!confirm("Delete this generated image? This cannot be undone.")) return;
      try {
        const r = await j("/api/plates/delete", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            confirm: true,
            scope: "files",
            book_id: el.dataset.bookid || undefined,
            paths: [decodeURIComponent(el.dataset.rmfile)],
          }),
        });
        showBanner(`deleted ${r.deleted}`, "ok");
        refreshRuns();
      } catch (e) { showBanner(e.message, "err"); }
    });
  });
}

async function loadBooks() {
  const box = $("books");
  if (!box) return;
  const r = await j("/api/books");
  box.innerHTML = "";
  (r.books || []).forEach((b) => {
    const row = document.createElement("div");
    row.className = "card";
    row.innerHTML = `
      <strong>${b.current ? "▸ " : ""}${b.title}</strong>
      <span class="tiny"> ${b.id} · ${b.n_plates} plates</span>
      ${b.current ? "" : `<button type="button" class="act ghost" data-openbook="${b.id}">Open</button>`}
      ${b.protected || b.id === "default" ? `<span class="tiny">demo</span>` : `<button type="button" class="act ghost" data-delbook="${b.id}">Delete book</button>`}
    `;
    box.appendChild(row);
  });
  box.querySelectorAll("[data-openbook]").forEach((el) => {
    el.addEventListener("click", async () => {
      const r = await j("/api/book/open", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id: el.dataset.openbook }),
      });
      book = r.book;
      $("title").value = book.title || "";
      $("prompts_raw").value = book.prompts_raw || "";
      $("captions_raw").value = book.captions_raw || "";
      renderCast();
      renderPreview(book.plates || [], []);
      showBanner("opened " + el.dataset.openbook, "ok");
      loadBooks();
    });
  });
  box.querySelectorAll("[data-delbook]").forEach((el) => {
    el.addEventListener("click", async () => {
      if (!confirm("Delete book “" + el.dataset.delbook + "”?\nThis removes the folder: plates, lettered files, stills, and story.\nThis cannot be undone.")) return;
      try {
        const r = await j("/api/book/delete", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ confirm: true, id: el.dataset.delbook }),
        });
        book = r.book;
        $("title").value = book.title || "";
        $("prompts_raw").value = book.prompts_raw || "";
        $("captions_raw").value = book.captions_raw || "";
        renderCast();
        renderPreview(book.plates || [], []);
        showBanner("book deleted", "ok");
        loadBooks();
      } catch (e) { showBanner(e.message, "err"); }
    });
  });
}

function startPoll() {
  if (pollTimer) return;
  pollTimer = setInterval(async () => {
    const r = await j("/api/runs");
    if (document.getElementById("view-queue").classList.contains("on")) refreshRuns();
    $("qstatus").textContent = `queue ${r.queue_depth}`;
    if (r.queue_depth === 0) {
      clearInterval(pollTimer);
      pollTimer = null;
      if (document.getElementById("view-queue").classList.contains("on")) refreshRuns();
    }
  }, 2000);
}

async function generate(mode) {
  const btn = mode === "sel" ? $("gen-sel") : mode === "all" ? $("gen-all") : $("gen-missing");
  try {
    await saveBookSilent();
    const body = {
      skip_done: $("skip_done").checked,
      send_refs: !!($("send_refs") && $("send_refs").checked),
    };
    if (mode === "all") body.skip_done = false;
    if (mode === "sel") {
      const picked = selectedSlugs();
      const parsed = await j("/api/parse", { method: "POST" });
      renderPreview(parsed.plates || [], parsed.warnings || [], picked);
      book.plates = parsed.plates;
      body.slugs = selectedSlugs();
      if (layoutValue() === "split" && body.slugs.length === 1) {
        const plates = parsed.plates || [];
        const i = plates.findIndex((p) => p.slug === body.slugs[0]);
        if (i >= 0 && plates[i + 1]) body.slugs.push(plates[i + 1].slug);
      }
      body.skip_done = false;
      if (!body.slugs.length) {
        showBanner("no plates selected after Parse — check the rows (slug renamed?)", "err");
        return;
      }
    }
    await withBusy(btn, "Queuing…", async () => {
      const r = await j("/api/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!r.ok) { showBanner(r.error || "generate failed", "err"); return; }
      if (!r.queued) {
        showBanner(
          `nothing queued (skipped ${r.skipped})${r.notice ? " · " + r.notice : ""}`,
          "warn"
        );
        return;
      }
      showBanner(`queued ${r.queued} (skipped ${r.skipped})${r.notice ? " · " + r.notice : ""}`, "ok");
      startPoll();
      setView("queue");
    });
  } catch (e) {
    showBanner(e.message, "err");
  }
}

["style", "layout_text", "tail", "ref_cutout_text"].forEach((id) => {
  const el = $(id);
  if (el) el.addEventListener("input", () => {
    markActiveExample();
    updateAssemblePreview();
  });
});
if ($("ref_cutout")) {
  $("ref_cutout").addEventListener("change", updateAssemblePreview);
}
if ($("send_refs")) {
  $("send_refs").addEventListener("change", async () => {
    try {
      settings = await j("/api/settings", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(readSettings()),
      });
      fillSettings(settings);
      updateAssemblePreview();
      showBanner(
        settings.send_refs ? "stills ON — Qwen will copy pose and backdrop" : "stills off — text locks only",
        settings.send_refs ? "warn" : "ok"
      );
    } catch (e) {
      showBanner(e.message, "err");
    }
  });
}
if ($("unet_name")) {
  $("unet_name").addEventListener("input", updateUnetWarn);
  $("unet_name").addEventListener("change", updateUnetWarn);
}
if ($("add-lora")) {
  $("add-lora").onclick = () => {
    const box = $("lora-stack");
    const rows = box ? [...box.querySelectorAll(".lora-row")] : [];
    if (rows.length >= LORA_SLOTS) return;
    const cur = rows.map((row) => ({
      name: String((row.querySelector(".lora-name") || {}).value || "").trim(),
      strength: Number((row.querySelector(".lora-strength") || {}).value) || 0.8,
    }));
    cur.push({ name: "", strength: 0.8 });
    renderLoras(cur);
  };
}
if ($("scan-weights")) {
  $("scan-weights").onclick = async () => {
    try {
      const r = await j("/api/weights", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          host: ($("host") && $("host").value) || "",
          port: ($("port") && $("port").value) || "",
          models_dir: ($("models_dir") && $("models_dir").value) || "",
          loras_dir: ($("loras_dir") && $("loras_dir").value) || "",
        }),
      });
      weightLists.models = r.models || [];
      weightLists.loras = r.loras || [];
      if ($("unet_name")) {
        $("unet_name").value = resolveCombo($("unet_name").value, weightLists.models);
      }
      document.querySelectorAll(".lora-name").forEach((el) => {
        el.value = resolveCombo(el.value, weightLists.loras);
      });
      fillDatalist("unet-list", weightLists.models, $("unet_name") && $("unet_name").value);
      fillDatalist("lora-list", weightLists.loras);
      updateUnetWarn();
      const bits = [];
      if (r.source === "comfy") bits.push("from Comfy");
      if (weightLists.models.length) bits.push(weightLists.models.length + " UNETs");
      if (weightLists.loras.length) bits.push(weightLists.loras.length + " LoRAs");
      const err = (r.errors || []).join("; ");
      if (err && !bits.length) showBanner(err, "err");
      else showBanner((bits.join(", ") || "loaded") + (err ? " · " + err : ""), err && bits.length ? "warn" : "ok");
    } catch (e) {
      showBanner(e.message, "err");
    }
  };
}
$("save-settings").onclick = async () => {
  settings = await j("/api/settings", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(readSettings()),
  });
  fillSettings(settings);
  showBanner("settings saved", "ok");
  loadBooks();
};
$("test-comfy").onclick = async () => {
  const r = await j("/api/comfy/test");
  showBanner(r.message, r.ok ? "ok" : "err");
};
$("demo-cast").onclick = async () => {
  const r = await j("/api/demo/cast", { method: "POST" });
  book = r.book;
  renderCast();
};
$("add-char").onclick = async () => {
  try {
    const r = await j("/api/character/add", { method: "POST" });
    book = r.book;
    renderCast();
    showBanner("added " + (book.characters || []).slice(-1)[0]?.name, "ok");
  } catch (e) {
    showBanner(e.message, "err");
  }
};
$("save-book").onclick = async () => {
  await saveBookSilent();
  showBanner("book saved", "ok");
};
if ($("refresh-workflows")) {
  $("refresh-workflows").onclick = async () => {
    await fillWorkflowSelect();
    showBanner("workflow list refreshed", "ok");
  };
}
if ($("book-workflow")) {
  $("book-workflow").addEventListener("change", async () => {
    await saveBookSilent();
    showBanner(
      book.workflow ? "using " + book.workflow : "using Settings default workflow",
      "ok"
    );
  });
}
$("title").addEventListener("input", () => {
  book.title = $("title").value;
  showCurrentBook();
});
$("parse").onclick = async () => {
  await saveBookSilent();
  const r = await j("/api/parse", { method: "POST" });
  renderPreview(r.plates, r.warnings);
  if (r.notice) showBanner(r.notice, "warn");
  else if (!r.warnings.length) showBanner(`${r.plates.length} plates`, "ok");
};
$("demo-bos").onclick = async () => {
  const r = await j("/api/demo/bos", { method: "POST" });
  await loadBook();
  renderPreview(r.plates, r.warnings);
};
$("demo-t1").onclick = async () => {
  const r = await j("/api/demo/t1", { method: "POST" });
  await loadBook();
  renderPreview(r.plates, r.warnings);
};
$("copy-llm").onclick = async () => {
  const r = await j("/api/llm-sheet");
  await navigator.clipboard.writeText(r.text);
  showBanner("LLM sheet copied", "ok");
};
$("gen-missing").onclick = () => generate("missing");
$("gen-all").onclick = () => generate("all");
$("gen-sel").onclick = () => generate("sel");
$("slug-all").addEventListener("change", () => setAllSlugs($("slug-all").checked));
$("letter-all").onclick = async () => {
  showBanner("lettering all…", "ok");
  try {
    await withBusy($("letter-all"), "Lettering…", async () => {
      const r = await j("/api/letter", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
      });
      showBanner(`lettered ${r.lettered}, skipped ${r.skipped}`, "ok");
    });
  } catch (e) { showBanner(e.message, "err"); }
};
$("export").onclick = async () => {
  const r = await j("/api/export", { method: "POST" });
  showBanner(`export ${r.dir}`, "ok");
};
$("open-folder").onclick = async () => {
  const r = await j("/api/open-folder", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ which: "book" }),
  });
  showBanner(r.dir, r.ok ? "ok" : "err");
};
$("del-earlier").onclick = async () => {
  if (!confirm("Delete earlier versions and keep only the latest generate?\nThis cannot be undone.")) return;
  try {
    const r = await j("/api/plates/delete", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ confirm: true, scope: "earlier" }),
    });
    showBanner(`deleted ${r.deleted}`, "ok");
    refreshRuns();
  } catch (e) { showBanner(e.message, "err"); }
};
$("del-all-plates").onclick = async () => {
  if (!confirm("Delete ALL generated plates in this book?\nStory text and character stills stay. Images go.\nThis cannot be undone.")) return;
  try {
    const r = await j("/api/plates/delete", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ confirm: true, scope: "all" }),
    });
    showBanner(`deleted ${r.deleted}`, "ok");
    refreshRuns();
  } catch (e) { showBanner(e.message, "err"); }
};
async function startNewBook() {
  const title = prompt("New book title?", "Untitled");
  if (title == null || !title.trim()) return;
  try {
    const r = await j("/api/book/new", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title: title.trim() }),
    });
    book = r.book;
    $("title").value = book.title || "";
    $("prompts_raw").value = "";
    $("captions_raw").value = "";
    renderCast();
    renderPreview([], []);
    showBanner("new book " + ((r.book && r.book.id) || ""), "ok");
    loadBooks();
    setView("book");
  } catch (e) { showBanner(e.message, "err"); }
}
document.querySelectorAll(".js-new-book").forEach((el) => {
  el.onclick = startNewBook;
});
if ($("copy-plate-template")) {
  $("copy-plate-template").onclick = async () => {
    const pre = $("plate-template");
    const text = pre ? pre.textContent : "";
    try {
      await navigator.clipboard.writeText(text);
      showBanner("plate template copied", "ok");
    } catch (e) {
      showBanner(e.message, "err");
    }
  };
}

(async function init() {
  try {
    fillSettings(await j("/api/settings"));
    await loadBook();
    await loadBooks();
    const ping = await j("/api/comfy/test");
    showBanner(ping.message, ping.ok ? "ok" : "err");
  } catch (e) {
    showBanner(e.message, "err");
  }
})();
