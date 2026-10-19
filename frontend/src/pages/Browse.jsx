import React, { useEffect, useState, useCallback } from "react";
import { Input } from "../components/ui/input";
import { Button } from "../components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { toast } from "sonner";
import { api } from "../lib/api";
import { useApp } from "../context/AppContext";
import { t } from "../lib/i18n";
import ProfileCard from "../components/ProfileCard";
import CountrySelect from "../components/CountrySelect";
import GiftModal from "../components/GiftModal";
import VideoCallModal from "../components/VideoCallModal";
import DateBookingModal from "../components/DateBookingModal";
import InviteDateModal from "../components/InviteDateModal";
import FeedBar from "../components/FeedBar";
import { Search, ChevronDown, ChevronLeft, ChevronRight, Crown, Lock } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { INTENTS, KIDS, HABITS, RELIGIONS, INCOMES, BUST, SIZES, GENDERS, ORIENTATIONS, optLabel } from "../components/ProfileDetailsForm";
import { VIP_CATEGORIES, catTitle, svcLabel } from "../lib/vipCatalog";
import { LANGUAGES, ZODIAC_EMOJI } from "../lib/i18n";
import { Switch } from "../components/ui/switch";
import CitySelect from "../components/CitySelect";
import MultiSelect from "../components/MultiSelect";
import SavedSearches from "../components/SavedSearches";
import RangeSlider from "../components/RangeSlider";
import * as SliderPrimitive from "@radix-ui/react-slider";
import { HOBBY_SELECT_GROUPS, HOBBY_MAX } from "../lib/hobbies";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "../components/ui/dialog";

const ALL = "all";
const RADII = [5, 10, 25, 50, 100, 250];
const VIP_EYE_COLORS = ["Brown", "Hazel", "Amber", "Green", "Blue", "Grey", "Black", "Heterochromia"];
const VIP_HAIR_COLORS = ["Black", "Dark brown", "Brown", "Light brown", "Blonde", "Platinum blonde", "Red", "Auburn", "Ginger", "Grey", "White", "Dyed / colourful"];
const VIP_HAIRCUTS = ["Fully shaved", "Trimmed", "Landing strip", "Bikini line", "Natural / full", "Triangle"];
const VIP_BREAST_SIZES = ["AA", "A", "B", "C", "D", "DD", "E", "F", "G", "H+", "Natural", "Enhanced"];
const EXTRA_DEFAULT = { intent: [], kids: [], smoking: [], drinking: [], religion: [], min_income: "", max_income: "", languages: [], bust_sizes: [], min_penis: "", max_penis: "", orientations: [], zodiac: [],
  min_height: "", max_height: "", min_weight: "", max_weight: "", hobbies: [], job: "", min_date_price: "", max_date_price: "", min_video_rate: "", max_video_rate: "", available_date: "", video_calls: false, premium_only: false, vip_only: false, with_photos: false, verified_only: false, online_now: false, video_now: false,
  vip_categories: [], vip_services: [], vip_min_price: "", vip_max_price: "", vip_date: "",
  vip_eye_color: ALL, vip_hair_color: ALL, vip_intimate_haircut: ALL, vip_breast_size: ALL,
  vip_min_height: "", vip_max_height: "", vip_min_weight: "", vip_max_weight: "",
  vip_min_dick: "", vip_max_dick: "", vip_min_girth: "", vip_max_girth: "",
  vip_price1h_min: "", vip_price1h_max: "", vip_price2h_min: "", vip_price2h_max: "", vip_price3h_min: "", vip_price3h_max: "" };

// Premium-Lite tier filters (looking for, distance, available on date, date price up to)
const LITE_DEFAULT = { intent: [], max_distance: "", available_date: "", min_date_price: "", max_date_price: "", min_video_rate: "", max_video_rate: "", video_calls: false, sort: "" };
// Full Premium filters = everything else in EXTRA_DEFAULT + search by name
const PREMIUM_DEFAULT = Object.fromEntries(Object.entries({ ...EXTRA_DEFAULT, q: "" }).filter(([k]) => !(k in LITE_DEFAULT)));

const INITIAL_FILTERS = { q: "", city: "", country: "", genders: [], min_age: 18, max_age: 60, max_distance: "", sort: "", ...EXTRA_DEFAULT };

const ZODIAC_SIGNS = ["aries", "taurus", "gemini", "cancer", "leo", "virgo", "libra", "scorpio", "sagittarius", "capricorn", "aquarius", "pisces"];

function FilterSelect({ testid, field, value, options, onChange, lang, label, labelFn }) {
  return (
    <div className="min-w-[150px]">
      <label className="text-xs text-slate-400">{label}</label>
      <Select value={value} onValueChange={onChange}>
        <SelectTrigger data-testid={testid} className="bg-white/5 border-white/10 mt-1"><SelectValue /></SelectTrigger>
        <SelectContent className="bg-[#161320] border-white/10 text-white max-h-72">
          <SelectItem value={ALL}>{t("all", lang)}</SelectItem>
          {options.map(o => <SelectItem key={o} value={o}>{labelFn ? labelFn(o) : optLabel(field, o, lang)}</SelectItem>)}
        </SelectContent>
      </Select>
    </div>
  );
}
function FilterMultiSelect({ testid, field, value, options, onChange, lang, label, labelFn }) {
  return (
    <div className="min-w-[200px]">
      <label className="text-xs text-slate-400">{label}</label>
      <div className="mt-1">
        <MultiSelect
          testid={testid}
          value={value}
          onChange={onChange}
          options={options.map(o => ({ value: o, label: labelFn ? labelFn(o) : optLabel(field, o, lang) }))}
          placeholder={t("all", lang)}
          searchPlaceholder={t("search", lang)}
          emptyText={t("no_results", lang)}
          accent="rose"
        />
      </div>
    </div>
  );
}
function NumInput({ testid, label, value, onChange, min, max }) {
  return (
    <div className="min-w-[100px]">
      <label className="text-xs text-slate-400">{label}</label>
      <Input data-testid={testid} type="number" min={min} max={max} value={value} onChange={e => onChange(e.target.value)} className="bg-white/5 border-white/10 mt-1" />
    </div>
  );
}
function Toggle({ testid, label, checked, onChange }) {
  return (
    <label className="flex items-center gap-2 text-xs text-slate-300 px-3 py-2 rounded-lg bg-white/5 border border-white/10 cursor-pointer">
      <Switch data-testid={testid} checked={checked} onCheckedChange={onChange} /> {label}
    </label>
  );
}

export default function Browse() {
  const { lang, user, meta } = useApp();
  const dateCoinsMin = meta?.date_min_coins || 150;
  const videoCoinsMin = meta?.video_rate || 10;
  const isPremium = user?.premium_until && new Date(user.premium_until) > new Date();
  const hasCoords = user?.lat != null && user?.lng != null;
  const isVip = user?.vip_until && new Date(user.vip_until) > new Date();
  const isPremiumFull = !!(isPremium || isVip);
  const isLite = !!(isPremiumFull || (user?.premium_lite_until && new Date(user.premium_lite_until) > new Date()));
  const nav = useNavigate();
  const [profiles, setProfiles] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filters, setFilters] = useState(INITIAL_FILTERS);
  const filtersRef = React.useRef(filters);
  filtersRef.current = filters;
  const [showMore, setShowMore] = useState(false);
  const [vipOpen, setVipOpen] = useState(false);
  const [target, setTarget] = useState(null);
  const [modal, setModal] = useState(null);
  const [quota, setQuota] = useState(null);
  const loadQuota = () => api.get("/likes/quota").then(r => setQuota(r.data)).catch(() => {});
  useEffect(() => { loadQuota(); }, []);

  const [pageInfo, setPageInfo] = useState({ page: 1, page_size: 2, has_more: false });
  const [slideDir, setSlideDir] = useState(""); // "next" | "prev" — drives the page-change slide animation
  const touchRef = React.useRef(null);
  const load = useCallback(async (pageArg, override) => {
    const filters = override || filtersRef.current; // override = filters from a saved search (state update is async)
    const pageNum = typeof pageArg === "number" ? pageArg : 1; // Search / Enter always restarts at page 1
    setLoading(true);
    try {
      const params = { ...filters, page: pageNum };
      if (Array.isArray(params.vip_categories)) { if (params.vip_categories.length) params.vip_categories = params.vip_categories.join(","); else delete params.vip_categories; }
      if (Array.isArray(params.vip_services)) { if (params.vip_services.length) params.vip_services = params.vip_services.join("||"); else delete params.vip_services; }
      if (Array.isArray(params.hobbies)) { if (params.hobbies.length) params.hobbies = params.hobbies.join("||"); else delete params.hobbies; }
      if (Array.isArray(params.bust_sizes)) { if (params.bust_sizes.length) params.bust_size = params.bust_sizes.join(","); delete params.bust_sizes; }
      if (Array.isArray(params.languages)) { if (params.languages.length) params.language = params.languages.join(","); delete params.languages; }
      if (Array.isArray(params.orientations)) { if (params.orientations.length) params.orientation = params.orientations.join(","); delete params.orientations; }
      if (Array.isArray(params.genders)) { if (params.genders.length) params.genders = params.genders.join(","); else delete params.genders; }
      if (Array.isArray(params.intent)) { if (params.intent.length) params.intent = params.intent.join(","); else delete params.intent; }
      ["kids", "smoking", "drinking", "religion", "zodiac"].forEach(k => {
        if (Array.isArray(params[k])) { if (params[k].length) params[k] = params[k].join(","); else delete params[k]; }
      });
      Object.keys(params).forEach(k => (params[k] === ALL || params[k] === "" || params[k] == null || params[k] === false) && delete params[k]);
      const { data } = await api.get("/profiles", { params });
      const items = Array.isArray(data) ? data : (data.items || []);
      setProfiles(items);
      if (!Array.isArray(data)) setPageInfo({ page: data.page, page_size: data.page_size, has_more: data.has_more });
      if (pageNum > 1) window.scrollTo({ top: 0, behavior: "smooth" });
    } catch (e) {
      if (e.response?.data?.detail === "VIP_REQUIRED") { toast.error(t("vip_filter_locked", lang), { action: { label: "VIP", onClick: () => nav("/wallet?premium=1") } }); setFilters(f => ({ ...f, vip_only: false })); }
      else if (e.response?.data?.detail === "PREMIUM_REQUIRED") { toast.error(t("premium_filters_locked", lang), { action: { label: t("premium", lang), onClick: () => nav("/wallet?premium=1") } }); setFilters(f => ({ ...f, ...PREMIUM_DEFAULT })); }
      else if (e.response?.data?.detail === "PREMIUM_LITE_REQUIRED") { toast.error(t("premium_lite_filters_locked", lang), { action: { label: "Premium-Lite", onClick: () => nav("/wallet?premium=1") } }); setFilters(f => ({ ...f, ...LITE_DEFAULT })); }
      else toast.error(t("failed_load", lang));
    }
    finally { setLoading(false); }
  }, [filters]); // eslint-disable-line react-hooks/exhaustive-deps

  // Run once on open; afterwards results refresh only when the Search button (or Enter) is pressed.
  useEffect(() => { load(); }, []); // eslint-disable-line react-hooks/exhaustive-deps
  const goPage = (dir) => {
    if (loading) return;
    if (dir === "next" && pageInfo.has_more) { setSlideDir("next"); load(pageInfo.page + 1); }
    else if (dir === "prev" && pageInfo.page > 1) { setSlideDir("prev"); load(pageInfo.page - 1); }
  };
  // Mobile swipe paging: swipe left -> next page, swipe right -> previous page
  const onTouchStart = (e) => { const t0 = e.touches[0]; touchRef.current = { x: t0.clientX, y: t0.clientY, time: Date.now() }; };
  const onTouchEnd = (e) => {
    const st = touchRef.current; touchRef.current = null;
    if (!st) return;
    const t1 = e.changedTouches[0];
    const dx = t1.clientX - st.x, dy = t1.clientY - st.y;
    if (Date.now() - st.time > 800 || Math.abs(dx) < 60 || Math.abs(dx) < Math.abs(dy) * 1.5) return; // ignore scrolls / slow drags
    goPage(dx < 0 ? "next" : "prev");
  };
  const onEnter = (e) => { if (e.key === "Enter" && e.target.tagName === "INPUT") load(1); };

  const like = async (p) => {
    try {
      const { data } = await api.post("/likes", { target_id: p.id });
      if (data.matched) toast.success(`💘 ${t("match", lang)} · ${p.name}`);
      else toast.success(`💗 ${t("like", lang)}: ${p.name}`);
      loadQuota();
    } catch (e) {
      const d = e.response?.data?.detail || "";
      if (d.startsWith("LIKE_LIMIT:")) toast.error(t("like_limit_reached", lang).replace("{n}", d.split(":")[1]), { duration: 6000, action: { label: t("premium", lang), onClick: () => nav("/wallet?premium=1") } });
      else toast.error(t("failed", lang));
    }
  };
  const open = (m, p) => { setTarget(p); setModal(m); };

  return (
    <div className="aurora-bg min-h-[calc(100vh-4rem)]">
      <div className="max-w-7xl mx-auto px-4 py-8">
        <FeedBar />
        <div className="glass rounded-2xl p-4 mb-6 flex flex-wrap gap-3 items-end" onKeyDown={onEnter}>
          <div className="min-w-[140px]">
            <label className="text-xs text-slate-400">{t("country", lang)}</label>
            <CountrySelect testid="profile-country-filter-select" value={filters.country} onChange={v => setFilters({ ...filters, country: v === "Global" ? "" : v })} lang={lang} placeholder={t("any_country", lang)} />
          </div>
          <div className="min-w-[160px]">
            <label className="text-xs text-slate-400">{t("city", lang)}</label>
            <CitySelect testid="profile-city-filter-select" value={filters.city} onChange={v => setFilters({ ...filters, city: v })} country={filters.country} lang={lang} />
          </div>
          <div className="min-w-[180px]">
            <label className="text-xs text-slate-400">{t("gender", lang)}</label>
            <div className="mt-1">
              <MultiSelect
                testid="profile-gender-filter-select"
                value={filters.genders}
                onChange={v => setFilters({ ...filters, genders: v })}
                options={GENDERS.map(g => ({ value: g, label: t(g, lang) }))}
                placeholder={t("all", lang)}
                searchPlaceholder={t("search_placeholder", lang)}
                emptyText={t("no_results", lang)}
                accent="rose"
              />
            </div>
          </div>
          <div className="min-w-[240px] flex-1 max-w-[320px] pb-0.5">
            <RangeSlider testid="profile-age-range" label={t("age", lang)} min={18} max={99} lo={filters.min_age} hi={filters.max_age} anyLabel={`18 – 99+`}
              onChange={(a, b) => setFilters(f => ({ ...f, min_age: a === "" ? 18 : parseInt(a), max_age: b === "" ? 99 : parseInt(b) }))} />
          </div>
          <Button data-testid="profile-search-submit-button" onClick={() => { setSlideDir(""); load(1); }} disabled={loading} className="rose-btn text-white border-0 px-6"><Search size={15} className="me-1"/> {t("search_btn", lang)}</Button>
          <label className="flex items-center gap-2 text-xs text-red-200 px-3 py-2 rounded-lg bg-red-500/10 border border-red-500/30 cursor-pointer h-[38px]" data-testid="main-vip-only-wrap">
            <Switch data-testid="main-filter-vip-only" checked={filters.vip_only} onCheckedChange={v => {
              setFilters({ ...filters, vip_only: v });
              if (v) { if (isVip) setVipOpen(true); else { toast.error(t("vip_search_locked", lang)); nav("/wallet?vip=1"); } }
            }} /> ♛ {t("vip_only", lang)}
          </label>
          {isVip && filters.vip_only && (
            <Button data-testid="vip-private-search-open" onClick={() => setVipOpen(true)} variant="outline" className="h-[38px] bg-red-500/10 border-red-500/40 text-red-200 hover:bg-red-500/20">
              <Crown size={14} className="me-1 fill-red-500 text-red-500" /> {t("vip_private_search", lang)}
            </Button>
          )}
          <Button data-testid="profile-more-filters-toggle" onClick={() => setShowMore(!showMore)} variant="outline" className={`bg-white/5 border-white/10 hover:bg-white/10 ${!isLite ? "text-amber-300 border-amber-500/30" : ""}`}><ChevronDown size={14} className={`me-1 transition-transform ${showMore ? "rotate-180" : ""}`}/>{!isLite && <Crown size={14} className="me-1 text-amber-300"/>} {t("more_filters", lang)}</Button>
          {quota && !quota.premium && (
            <button data-testid="likes-quota-badge" onClick={() => nav("/wallet?premium=1")} className={`ms-auto px-3 py-2 rounded-full text-xs border font-mono-num ${quota.remaining === 0 ? "bg-rose-500/15 border-rose-500/40 text-rose-300" : "bg-white/5 border-white/10 text-slate-300"}`}>
              💗 {t("likes_left", lang).replace("{a}", quota.used).replace("{b}", quota.limit)}
            </button>
          )}
        </div>
        <SavedSearches
          lang={lang}
          enabled={isPremiumFull}
          filters={filters}
          defaults={INITIAL_FILTERS}
          onUpgrade={() => nav("/wallet?premium=1")}
          onApply={(saved) => { const merged = { ...INITIAL_FILTERS, ...saved }; setFilters(merged); setSlideDir(""); load(1, merged); }}
        />
        {showMore && (
          <div className="glass rounded-2xl p-4 mb-6 space-y-5 float-in" data-testid="profile-more-filters-panel" onKeyDown={onEnter}>
            {/* ---------- Premium-Lite filters ---------- */}
            <section data-testid="premium-lite-filters-section" className="space-y-3">
              <div className="flex items-center gap-2 text-sm font-semibold text-sky-300"><Crown size={14} className="text-sky-300" /> {t("premium_lite_filters", lang)}</div>
              {!isLite && (
                <div data-testid="premium-lite-filters-lock" className="rounded-xl border border-sky-500/30 bg-sky-500/10 p-3 flex flex-wrap items-center gap-3">
                  <div className="w-9 h-9 rounded-lg bg-sky-500/15 border border-sky-500/30 flex items-center justify-center shrink-0"><Lock size={16} className="text-sky-300" /></div>
                  <div className="flex-1 min-w-[200px] font-serif-luxe text-base">{t("premium_lite_filters_locked", lang)}</div>
                  <Button data-testid="premium-lite-filters-get" onClick={() => nav("/wallet?premium=1")} className="rose-btn text-white border-0 h-10"><Crown size={16} className="me-1" /> {t("buy_premium_lite", lang)}</Button>
                </div>
              )}
              <fieldset disabled={!isLite} data-testid="premium-lite-filters-controls" className={`border-0 p-0 m-0 min-w-0 ${!isLite ? "opacity-60 select-none" : ""}`}>
                <div className="flex flex-wrap gap-3 items-end">
                  <div className="min-w-[220px]">
                    <label className="text-xs text-slate-400">{t("relationship_intent", lang)}</label>
                    <div className="mt-1">
                      <MultiSelect
                        testid="filter-intent-select"
                        value={filters.intent}
                        onChange={v => setFilters({ ...filters, intent: v })}
                        options={INTENTS.map(o => ({ value: o, label: optLabel("relationship_intent", o, lang) }))}
                        placeholder={t("all", lang)}
                        searchPlaceholder={t("search", lang)}
                        emptyText={t("no_results", lang)}
                        accent="rose"
                      />
                    </div>
                  </div>
                  <div className="min-w-[230px] flex-1 max-w-[340px] pb-0.5" title={!hasCoords ? t("location_needed_for_distance", lang) : undefined}>
                    <div className="flex items-center justify-between text-xs">
                      <span className="text-slate-400">{t("distance_label", lang)}</span>
                      <span data-testid="profile-distance-filter-value" className={`font-mono-num ${filters.max_distance ? "text-rose-200" : "text-slate-500"}`}>
                        {filters.max_distance ? t("within_km", lang).replace("{n}", filters.max_distance) : t("any_distance", lang)}
                      </span>
                    </div>
                    <SliderPrimitive.Root
                      data-testid="profile-distance-filter-slider"
                      className="relative flex w-full touch-none select-none items-center h-9 mt-1 data-[disabled]:opacity-50"
                      min={0} max={1000} step={5}
                      value={[filters.max_distance ? Number(filters.max_distance) : 0]}
                      disabled={!isLite || !hasCoords}
                      onValueChange={([v]) => setFilters({ ...filters, max_distance: v <= 0 ? "" : v })}
                    >
                      <SliderPrimitive.Track className="relative h-1.5 w-full grow overflow-hidden rounded-full bg-white/10">
                        <SliderPrimitive.Range className="absolute h-full bg-gradient-to-r from-rose-500 to-rose-400" />
                      </SliderPrimitive.Track>
                      <SliderPrimitive.Thumb data-testid="profile-distance-filter-thumb" aria-label={t("distance_label", lang)}
                        className="block h-5 w-5 rounded-full border-2 border-rose-400 bg-[#161320] shadow-[0_0_0_4px_rgba(244,63,94,0.15)] transition-[box-shadow,background-color] hover:bg-rose-500/30 focus-visible:outline-none focus-visible:shadow-[0_0_0_6px_rgba(244,63,94,0.3)] cursor-grab active:cursor-grabbing" />
                    </SliderPrimitive.Root>
                  </div>
                  <div className="min-w-[150px]"><label className="text-xs text-slate-400">{t("available_on_date", lang)}</label>
                    <Input data-testid="filter-available-date-input" type="date" value={filters.available_date} onChange={e => setFilters({ ...filters, available_date: e.target.value })} className="bg-white/5 border-white/10 mt-1" /></div>
                  <RangeSlider testid="filter-date-coins-range" label={t("max_date_price", lang)} min={dateCoinsMin} max={5000} step={50} disabled={!isLite}
                    lo={filters.min_date_price} hi={filters.max_date_price} anyLabel={t("all", lang)} format={(v) => `🪙 ${v}`}
                    onChange={(a, b) => setFilters(f => ({ ...f, min_date_price: a, max_date_price: b }))} />
                  <RangeSlider testid="filter-video-coins-range" label={t("video_price", lang)} min={videoCoinsMin} max={200} step={5} disabled={!isLite}
                    lo={filters.min_video_rate} hi={filters.max_video_rate} anyLabel={t("all", lang)} format={(v) => `🪙 ${v}`}
                    onChange={(a, b) => setFilters(f => ({ ...f, min_video_rate: a, max_video_rate: b }))} />
                <div className="min-w-[240px]">
                  <label className="text-xs text-slate-400">{t("sort_by", lang)}</label>
                  <Select disabled={!isLite} value={filters.sort || "recommended"} onValueChange={v => {
                    const next = { ...filtersRef.current, sort: v === "recommended" ? "" : v };
                    setFilters(next); setSlideDir(""); load(1, next);
                  }}>
                    <SelectTrigger data-testid="profile-sort-select" className="bg-white/5 border-white/10 mt-1"><SelectValue /></SelectTrigger>
                    <SelectContent className="bg-[#161320] border-white/10 text-slate-100">
                      <SelectItem value="recommended" data-testid="sort-option-recommended">{t("sort_recommended", lang)}</SelectItem>
                      <SelectItem value="coins_asc" data-testid="sort-option-coins-asc">🪙 {t("sort_coins_asc", lang)}</SelectItem>
                      <SelectItem value="coins_desc" data-testid="sort-option-coins-desc">🪙 {t("sort_coins_desc", lang)}</SelectItem>
                      <SelectItem value="video_asc" data-testid="sort-option-video-asc">📹 {t("sort_video_asc", lang)}</SelectItem>
                      <SelectItem value="video_desc" data-testid="sort-option-video-desc">📹 {t("sort_video_desc", lang)}</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                  <Toggle testid="filter-video-calls" label={`📹 ${t("video_calls_available", lang)}`} checked={filters.video_calls} onChange={v => setFilters({ ...filters, video_calls: v })} />
                  {isLite && <Button data-testid="premium-lite-filters-reset" variant="ghost" onClick={() => setFilters({ ...filters, ...LITE_DEFAULT })} className="text-slate-400 hover:text-white ms-auto">{t("reset", lang)}</Button>}
                </div>
              </fieldset>
            </section>

            <div className="h-px bg-white/10" />

            {/* ---------- Full Premium filters ---------- */}
            <section data-testid="premium-filters-section" className="space-y-3">
              <div className="flex items-center gap-2 text-sm font-semibold text-amber-300"><Crown size={14} className="text-amber-300" /> {t("premium_filters_title", lang)}</div>
              {!isPremiumFull && (
                <div data-testid="profile-filters-premium-lock" className="rounded-xl border border-amber-500/30 bg-amber-500/10 p-3 flex flex-wrap items-center gap-3">
                  <div className="w-9 h-9 rounded-lg bg-amber-500/15 border border-amber-500/30 flex items-center justify-center shrink-0"><Lock size={16} className="text-amber-300" /></div>
                  <div className="flex-1 min-w-[200px]">
                    <div className="font-serif-luxe text-base">{t("premium_filters_locked", lang)}</div>
                    <div className="text-xs text-slate-400">{t("premium_perks_short", lang)}</div>
                  </div>
                  <Button data-testid="profile-filters-get-premium" onClick={() => nav("/wallet?premium=1")} className="rose-btn text-white border-0 h-10"><Crown size={16} className="me-1" /> {t("buy_premium", lang)}</Button>
                </div>
              )}
              <fieldset disabled={!isPremiumFull} data-testid="profile-more-filters-controls" className={`space-y-3 border-0 p-0 m-0 min-w-0 ${!isPremiumFull ? "opacity-60 select-none" : ""}`}>
              <div className="flex flex-wrap gap-3 items-end">
                <div className="flex-1 min-w-[220px]">
                  <label className="text-xs text-slate-400 flex items-center gap-1"><Search size={12}/> {t("search_by_name", lang)}</label>
                  <Input data-testid="profile-search-input" value={filters.q} onChange={e => setFilters({ ...filters, q: e.target.value })} className="bg-white/5 border-white/10 mt-1" />
                </div>
                <div className="min-w-[200px]">
                  <label className="text-xs text-slate-400">{t("orientation", lang)}</label>
                  <div className="mt-1">
                    <MultiSelect
                      testid="filter-orientation-select"
                      value={filters.orientations}
                      onChange={v => setFilters({ ...filters, orientations: v })}
                      options={ORIENTATIONS.filter(o => o !== "prefer_not").map(o => ({ value: o, label: optLabel("orientation", o, lang) }))}
                      placeholder={t("all", lang)}
                      searchPlaceholder={t("search", lang)}
                      emptyText={t("no_results", lang)}
                      accent="rose"
                    />
                  </div>
                </div>
                <FilterMultiSelect testid="filter-kids-select" field="kids" label={t("kids", lang)} value={filters.kids} options={KIDS} onChange={v => setFilters({ ...filters, kids: v })} lang={lang} />
                <FilterMultiSelect testid="filter-smoking-select" field="smoking" label={t("smoking", lang)} value={filters.smoking} options={HABITS} onChange={v => setFilters({ ...filters, smoking: v })} lang={lang} />
                <FilterMultiSelect testid="filter-drinking-select" field="drinking" label={t("drinking", lang)} value={filters.drinking} options={HABITS} onChange={v => setFilters({ ...filters, drinking: v })} lang={lang} />
                <FilterMultiSelect testid="filter-religion-select" field="religion" label={t("religion", lang)} value={filters.religion} options={RELIGIONS.filter(r => r !== "prefer_not")} onChange={v => setFilters({ ...filters, religion: v })} lang={lang} />
                <RangeSlider testid="filter-income-range" label={`${t("income", lang)} $/month`} min={0} max={50000} step={500} lo={filters.min_income} hi={filters.max_income} anyLabel={t("all", lang)}
                  format={v => `$${v >= 1000 ? (v / 1000).toLocaleString("en-US", { maximumFractionDigits: 1 }) + "k" : v}`}
                  onChange={(a, b) => setFilters(f => ({ ...f, min_income: a, max_income: b }))} />
                <div className="min-w-[200px]">
                  <label className="text-xs text-slate-400">{t("language_filter", lang)}</label>
                  <div className="mt-1">
                    <MultiSelect
                      testid="filter-language-select"
                      value={filters.languages}
                      onChange={v => setFilters({ ...filters, languages: v })}
                      options={LANGUAGES.map(l => ({ value: l.code, label: `${l.flag} ${l.name}` }))}
                      placeholder={t("all", lang)}
                      searchPlaceholder={t("search", lang)}
                      emptyText={t("no_results", lang)}
                      accent="rose"
                    />
                  </div>
                </div>
                <FilterMultiSelect testid="filter-zodiac-select" field="zodiac" label={t("zodiac", lang)} value={filters.zodiac} options={ZODIAC_SIGNS} labelFn={z => `${ZODIAC_EMOJI[z] || ""} ${t("zod_" + z, lang)}`} onChange={v => setFilters({ ...filters, zodiac: v })} lang={lang} />
              </div>
              <div className="flex flex-wrap gap-3 items-end">
                <RangeSlider testid="filter-height-range" label={t("height", lang)} min={100} max={250} lo={filters.min_height} hi={filters.max_height} anyLabel={t("all", lang)} onChange={(a, b) => setFilters(f => ({ ...f, min_height: a, max_height: b }))} />
                <RangeSlider testid="filter-weight-range" label={t("weight", lang)} min={30} max={300} lo={filters.min_weight} hi={filters.max_weight} anyLabel={t("all", lang)} onChange={(a, b) => setFilters(f => ({ ...f, min_weight: a, max_weight: b }))} />
                <div className="min-w-[220px]">
                  <label className="text-xs text-slate-400 flex justify-between gap-2"><span>{t("hobbies", lang)}</span><span data-testid="filter-hobby-count" className="font-mono-num text-slate-500">{filters.hobbies.length}/{HOBBY_MAX}</span></label>
                  <div className="mt-1">
                    <MultiSelect testid="filter-hobby-select" value={filters.hobbies} onChange={v => { if (v.length > HOBBY_MAX) { toast.error(t("hobby_filter_max", lang).replace("{n}", HOBBY_MAX)); return; } setFilters({ ...filters, hobbies: v }); }}
                      groups={HOBBY_SELECT_GROUPS} placeholder={t("all", lang)} searchPlaceholder={t("search", lang)} emptyText={t("no_results", lang)} accent="rose" />
                  </div>
                </div>
                <div className="min-w-[150px]"><label className="text-xs text-slate-400">{t("job_title", lang)}</label>
                  <Input data-testid="filter-job-input" value={filters.job} onChange={e => setFilters({ ...filters, job: e.target.value })} className="bg-white/5 border-white/10 mt-1" /></div>
                {(filters.genders.length === 0 || filters.genders.some(g => g !== "male")) && (
                  <div className="min-w-[200px]">
                    <label className="text-xs text-slate-400">{t("bust_size", lang)}</label>
                    <div className="mt-1">
                      <MultiSelect testid="filter-bust-select" value={filters.bust_sizes} onChange={v => setFilters({ ...filters, bust_sizes: v })}
                        options={BUST.map(b => ({ value: b, label: optLabel("bust_size", b, lang) }))}
                        placeholder={t("all", lang)} searchPlaceholder={t("search", lang)} emptyText={t("no_results", lang)} accent="rose" />
                    </div>
                  </div>
                )}
                {(filters.genders.length === 0 || filters.genders.some(g => g !== "female")) && (<>
                  <RangeSlider testid="filter-penis-range" label={t("penis_size", lang)} min={5} max={30} lo={filters.min_penis} hi={filters.max_penis} anyLabel={t("all", lang)} onChange={(a, b) => setFilters(f => ({ ...f, min_penis: a, max_penis: b }))} />
                </>)}
              </div>
              {/* VIP private search is available as a popup — press the "VIP only" switch above */}
              <div className="flex flex-wrap gap-2 items-center">
                <Toggle testid="filter-premium-only" label={`👑 ${t("premium_only", lang)}`} checked={filters.premium_only} onChange={v => setFilters({ ...filters, premium_only: v })} />
                <Toggle testid="filter-online-now" label={`🟢 ${t("online_now", lang)}`} checked={filters.online_now} onChange={v => setFilters({ ...filters, online_now: v })} />
                <Toggle testid="filter-video-now" label={`📹 ${t("video_now", lang)}`} checked={filters.video_now} onChange={v => setFilters({ ...filters, video_now: v })} />
                <Toggle testid="filter-with-photos" label={`📷 ${t("with_photos", lang)}`} checked={filters.with_photos} onChange={v => setFilters({ ...filters, with_photos: v })} />
                <Toggle testid="filter-verified-only" label={`✅ ${t("verified_only", lang)}`} checked={filters.verified_only} onChange={v => setFilters({ ...filters, verified_only: v })} />
                {isPremiumFull && <Button data-testid="profile-filters-reset-button" variant="ghost" onClick={() => setFilters({ ...filters, ...PREMIUM_DEFAULT })} className="text-slate-400 hover:text-white ms-auto">{t("reset", lang)}</Button>}
              </div>
              </fieldset>
            </section>
            <div className="flex justify-end pt-1">
              <Button data-testid="more-filters-search-button" onClick={() => { setSlideDir(""); load(1); }} disabled={loading} className="rose-btn text-white border-0 px-8 h-11"><Search size={16} className="me-1.5"/> {t("search_btn", lang)}</Button>
            </div>
          </div>
        )}

        {loading ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-5">
            {Array.from({ length: 8 }).map((_, i) => <div key={i} className="rounded-3xl bg-white/5 h-96 animate-pulse" />)}
          </div>
        ) : profiles.length === 0 ? (
          <div className="text-center py-24 text-slate-400" data-testid="browse-empty">{t("no_profiles", lang)}</div>
        ) : (
          <div data-testid="browse-results-grid" onTouchStart={onTouchStart} onTouchEnd={onTouchEnd}
            key={`page-${pageInfo.page}`}
            className={`grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-5 touch-pan-y ${slideDir === "next" ? "slide-in-next" : slideDir === "prev" ? "slide-in-prev" : ""}`}>
            {profiles.map(p => <ProfileCard key={p.id} p={p} onOpen={(p) => nav(`/profile/${p.id}`)} onLike={like} onGift={(p)=>open("gift",p)} onVideo={(p)=>open("video",p)} onDate={(p)=>open("date",p)} onMessage={()=>nav("/chats")} />)}
          </div>
        )}
        {!loading && (profiles.length > 0 || pageInfo.page > 1) && (
          <div data-testid="browse-pagination" className="glass rounded-2xl mt-6 max-sm:mb-20 p-3 flex flex-wrap items-center justify-between gap-3">
            <div className="text-xs text-slate-400" data-testid="browse-page-size-info">
              {t("per_page_info", lang).replace("{n}", pageInfo.page_size)}
              {!isVip && (
                <button type="button" data-testid="browse-upgrade-more-results" onClick={() => nav("/wallet?premium=1")} className="ms-2 text-amber-300 hover:text-amber-200 underline-offset-2 hover:underline">
                  <Crown size={12} className="inline me-1 -mt-0.5" />{t("upgrade_more_results", lang)}
                </button>
              )}
            </div>
            <div data-testid="browse-swipe-hint" className="w-full sm:hidden flex items-center justify-center gap-1.5 text-[11px] text-slate-500 order-first">
              <ChevronLeft size={12} /> {t("swipe_to_change_page", lang)} <ChevronRight size={12} />
            </div>
            <div className="flex items-center gap-2 max-sm:w-full max-sm:justify-between">
              <Button data-testid="browse-prev-page" variant="outline" disabled={pageInfo.page <= 1} onClick={() => goPage("prev")} className="bg-white/5 border-white/10 hover:bg-white/10 h-9">
                <ChevronLeft size={16} className="me-1" /> {t("prev_page", lang)}
              </Button>
              <span data-testid="browse-page-indicator" className="text-sm text-slate-300 font-mono-num px-2">{t("page_label", lang)} {pageInfo.page}</span>
              <Button data-testid="browse-next-page" disabled={!pageInfo.has_more} onClick={() => goPage("next")} className="rose-btn text-white border-0 h-9">
                {t("next_page", lang)} <ChevronRight size={16} className="ms-1" />
              </Button>
            </div>
          </div>
        )}
      </div>

      <GiftModal open={modal==="gift"} onOpenChange={(v)=>!v&&setModal(null)} target={target}/>
      <VideoCallModal open={modal==="video"} onOpenChange={(v)=>!v&&setModal(null)} target={target}/>
      <InviteDateModal open={modal==="date"} onOpenChange={(v)=>!v&&setModal(null)} target={target}/>

      <Dialog open={vipOpen} onOpenChange={setVipOpen}>
        <DialogContent data-testid="vip-private-search-dialog" className="bg-[#161320] border-red-500/30 text-white max-w-3xl max-h-[88vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-red-200"><Crown size={18} className="fill-red-500 text-red-500" /> {t("vip_private_search", lang)}</DialogTitle>
            <DialogDescription className="text-slate-400">{t("vip_private_search_desc", lang)}</DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <div className="text-xs font-semibold text-red-300/90">{t("vip_services", lang)}</div>
              {filters.vip_services.length > 0 && (
                <button type="button" data-testid="vip-services-clear" onClick={() => setFilters(f => ({ ...f, vip_services: [] }))} className="text-[11px] text-slate-400 hover:text-white">{t("reset", lang)} ({filters.vip_services.length})</button>
              )}
            </div>
            <div className="space-y-3 rounded-xl border border-white/10 bg-black/20 p-3">
              {VIP_CATEGORIES.map(c => {
                const allSel = c.items.every(s => filters.vip_services.includes(s));
                return (
                  <div key={c.key} data-testid={`vip-svc-group-${c.key}`}>
                    <button type="button" data-testid={`vip-svc-selectall-${c.key}`}
                      onClick={() => setFilters(f => ({ ...f, vip_services: allSel ? f.vip_services.filter(x => !c.items.includes(x)) : [...new Set([...f.vip_services, ...c.items])] }))}
                      className="text-xs font-semibold text-red-300 mb-1.5 flex items-center gap-1.5 hover:text-red-200">
                      <span className={`inline-block w-3 h-3 rounded-sm border ${allSel ? "bg-red-500 border-red-500" : "border-red-400/50"}`} /> {catTitle(c.key, lang)}
                    </button>
                    <div className="flex flex-wrap gap-1.5">
                      {c.items.map(s => (
                        <button key={s} type="button"
                          onClick={() => setFilters(f => ({ ...f, vip_services: f.vip_services.includes(s) ? f.vip_services.filter(x => x !== s) : [...f.vip_services, s] }))}
                          className={`text-[11px] px-2.5 py-1 rounded-full border transition-colors ${filters.vip_services.includes(s) ? "bg-red-500/25 border-red-500/60 text-red-100" : "bg-white/5 border-white/10 text-slate-300 hover:bg-white/10"}`}>{svcLabel(s, lang)}</button>
                      ))}
                    </div>
                  </div>
                );
              })}
            </div>
            <div className="flex flex-wrap gap-3 items-end">
              <div className="min-w-[150px]"><label className="text-xs text-slate-400">{t("vip_availability", lang)}</label>
                <Input data-testid="vip-filter-date" type="date" value={filters.vip_date} onChange={e => setFilters({ ...filters, vip_date: e.target.value })} className="bg-white/5 border-white/10 mt-1" /></div>
            </div>
            <div className="text-xs font-semibold text-red-300/90 pt-1">{t("vip_price_by_duration", lang)}</div>
            <div className="grid grid-cols-2 sm:grid-cols-6 gap-3 items-end">
              <NumInput testid="vip-filter-price1h-min" label={`${t("vip_price_1h", lang)} · ${t("min", lang)}`} min="0" value={filters.vip_price1h_min} onChange={v => setFilters({ ...filters, vip_price1h_min: v })} />
              <NumInput testid="vip-filter-price1h-max" label={`${t("vip_price_1h", lang)} · ${t("max", lang)}`} min="0" value={filters.vip_price1h_max} onChange={v => setFilters({ ...filters, vip_price1h_max: v })} />
              <NumInput testid="vip-filter-price2h-min" label={`${t("vip_price_2h", lang)} · ${t("min", lang)}`} min="0" value={filters.vip_price2h_min} onChange={v => setFilters({ ...filters, vip_price2h_min: v })} />
              <NumInput testid="vip-filter-price2h-max" label={`${t("vip_price_2h", lang)} · ${t("max", lang)}`} min="0" value={filters.vip_price2h_max} onChange={v => setFilters({ ...filters, vip_price2h_max: v })} />
              <NumInput testid="vip-filter-price3h-min" label={`${t("vip_price_3h", lang)} · ${t("min", lang)}`} min="0" value={filters.vip_price3h_min} onChange={v => setFilters({ ...filters, vip_price3h_min: v })} />
              <NumInput testid="vip-filter-price3h-max" label={`${t("vip_price_3h", lang)} · ${t("max", lang)}`} min="0" value={filters.vip_price3h_max} onChange={v => setFilters({ ...filters, vip_price3h_max: v })} />
            </div>
            <div className="text-xs font-semibold text-red-300/90 pt-1">{t("vip_appearance", lang)}</div>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              <FilterSelect testid="vip-filter-hair" field="vip_hair_color" label={t("vip_hair_color", lang)} value={filters.vip_hair_color} options={VIP_HAIR_COLORS} labelFn={o => o} onChange={v => setFilters({ ...filters, vip_hair_color: v })} lang={lang} />
              <FilterSelect testid="vip-filter-eye" field="vip_eye_color" label={t("vip_eye_color", lang)} value={filters.vip_eye_color} options={VIP_EYE_COLORS} labelFn={o => o} onChange={v => setFilters({ ...filters, vip_eye_color: v })} lang={lang} />
              <FilterSelect testid="vip-filter-haircut" field="vip_intimate_haircut" label={t("vip_intimate_haircut", lang)} value={filters.vip_intimate_haircut} options={VIP_HAIRCUTS} labelFn={o => o} onChange={v => setFilters({ ...filters, vip_intimate_haircut: v })} lang={lang} />
              <FilterSelect testid="vip-filter-breast" field="vip_breast_size" label={t("vip_breast_size", lang)} value={filters.vip_breast_size} options={VIP_BREAST_SIZES} labelFn={o => o} onChange={v => setFilters({ ...filters, vip_breast_size: v })} lang={lang} />
            </div>
            <div className="flex flex-wrap gap-6 items-end">
              <RangeSlider testid="vip-filter-height-range" label={t("height", lang)} min={100} max={250} lo={filters.vip_min_height} hi={filters.vip_max_height} anyLabel={t("all", lang)} onChange={(a, b) => setFilters(f => ({ ...f, vip_min_height: a, vip_max_height: b }))} />
              <RangeSlider testid="vip-filter-weight-range" label={t("weight", lang)} min={30} max={400} lo={filters.vip_min_weight} hi={filters.vip_max_weight} anyLabel={t("all", lang)} onChange={(a, b) => setFilters(f => ({ ...f, vip_min_weight: a, vip_max_weight: b }))} />
            </div>
            {(filters.genders.length === 0 || filters.genders.some(g => g !== "female")) && (
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 items-end">
                <NumInput testid="vip-filter-min-dick" label={`${t("vip_dick_size", lang)} · ${t("min", lang)}`} min="0" max="40" value={filters.vip_min_dick} onChange={v => setFilters({ ...filters, vip_min_dick: v })} />
                <NumInput testid="vip-filter-max-dick" label={`${t("vip_dick_size", lang)} · ${t("max", lang)}`} min="0" max="40" value={filters.vip_max_dick} onChange={v => setFilters({ ...filters, vip_max_dick: v })} />
                <NumInput testid="vip-filter-min-girth" label={`${t("vip_dick_girth", lang)} · ${t("min", lang)}`} min="0" max="30" value={filters.vip_min_girth} onChange={v => setFilters({ ...filters, vip_min_girth: v })} />
                <NumInput testid="vip-filter-max-girth" label={`${t("vip_dick_girth", lang)} · ${t("max", lang)}`} min="0" max="30" value={filters.vip_max_girth} onChange={v => setFilters({ ...filters, vip_max_girth: v })} />
              </div>
            )}
          </div>
          <DialogFooter className="gap-2">
            <Button data-testid="vip-private-search-reset" variant="ghost" onClick={() => setFilters({ ...filters,
              vip_categories: [], vip_services: [], vip_min_price: "", vip_max_price: "", vip_date: "",
              vip_eye_color: ALL, vip_hair_color: ALL, vip_intimate_haircut: ALL, vip_breast_size: ALL,
              vip_min_height: "", vip_max_height: "", vip_min_weight: "", vip_max_weight: "",
              vip_min_dick: "", vip_max_dick: "", vip_min_girth: "", vip_max_girth: "",
              vip_price1h_min: "", vip_price1h_max: "", vip_price2h_min: "", vip_price2h_max: "", vip_price3h_min: "", vip_price3h_max: "" })}
              className="text-slate-400 hover:text-white">{t("reset", lang)}</Button>
            <Button data-testid="vip-private-search-apply" onClick={() => { setVipOpen(false); load(1); }} className="rose-btn text-white border-0"><Search size={14} className="me-1" /> {t("apply_filters", lang)}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
