import React, { useEffect, useState } from "react";
import { toast } from "sonner";
import { Bookmark, BookmarkPlus, Crown, X, Check, Loader2 } from "lucide-react";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { api } from "../lib/api";
import { t } from "../lib/i18n";

/** Keep only filters that differ from defaults so saved searches stay compact. */
export function compactFilters(filters, defaults) {
  const out = {};
  Object.entries(filters).forEach(([k, v]) => {
    const d = defaults[k];
    if (Array.isArray(v)) { if (v.length && JSON.stringify(v) !== JSON.stringify(d || [])) out[k] = v; return; }
    if (v === d || v === "" || v == null || v === false || v === "all") return;
    out[k] = v;
  });
  return out;
}

const sameFilters = (a, b) => {
  const ka = Object.keys(a).sort(), kb = Object.keys(b).sort();
  if (ka.join("|") !== kb.join("|")) return false;
  return ka.every(k => JSON.stringify(a[k]) === JSON.stringify(b[k]));
};

/**
 * Saved searches row (Premium / VIP). Tap a chip to apply its filters and search instantly.
 * Non-premium members see a locked teaser that links to the Premium upgrade.
 */
export default function SavedSearches({ lang, enabled, filters, defaults, onApply, onUpgrade }) {
  const [items, setItems] = useState([]);
  const [naming, setNaming] = useState(false);
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!enabled) return;
    api.get("/saved-searches").then(r => setItems(r.data || [])).catch(() => {});
  }, [enabled]);

  const current = compactFilters(filters, defaults);
  const hasAny = Object.keys(current).length > 0;

  const save = async () => {
    const n = name.trim();
    if (!n) return;
    setBusy(true);
    try {
      const { data } = await api.post("/saved-searches", { name: n, filters: current });
      setItems(list => [data, ...list]);
      setNaming(false); setName("");
      toast.success(t("saved_search_saved", lang).replace("{name}", data.name));
    } catch (e) {
      const d = e.response?.data?.detail || "";
      if (d.startsWith("SAVED_SEARCH_LIMIT:")) toast.error(t("saved_search_limit", lang).replace("{n}", d.split(":")[1]));
      else toast.error(t("failed", lang));
    } finally { setBusy(false); }
  };

  const remove = async (s) => {
    const prev = items;
    setItems(list => list.filter(x => x.id !== s.id));
    try { await api.delete(`/saved-searches/${s.id}`); toast.success(t("saved_search_deleted", lang)); }
    catch { setItems(prev); toast.error(t("failed", lang)); }
  };

  if (!enabled) {
    return (
      <div data-testid="saved-searches-locked" className="glass rounded-2xl px-4 py-3 mb-6 flex flex-wrap items-center gap-3">
        <Bookmark size={16} className="text-amber-300" />
        <span className="text-sm text-slate-300">{t("saved_searches", lang)}</span>
        <span className="text-xs text-slate-500">{t("saved_searches_locked", lang)}</span>
        <Button data-testid="saved-searches-upgrade" onClick={onUpgrade} variant="outline" className="ms-auto h-8 bg-amber-500/10 border-amber-500/30 text-amber-200 hover:bg-amber-500/20 text-xs">
          <Crown size={13} className="me-1" /> {t("buy_premium", lang)}
        </Button>
      </div>
    );
  }

  return (
    <div data-testid="saved-searches-bar" className="glass rounded-2xl px-4 py-3 mb-6 flex flex-wrap items-center gap-2">
      <span className="flex items-center gap-1.5 text-sm text-slate-300 me-1"><Bookmark size={15} className="text-rose-300" /> {t("saved_searches", lang)}</span>
      {items.length === 0 && !naming && <span data-testid="saved-searches-empty" className="text-xs text-slate-500">{t("no_saved_searches", lang)}</span>}
      {items.map(s => {
        const active = sameFilters(current, s.filters || {});
        return (
          <span key={s.id} data-testid={`saved-search-chip-${s.id}`}
            className={`group inline-flex items-center rounded-full border text-xs transition-colors ${active ? "bg-rose-500/25 border-rose-500/60 text-rose-100" : "bg-white/5 border-white/10 text-slate-200 hover:bg-white/10"}`}>
            <button type="button" data-testid="saved-search-apply" onClick={() => onApply(s.filters || {})} className="ps-3 pe-1.5 py-1.5 flex items-center gap-1">
              {active && <Check size={12} />} {s.name}
            </button>
            <button type="button" data-testid="saved-search-delete" aria-label="Delete" onClick={() => remove(s)} className="pe-2 ps-0.5 py-1.5 text-slate-500 hover:text-rose-300">
              <X size={12} />
            </button>
          </span>
        );
      })}
      <div className="ms-auto flex items-center gap-2">
        {naming ? (
          <>
            <Input data-testid="saved-search-name-input" autoFocus value={name} maxLength={40} placeholder={t("saved_search_name_ph", lang)}
              onChange={e => setName(e.target.value)}
              onKeyDown={e => { e.stopPropagation(); if (e.key === "Enter") save(); if (e.key === "Escape") { setNaming(false); setName(""); } }}
              className="h-8 w-48 bg-white/5 border-white/10 text-sm" />
            <Button data-testid="saved-search-confirm" onClick={save} disabled={busy || !name.trim()} className="h-8 rose-btn text-white border-0 text-xs">
              {busy ? <Loader2 size={13} className="animate-spin" /> : <Check size={13} className="me-1" />} {t("save", lang)}
            </Button>
            <Button data-testid="saved-search-cancel" variant="ghost" onClick={() => { setNaming(false); setName(""); }} className="h-8 text-slate-400 hover:text-white text-xs">{t("cancel", lang)}</Button>
          </>
        ) : (
          <Button data-testid="saved-search-save-button" onClick={() => setNaming(true)} disabled={!hasAny}
            title={!hasAny ? t("saved_search_pick_filters", lang) : undefined}
            variant="outline" className="h-8 bg-white/5 border-white/10 hover:bg-white/10 text-xs">
            <BookmarkPlus size={14} className="me-1" /> {t("save_search", lang)}
          </Button>
        )}
      </div>
    </div>
  );
}
