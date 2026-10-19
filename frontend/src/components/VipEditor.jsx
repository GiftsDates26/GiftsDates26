import React, { useState, useEffect } from "react";
import { Crown, Plus, X, Sparkles, Lock, MapPin, Loader2, CalendarClock, ArrowRight } from "lucide-react";
import { toast } from "sonner";
import { useNavigate } from "react-router-dom";
import { api, fileUrl } from "../lib/api";
import { useApp } from "../context/AppContext";
import { t } from "../lib/i18n";
import { detectLocation } from "../lib/geolocate";
import { normalizeCountry } from "../lib/countries";
import { matchCuratedCity } from "../lib/cities";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { Textarea } from "./ui/textarea";
import { Switch } from "./ui/switch";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "./ui/select";
import VerifiedAddressForm, { addressReady, addrPayload, addrErrKey } from "./VerifiedAddressForm";
import { VIP_CATEGORIES, VIP_PLACES, PRICE_KEYS, svcLabel, catTitle, placeLabel, priceLabel, extraLabel, EXTRA_HOUR_MIN } from "../lib/vipCatalog";
import { GENDERS } from "./ProfileDetailsForm";
import CountrySelect from "./CountrySelect";
import CitySelect from "./CitySelect";
import MultiSelect from "./MultiSelect";

// Appearance option lists for the standalone anonymous VIP profile.
const EYE_COLORS = ["Brown", "Hazel", "Amber", "Green", "Blue", "Grey", "Black", "Heterochromia"];
const HAIR_COLORS = ["Black", "Dark brown", "Brown", "Light brown", "Blonde", "Platinum blonde", "Red", "Auburn", "Ginger", "Grey", "White", "Dyed / colourful"];
const INTIMATE_HAIRCUTS = ["Fully shaved", "Trimmed", "Landing strip", "Bikini line", "Natural / full", "Triangle"];
const BREAST_SIZES = ["AA", "A", "B", "C", "D", "DD", "E", "F", "G", "H+", "Natural", "Enhanced"];
const DICK_SIZES = ["< 12 cm", "12–14 cm", "15–17 cm", "18–20 cm", "21–23 cm", "24+ cm"];
const DICK_GIRTHS = ["Slim", "Average", "Thick", "Very thick"];

const NONE_VAL = "__none";
const CUSTOM_VAL = "__custom";

// A dropdown with all preset options plus a "Custom (type)…" entry that reveals a free-text input.
function AttrSelect({ label, value, onChange, options, lang, testid, customPh, noCustom }) {
  const isPreset = value && options.includes(value);
  const isCustom = !noCustom && !!value && !isPreset;
  const selectVal = isPreset ? value : (isCustom ? CUSTOM_VAL : NONE_VAL);
  return (
    <div>
      <label className="text-xs text-slate-400">{label}</label>
      <Select
        value={selectVal}
        onValueChange={(v) => {
          if (v === NONE_VAL) onChange("");
          else if (v === CUSTOM_VAL) onChange(" ");
          else onChange(v);
        }}
      >
        <SelectTrigger data-testid={testid} className="bg-white/5 border-white/10 mt-1"><SelectValue /></SelectTrigger>
        <SelectContent className="bg-[#161320] border-white/10 text-white max-h-72">
          <SelectItem value={NONE_VAL}>{t("not_specified_short", lang)}</SelectItem>
          {options.map((o) => <SelectItem key={o} value={o}>{o}</SelectItem>)}
          {!noCustom && <SelectItem value={CUSTOM_VAL}>{t("vip_attr_custom", lang)}</SelectItem>}
        </SelectContent>
      </Select>
      {isCustom && (
        <Input
          data-testid={`${testid}-custom`}
          value={value.trim() === "" ? "" : value}
          maxLength={60}
          onChange={(e) => onChange(e.target.value || " ")}
          placeholder={customPh || t("vip_attr_custom_ph", lang)}
          className="bg-white/5 border-white/10 mt-2"
        />
      )}
    </div>
  );
}

export default function VipEditor() {
  const { user, refreshUser, lang } = useApp();
  const nav = useNavigate();
  const isVip = user?.is_vip || (user?.vip_until && new Date(user.vip_until) > new Date());
  const v = user?.vip || {};
  const [services, setServices] = useState(v.services || []);
  const [servicesNote, setServicesNote] = useState(v.services_note || "");
  const [prices, setPrices] = useState({ hour: "", h2: "", h3: "", ...(v.prices || {}), extra: v.prices?.extra || EXTRA_HOUR_MIN });
  const [places, setPlaces] = useState(v.places || []);
  const [ownPlace, setOwnPlace] = useState({});
  useEffect(() => { api.get("/vip/own-place").then((r) => { const d = r.data || {}; setOwnPlace({ ...d, verified: d.lat != null, confirmed: !!d.unverified }); }).catch(() => {}); }, []);
  const [wants, setWants] = useState(v.client_wants || "");
  const [slots, setSlots] = useState(v.availability || []);
  const [ns, setNs] = useState({ date: "", from: "18:00", to: "23:00" });
  const [photos, setPhotos] = useState(v.photos || []);
  const [privatePhotos, setPrivatePhotos] = useState(v.private_photos || []);
  const [nickname, setNickname] = useState(v.nickname || "");
  const [postMode, setPostMode] = useState(v.post_mode === "separate" ? "separate" : "together");
  const [sepAge, setSepAge] = useState(v.age || "");
  const [sepCity, setSepCity] = useState(v.city || "");
  const [sepCountry, setSepCountry] = useState(v.country || "");
  const [sepGenders, setSepGenders] = useState(v.genders || (v.gender ? [v.gender] : []));
  const [sepBio, setSepBio] = useState(v.bio || "");
  const [sepHeight, setSepHeight] = useState(v.height || "");
  const [sepWeight, setSepWeight] = useState(v.weight || "");
  const [sepEye, setSepEye] = useState(v.eye_color || "");
  const [sepHair, setSepHair] = useState(v.hair_color || "");
  const [sepHaircut, setSepHaircut] = useState(v.intimate_haircut || "");
  const [sepBreast, setSepBreast] = useState(Array.isArray(v.breast_size) ? v.breast_size : (v.breast_size ? [v.breast_size] : []));
  const [sepDick, setSepDick] = useState(v.dick_size || "");
  const [sepDickGirth, setSepDickGirth] = useState(v.dick_girth || "");
  const [showOnMain, setShowOnMain] = useState(v.show_on_main !== false);
  const [published, setPublished] = useState(v.published !== false);
  const [busy, setBusy] = useState(false);
  const [locating, setLocating] = useState(false);
  const photoRef = React.useRef(null);
  const privateRef = React.useRef(null);
  const goBuyVip = () => { toast.info(t("vip_upsell", lang)); nav("/wallet?vip=1"); };
  const detectMyLocation = async () => {
    setLocating(true);
    try {
      const { city, country } = await detectLocation(lang);
      const normCountry = normalizeCountry(country);
      const nearestCity = matchCuratedCity(city, normCountry);
      if (normCountry) setSepCountry(normCountry);
      if (nearestCity) setSepCity(nearestCity);
      toast.success(t("location_detected", lang) + (nearestCity ? ` · ${nearestCity}${normCountry ? ", " + normCountry : ""}` : ""));
    } catch {
      toast.error(t("location_failed", lang));
    } finally {
      setLocating(false);
    }
  };
  const addPhoto = async (e, isPrivate = false) => {
    const files = Array.from(e.target.files || []); if (!files.length) return;
    const list = isPrivate ? privatePhotos : photos;
    const limit = isPrivate ? 12 : 8;
    const room = limit - list.length;
    const ref = isPrivate ? privateRef : photoRef;
    if (room <= 0) { toast.error(t("vip_max_photos", lang)); if (ref.current) ref.current.value = ""; return; }
    const toUpload = files.slice(0, room);
    if (files.length > room) toast.error(t("vip_max_photos", lang));
    try {
      let data;
      for (const f of toUpload) {
        const fd = new FormData(); fd.append("photo", f);
        ({ data } = await api.post(`/vip/photo?private=${isPrivate}`, fd));
      }
      if (data) { setPhotos(data.photos); setPrivatePhotos(data.private_photos); }
    }
    catch (er) { toast.error(er.response?.data?.detail === "MAX_PHOTOS" ? t("vip_max_photos", lang) : "Ошибка"); }
    finally { if (ref.current) ref.current.value = ""; }
  };
  const delPhoto = async (p, isPrivate = false) => {
    try { const { data } = await api.delete(`/vip/photo?path=${encodeURIComponent(p)}&private=${isPrivate}`); setPhotos(data.photos); setPrivatePhotos(data.private_photos); } catch { toast.error("Ошибка"); }
  };
  const makeCover = async (p) => {
    const reordered = [p, ...photos.filter((x) => x !== p)];
    setPhotos(reordered);
    try { await api.post("/vip/photos/reorder", { photos: reordered }); toast.success(t("vip_cover_updated", lang)); } catch { toast.error("Ошибка"); }
  };

  const toggle = (arr, set, val) => set(arr.includes(val) ? arr.filter((x) => x !== val) : [...arr, val]);
  // Gender-aware appearance: show breast fields for feminine identities, dick fields for masculine ones.
  const FEMININE = ["female", "cis_woman"];
  const MASCULINE = ["male", "cis_man"];
  const onlyFeminine = sepGenders.length > 0 && sepGenders.every((g) => FEMININE.includes(g));
  const onlyMasculine = sepGenders.length > 0 && sepGenders.every((g) => MASCULINE.includes(g));
  const showBreast = !onlyMasculine; // hide only when purely masculine
  const showDick = !onlyFeminine;    // hide only when purely feminine
  const addSlot = () => {
    if (!/^\d{4}-\d{2}-\d{2}$/.test(ns.date) || ns.from >= ns.to) { toast.error("Укажите дату и корректное время"); return; }
    setSlots([...slots, { ...ns }].sort((a, b) => (a.date + a.from).localeCompare(b.date + b.from)));
  };
  const onTogglePublish = (val) => {
    if (!isVip) { goBuyVip(); return; }
    setPublished(val);
  };
  const save = async () => {
    setBusy(true);
    try {
      // In "separate" mode the user only fills Nickname, Age, Country, City.
      // Gender, bio and all appearance fields are inherited from the main profile.
      const sep = postMode === "separate";
      const mp = user || {};
      const inhGenders = sep ? (mp.genders && mp.genders.length ? mp.genders : (mp.gender ? [mp.gender] : [])) : sepGenders;
      const payload = {
        services, services_note: servicesNote, places, client_wants: wants,
        price_hour: Math.max(EXTRA_HOUR_MIN, Number(prices.hour) || 0), price_2h: Math.max(EXTRA_HOUR_MIN, Number(prices.h2) || 0), price_3h: Math.max(EXTRA_HOUR_MIN, Number(prices.h3) || 0),
        price_extra_hour: Math.max(EXTRA_HOUR_MIN, Number(prices.extra) || 0),
        availability: slots, published: isVip ? published : false,
        nickname, post_mode: postMode,
        age: Number(sepAge) || null, city: sepCity, country: sepCountry,
        gender: inhGenders[0] || "", genders: inhGenders,
        bio: sep ? (mp.bio || "") : sepBio,
        height: Number(sepHeight) || null,
        weight: Number(sepWeight) || null,
        eye_color: (sepEye || "").trim(),
        hair_color: (sepHair || "").trim(),
        intimate_haircut: (sepHaircut || "").trim(),
        breast_size: Array.isArray(sepBreast) ? sepBreast : (sepBreast ? [sepBreast] : []),
        dick_size: (sepDick || "").trim(),
        dick_girth: (sepDickGirth || "").trim(),
        show_on_main: showOnMain,
      };
      await api.put("/vip/profile", payload);
      if (places.includes("own")) {
        if (!addressReady(ownPlace, false)) throw { response: { data: { detail: "ADDRESS_FIELDS_REQUIRED" } } };
        await api.put("/vip/own-place", addrPayload(ownPlace));
      }
      await refreshUser();
      toast.success(t("vip_saved_toast", lang));
    } catch (e) { const d = e.response?.data?.detail; toast.error(addrErrKey(d) ? t(addrErrKey(d), lang) : d || "Ошибка"); } finally { setBusy(false); }
  };

  return (
    <div className="glass rounded-2xl p-6 mb-6 border border-rose-500/30 space-y-5" data-testid="vip-editor">
      <div className={`rounded-2xl p-4 border ${isVip ? "border-amber-500/30 bg-amber-500/5" : "border-amber-500/40 bg-amber-500/10"}`} data-testid="vip-publish-box">
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-2.5">
            <Crown className="text-amber-300 shrink-0" size={22} />
            <div>
              <div className="text-sm font-semibold text-amber-100">{t("vip_publish_toggle", lang)}</div>
              <div className="text-xs text-slate-400">{isVip ? (published ? t("vip_live", lang) : t("vip_hidden", lang)) : t("vip_preview_note", lang)}</div>
            </div>
          </div>
          <Switch data-testid="vip-publish-switch" checked={isVip && published} onCheckedChange={onTogglePublish} />
        </div>
        {isVip && <div className="flex items-center justify-between gap-3 mt-3 pt-3 border-t border-amber-500/20" data-testid="vip-show-on-main-row">
          <div className="ps-8">
            <div className="text-sm font-semibold text-amber-100">{t("vip_show_on_main", lang)}</div>
            <div className={`text-[11px] ${showOnMain ? "text-slate-400" : "text-amber-300"}`} data-testid="vip-show-on-main-note">{t(showOnMain ? "vip_show_on_main_on" : "vip_show_on_main_off", lang)}</div>
          </div>
          <Switch data-testid="vip-show-on-main-switch" checked={showOnMain} onCheckedChange={setShowOnMain} />
        </div>}
        {!isVip && (
          <Button data-testid="vip-buy-publish-cta" onClick={goBuyVip} className="rose-btn text-white border-0 mt-3 w-full sm:w-auto"><Sparkles size={16} className="me-1" /> {t("vip_buy_publish", lang)}</Button>
        )}
      </div>

      <h2 className="font-serif-luxe text-2xl gold-text flex items-center gap-2"><Crown size={22} className="text-amber-300" /> {t("vip_editor_title", lang)}</h2>
      <p className="text-xs text-slate-400">{t("vip_editor_note", lang)}</p>

      <div className="grid sm:grid-cols-2 gap-4">
        <div>
          <label className="text-sm font-semibold text-amber-200">{t("vip_nickname", lang)}</label>
          <Input data-testid="vip-nickname-input" value={nickname} maxLength={40} onChange={(e) => setNickname(e.target.value)} placeholder={t("vip_nickname_ph", lang)} className="bg-white/5 border-white/10 mt-1" />
          <p className="text-[11px] text-slate-500 mt-1 flex items-start gap-1"><Lock size={11} className="mt-0.5 shrink-0 text-amber-300" /> {t("vip_nickname_note", lang)}</p>
        </div>
        <div>
          <label className="text-sm font-semibold text-amber-200">{t("vip_post_mode", lang)}</label>
          <div className="mt-1 grid grid-cols-2 gap-2" data-testid="vip-post-mode">
            {[{ v: "together", l: "vip_post_together" }, { v: "separate", l: "vip_post_separate" }].map((o) => (
              <button key={o.v} type="button" data-testid={`vip-post-mode-${o.v}`} onClick={() => setPostMode(o.v)}
                className={`text-xs px-3 py-2 rounded-lg border transition-colors ${postMode === o.v ? "bg-amber-500/20 border-amber-500/50 text-amber-200" : "bg-white/5 border-white/10 text-slate-300 hover:bg-white/10"}`}>{t(o.l, lang)}</button>
            ))}
          </div>
          <p className="text-[11px] text-slate-500 mt-1">{t("vip_post_mode_note", lang)}</p>
          {postMode === "together" && (
            <div className="mt-2 flex items-start gap-2 rounded-lg border border-amber-500/30 bg-amber-500/5 p-2.5 text-[11px] text-amber-200/90" data-testid="vip-unlock-split-note">
              <Lock size={13} className="mt-0.5 shrink-0 text-amber-300" />
              <span>{t("vip_unlock_split_note", lang)}</span>
            </div>
          )}
        </div>
      </div>

      {postMode === "separate" && (
        <div className="rounded-2xl border border-amber-500/30 bg-amber-500/5 p-4 space-y-4" data-testid="vip-separate-block">
          <div className="flex items-start gap-2 text-[11px] text-amber-200/90">
            <Lock size={13} className="mt-0.5 shrink-0 text-amber-300" />
            <span>{t("vip_separate_intro", lang)}</span>
          </div>
          <div className="grid sm:grid-cols-3 gap-3">
            <div>
              <label className="text-xs text-slate-400">{t("age", lang)}</label>
              <Input data-testid="vip-sep-age" type="number" min="18" max="99" value={sepAge} onChange={(e) => setSepAge(e.target.value)} className="bg-white/5 border-white/10 mt-1 font-mono-num" />
            </div>
            <div>
              <label className="text-xs text-slate-400">{t("country", lang)}</label>
              <CountrySelect testid="vip-sep-country" value={sepCountry} onChange={(c) => { setSepCountry(c); setSepCity(""); }} lang={lang} />
            </div>
            <div>
              <label className="text-xs text-slate-400">{t("city", lang)}</label>
              <CitySelect testid="vip-sep-city" value={sepCity} country={sepCountry} onChange={setSepCity} lang={lang} />
            </div>
          </div>
          <button
            type="button"
            data-testid="vip-sep-detect-location"
            onClick={detectMyLocation}
            disabled={locating}
            className="w-full inline-flex items-center justify-center gap-2 h-10 rounded-lg border border-sky-500/40 bg-sky-500/10 text-sky-200 text-sm hover:bg-sky-500/20 transition-colors disabled:opacity-60"
          >
            {locating ? <Loader2 size={15} className="animate-spin" /> : <MapPin size={15} />}
            {locating ? t("detecting_location", lang) : t("detect_location", lang)}
          </button>
        </div>
      )}


      <div className="rounded-xl border border-rose-500/20 bg-white/5 p-4 space-y-3" data-testid="vip-appearance">
        <div className="text-sm font-semibold text-rose-200 flex items-center gap-1.5"><Lock size={14} className="text-rose-300" /> {t("vip_appearance", lang)}</div>
        <p className="text-[11px] text-slate-500">{t("vip_private_photos_note", lang)}</p>
        <div className="grid sm:grid-cols-2 gap-3">
          <div>
            <label className="text-xs text-slate-400">{t("height", lang)}</label>
            <Input data-testid="vip-height" type="number" min="100" max="250" value={sepHeight} onChange={(e) => setSepHeight(e.target.value)} className="bg-white/5 border-white/10 mt-1 font-mono-num" />
          </div>
          <div>
            <label className="text-xs text-slate-400">{t("weight", lang)}</label>
            <Input data-testid="vip-weight" type="number" min="30" max="400" value={sepWeight} onChange={(e) => setSepWeight(e.target.value)} className="bg-white/5 border-white/10 mt-1 font-mono-num" />
          </div>
          <AttrSelect testid="vip-eye" label={t("vip_eye_color", lang)} value={sepEye} onChange={setSepEye} options={EYE_COLORS} lang={lang} />
          <AttrSelect testid="vip-hair" label={t("vip_hair_color", lang)} value={sepHair} onChange={setSepHair} options={HAIR_COLORS} lang={lang} />
          <AttrSelect testid="vip-haircut" label={t("vip_intimate_haircut", lang)} value={sepHaircut} onChange={setSepHaircut} options={INTIMATE_HAIRCUTS} lang={lang} />
          <div>
            <label className="text-xs text-slate-400">{t("vip_breast_size", lang)}</label>
            <div className="mt-1">
              <MultiSelect
                testid="vip-breast"
                value={Array.isArray(sepBreast) ? sepBreast : (sepBreast ? [sepBreast] : [])}
                onChange={setSepBreast}
                options={BREAST_SIZES.map(o => ({ value: o, label: o }))}
                placeholder={t("not_specified_short", lang)}
                searchPlaceholder={t("search", lang)}
                emptyText={t("no_results", lang)}
                accent="amber"
              />
            </div>
          </div>
          <div>
            <label className="text-xs text-slate-400">{t("vip_dick_size", lang)}</label>
            <Input data-testid="vip-dick" type="number" min="1" max="60" value={(sepDick || "").trim()} onChange={(e) => setSepDick(e.target.value)} placeholder={t("vip_dick_custom_ph", lang)} className="bg-white/5 border-white/10 mt-1" />
          </div>
          <AttrSelect testid="vip-dick-girth" label={t("vip_dick_girth", lang)} value={sepDickGirth} onChange={setSepDickGirth} options={DICK_GIRTHS} lang={lang} noCustom />
        </div>
      </div>


      <div data-testid="vip-private-photos">
        <div className="text-sm font-semibold text-rose-200 mb-1 flex items-center gap-1.5"><Lock size={14} className="text-rose-300" /> {t("vip_private_photos", lang)}</div>
        <p className="text-[11px] text-slate-500 mb-2">{t("vip_private_photos_note", lang)}</p>
        <div className="flex flex-wrap gap-2">
          {privatePhotos.map((p) => (
            <div key={p} className="relative w-20 h-20 rounded-lg overflow-hidden border border-rose-500/40 group">
              <img src={fileUrl(p)} alt="" className="w-full h-full object-cover" />
              <button data-testid="vip-private-photo-del" onClick={() => delPhoto(p, true)} className="absolute top-0 right-0 bg-black/70 text-rose-300 p-0.5"><X size={12} /></button>
            </div>
          ))}
          {privatePhotos.length < 12 && (
            <>
              <input ref={privateRef} data-testid="vip-private-photo-input" type="file" accept="image/*" multiple onChange={(e) => addPhoto(e, true)} className="hidden" id="vip-private-photo" />
              <label htmlFor="vip-private-photo" className="w-20 h-20 rounded-lg border-2 border-dashed border-rose-400/50 flex items-center justify-center text-rose-300 cursor-pointer hover:bg-white/5"><Plus size={20} /></label>
            </>
          )}
        </div>
      </div>

      <div data-testid="vip-services">
        <div className="text-sm font-semibold text-amber-200 mb-2">{t("vip_services", lang)}</div>
        <MultiSelect
          testid="vip-services-select"
          accent="rose"
          value={services}
          onChange={setServices}
          groups={VIP_CATEGORIES.map((cat) => ({
            label: catTitle(cat.key, lang),
            options: cat.items.map((it) => ({ value: it, label: svcLabel(it, lang) })),
          }))}
          placeholder={t("vip_services_ph", lang)}
          searchPlaceholder={t("search", lang)}
          emptyText={t("no_results", lang)}
        />
        <Textarea
          data-testid="vip-services-note"
          rows={2}
          maxLength={500}
          value={servicesNote}
          onChange={(e) => setServicesNote(e.target.value)}
          placeholder={t("vip_services_note_ph", lang)}
          className="bg-white/5 border-white/10 mt-2"
        />
        <p className="text-[11px] text-slate-500 mt-1">{t("vip_services_note_hint", lang)}</p>
      </div>

      <div>
        <div className="text-sm font-semibold text-amber-200 mb-2">{t("vip_prices", lang)}</div>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {PRICE_KEYS.map((p) => (
            <div key={p.k}>
              <label className="text-xs text-slate-400">{priceLabel(p.k, lang)}</label>
              <Input data-testid={`vip-price-${p.k}`} type="number" min={EXTRA_HOUR_MIN} step="50" value={prices[p.k] ?? ""} placeholder={`min ${EXTRA_HOUR_MIN}`} onChange={(e) => setPrices({ ...prices, [p.k]: e.target.value })}
                onBlur={() => setPrices((x) => ({ ...x, [p.k]: Math.max(EXTRA_HOUR_MIN, Number(x[p.k]) || 0) }))} className="bg-white/5 border-white/10 mt-1 font-mono-num" />
            </div>
          ))}
          <div>
            <label className="text-xs text-slate-400">{extraLabel(lang)} (min {EXTRA_HOUR_MIN})</label>
            <Input data-testid="vip-price-extra" type="number" min={EXTRA_HOUR_MIN} step="50" value={prices.extra ?? ""}
              onChange={(e) => setPrices({ ...prices, extra: e.target.value })}
              onBlur={() => setPrices((p) => ({ ...p, extra: Math.max(EXTRA_HOUR_MIN, Number(p.extra) || 0) }))}
              className="bg-white/5 border-white/10 mt-1 font-mono-num" />
          </div>
        </div>
      </div>

      <div>
        <div className="text-sm font-semibold text-amber-200 mb-2">{t("vip_place", lang)}</div>
        <MultiSelect
          testid="vip-places-select"
          accent="amber"
          value={places}
          onChange={setPlaces}
          options={VIP_PLACES.map((p) => ({ value: p.v, label: placeLabel(p.v, lang) }))}
          placeholder={t("vip_place_ph", lang)}
          searchPlaceholder={t("search", lang)}
          emptyText={t("no_results", lang)}
        />
        {places.includes("own") && (
          <div className="mt-3 rounded-xl border border-amber-500/25 bg-amber-500/5 p-3 space-y-2" data-testid="vip-own-place">
            <div className="text-xs font-semibold text-amber-200">{t("own_addr_title", lang)}</div>
            <p className="text-[11px] text-slate-400">{t("own_addr_note", lang)}</p>
            <VerifiedAddressForm value={ownPlace} onChange={setOwnPlace} needVenue={false} testid="vip-own-place-addr" />
            {!ownPlace.address && <p className="text-[11px] text-amber-300" data-testid="vip-own-place-missing">{t("own_addr_missing", lang)}</p>}
          </div>
        )}
      </div>

      <div>
        <div className="flex items-center justify-between mb-2 gap-2 flex-wrap">
          <div className="text-sm font-semibold text-amber-200">{t("vip_calendar", lang)}</div>
          <Button
            data-testid="vip-open-bookings"
            type="button"
            onClick={() => nav("/vip-bookings")}
            size="sm"
            className="bg-rose-500 hover:bg-rose-600 text-white h-8 px-3 gap-1.5"
          >
            <CalendarClock size={15} />
            {t("vip_manage_bookings", lang)}
            <ArrowRight size={14} />
          </Button>
        </div>
      </div>

      <div>
        <div className="text-sm font-semibold text-amber-200 mb-2">{t("vip_wants", lang)}</div>
        <Textarea data-testid="vip-wants" rows={3} maxLength={1000} value={wants} onChange={(e) => setWants(e.target.value)} placeholder={t("vip_wants_ph", lang)} className="bg-white/5 border-white/10" />
      </div>

      <Button data-testid="vip-save" onClick={save} disabled={busy} className="rose-btn text-white border-0 h-11 w-full">{busy ? "…" : t("vip_save_btn", lang)}</Button>
    </div>
  );
}
