// GiftsDates — site-wide automatic translation into ANY world language.
// Translates every visible text node, placeholder, tooltip and aria-label on every page
// (including portals: dropdowns, dialogs, toasts, popovers) plus native confirm/alert/prompt.
// Translations come from POST /api/i18n/translate (AI, shared server cache) and are cached locally.
import { api } from "./api";

const ATTRS = ["placeholder", "title", "aria-label"];
const SKIP_TAGS = new Set(["SCRIPT", "STYLE", "NOSCRIPT", "CODE", "PRE", "TEXTAREA", "SVG", "PATH", "IFRAME", "CANVAS"]);
const HAS_LETTER = /\p{L}/u;
const LS_PREFIX = "gd_tr_v1_";

let lang = "en";
let cache = new Map();          // source -> translation (current lang)
const textRec = new WeakMap();  // TextNode -> { orig, applied }
const attrRec = new WeakMap();  // Element -> { [attr]: { orig, applied } }
const tracked = new Set();      // nodes/elements we've touched (for restore)
let queue = new Set();      // visible strings (high priority)
let preQueue = new Set();   // dictionary prefetch (low priority)
let timer = null;
let running = false;
let inflight = 0;
let observer = null;
let persistTimer = null;
const listeners = new Set();
const native = new Set();       // strings already rendered in the target language by t()
let ready = Promise.resolve();  // resolves when the pre-translated bundle is loaded

// Called by t() for curated/generated translations so they are not re-translated.
export function markNative(s, code) { if (s && code && code !== "en") native.add(code + "\u0001" + String(s).trim()); }

export const onTranslatingChange = (fn) => { listeners.add(fn); return () => listeners.delete(fn); };
const emit = () => { const busy = inflight > 0 || queue.size > 0; listeners.forEach(fn => fn(busy)); };

function loadCache(code) {
  try { return new Map(Object.entries(JSON.parse(localStorage.getItem(LS_PREFIX + code) || "{}"))); }
  catch { return new Map(); }
}
function persist() {
  clearTimeout(persistTimer);
  const code = lang, snapshot = cache;
  persistTimer = setTimeout(() => {
    try { localStorage.setItem(LS_PREFIX + code, JSON.stringify(Object.fromEntries(snapshot))); }
    catch { /* quota — keep in-memory only */ }
  }, 800);
}

function skipped(el) {
  if (!el || el.nodeType !== 1) return false;
  if (SKIP_TAGS.has(el.tagName.toUpperCase())) return true;
  return !!el.closest('[translate="no"],[data-no-translate],.notranslate,[contenteditable="true"]');
}
const translatable = (s) => s && s.length <= 800 && HAS_LETTER.test(s) && !native.has(lang + "\u0001" + s);

// Public: synchronous lookup used by t() and native dialogs. Queues unknown strings.
export function autoLookup(src, code = lang) {
  if (!src || code === "en" || code !== lang) return null;
  const key = String(src).trim();
  if (!translatable(key)) return null;
  const hit = cache.get(key);
  if (hit) return hit;
  enqueue(key);
  return null;
}

function enqueue(s) {
  if (lang === "en" || cache.has(s)) return;
  queue.add(s);
  clearTimeout(timer);
  timer = setTimeout(flush, 120);
  emit();
}

async function flush() {
  if (running) return;
  running = true;
  try {
    await ready;
    while (lang !== "en" && (queue.size || preQueue.size)) {
      const code = lang;
      const src = queue.size ? queue : preQueue;
      const batch = [];
      for (const s of src) { src.delete(s); if (!cache.has(s)) batch.push(s); if (batch.length >= 60) break; }
      if (!batch.length) continue;
      inflight++; emit();
      try {
        const { data } = await api.post("/i18n/translate", { lang: code, texts: batch });
        if (code !== lang) continue;
        (data.translations || []).forEach((tr, i) => { if (tr) cache.set(batch[i], tr); });
        persist();
        scan(document.body);
        if (document.title) translateTitle();
      } catch { /* offline / unavailable — leave originals */ }
      finally { inflight--; emit(); }
    }
  } finally {
    running = false;
    if (lang === "en") { queue.clear(); preQueue.clear(); }
    emit();
  }
}

function applyText(node) {
  const parent = node.parentElement;
  if (!parent || skipped(parent)) return;
  const cur = node.nodeValue;
  let rec = textRec.get(node);
  if (!rec || (cur !== rec.applied && cur !== rec.orig)) { rec = { orig: cur, applied: null }; textRec.set(node, rec); }
  const src = rec.orig;
  const key = src.trim();
  if (!translatable(key)) return;
  tracked.add(node);
  const tr = cache.get(key);
  if (!tr) { enqueue(key); return; }
  const lead = src.match(/^\s*/)[0], trail = src.match(/\s*$/)[0];
  const out = lead + tr + trail;
  rec.applied = out;
  if (node.nodeValue !== out) node.nodeValue = out;
}

function applyAttrs(el) {
  if (skipped(el)) return;
  const attrs = [...ATTRS];
  if (el.tagName === "INPUT" && ["button", "submit", "reset"].includes(el.type)) attrs.push("value");
  for (const a of attrs) {
    const cur = el.getAttribute(a);
    if (cur == null) continue;
    const recs = attrRec.get(el) || {};
    let r = recs[a];
    if (!r || (cur !== r.applied && cur !== r.orig)) { r = { orig: cur, applied: null }; recs[a] = r; attrRec.set(el, recs); }
    const key = r.orig.trim();
    if (!translatable(key)) continue;
    tracked.add(el);
    const tr = cache.get(key);
    if (!tr) { enqueue(key); continue; }
    r.applied = tr;
    if (cur !== tr) el.setAttribute(a, tr);
  }
}

function scan(root) {
  if (!root || lang === "en") return;
  if (root.nodeType === 3) { applyText(root); return; }
  if (root.nodeType !== 1 || skipped(root)) return;
  applyAttrs(root);
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_ELEMENT | NodeFilter.SHOW_TEXT, {
    acceptNode: (n) => (n.nodeType === 1 && skipped(n) ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT),
  });
  let n;
  while ((n = walker.nextNode())) { if (n.nodeType === 3) applyText(n); else applyAttrs(n); }
}

let origTitle = null;
function translateTitle() {
  if (origTitle == null || (document.title !== cache.get(origTitle) && document.title !== origTitle)) origTitle = document.title;
  const tr = autoLookup(origTitle);
  if (tr) document.title = tr;
}

function restoreAll() {
  tracked.forEach((n) => {
    if (n.nodeType === 3) { const r = textRec.get(n); if (r && n.nodeValue === r.applied) n.nodeValue = r.orig; }
    else { const recs = attrRec.get(n) || {}; Object.entries(recs).forEach(([a, r]) => { if (n.getAttribute(a) === r.applied) n.setAttribute(a, r.orig); }); }
  });
  tracked.clear();
  if (origTitle) document.title = origTitle;
}

function startObserver() {
  if (observer) return;
  observer = new MutationObserver((muts) => {
    if (lang === "en") return;
    for (const m of muts) {
      if (m.type === "characterData") applyText(m.target);
      else if (m.type === "attributes") applyAttrs(m.target);
      else m.addedNodes.forEach(scan);
    }
  });
  observer.observe(document.body, { subtree: true, childList: true, characterData: true, attributes: true, attributeFilter: [...ATTRS, "value"] });
}

// Native browser dialogs (warnings / confirmations) — translate from cache when possible.
let patched = false;
function patchDialogs() {
  if (patched) return; patched = true;
  const tx = (msg) => {
    if (lang === "en" || msg == null) return msg;
    return String(msg).split(/(\n+)/).map(part => (/^\n+$/.test(part) ? part : (autoLookup(part) || part))).join("");
  };
  const { alert, confirm, prompt } = window;
  window.alert = (m) => alert.call(window, tx(m));
  window.confirm = (m) => confirm.call(window, tx(m));
  window.prompt = (m, d) => prompt.call(window, tx(m), d);
}

// Prefetch whole dictionaries (all app strings, incl. warnings, coin purchase & withdrawal notices).
export function prefetch(strings) {
  if (lang === "en") return;
  strings.forEach((s) => { const k = String(s || "").trim(); if (translatable(k) && !cache.has(k)) preQueue.add(k); });
  clearTimeout(timer); timer = setTimeout(flush, 400);
}

export function setAutoLanguage(code) {
  code = code || "en";
  if (code === lang && observer) return;
  restoreAll();
  lang = code;
  queue = new Set();
  preQueue = new Set();
  cache = code === "en" ? new Map() : loadCache(code);
  if (code !== "en") {
    // Load everything pre-translated for this language in one request (instant first load).
    ready = api.get(`/i18n/bundle/${encodeURIComponent(code)}`).then(({ data }) => {
      if (code !== lang || !data?.translations) return;
      for (const [k, v] of Object.entries(data.translations)) cache.set(k, v);
      persist();
      scan(document.body); translateTitle();
    }).catch(() => {});
  } else ready = Promise.resolve();
  patchDialogs();
  startObserver();
  if (code !== "en") { scan(document.body); translateTitle(); }
  emit();
}

export const getAutoLanguage = () => lang;
