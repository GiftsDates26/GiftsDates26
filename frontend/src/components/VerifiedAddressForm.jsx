import React, { useState } from "react";
import { CheckCircle2, AlertTriangle, MapPinned, Loader2 } from "lucide-react";
import { Input } from "./ui/input";
import { Button } from "./ui/button";
import { Checkbox } from "./ui/checkbox";
import AddressPicker, { MapsLink } from "./AddressPicker";
import { api } from "../lib/api";
import { useApp } from "../context/AppContext";
import { t } from "../lib/i18n";

const KEYS = ["address", "city", "postal_code", "country"];
export const addressComplete = (v, needVenue = true) => (!needVenue || !!(v?.venue || "").trim()) && KEYS.every(k => (v?.[k] || "").trim());
export const addressReady = (v, needVenue = true) => addressComplete(v, needVenue) && (!!v?.verified || !!v?.confirmed);
export const addrPayload = (v) => ({ address: v?.address || "", city: v?.city || "", postal_code: v?.postal_code || "", country: v?.country || "", lat: v?.lat ?? null, lng: v?.lng ?? null, address_confirmed: !!v?.confirmed && !v?.verified });
export const addrHintKey = (v, needVenue = true) => addressComplete(v, needVenue) ? "av_check_first" : (needVenue ? "av_required" : "av_required_nv");
export const addrErrKey = (d) => ({ CHECK_FIRST: "av_check_first", ADDRESS_FIELDS_REQUIRED: "av_required", ADDRESS_NUMBER_REQUIRED: "av_number", ADDRESS_NOT_FOUND: "av_fail", ADDRESS_CHECK_UNAVAILABLE: "av_unavailable" })[d];

// Venue + street & number + city + postal code + country, all required, checked against the map.
// If the map can't find it, the user may confirm the address is correct and accept the risk.
export default function VerifiedAddressForm({ value, onChange, testid = "vaddr", needVenue = true }) {
  const { lang } = useApp();
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const v = value || {};
  const change = (next) => {
    const moved = KEYS.some(k => (next[k] || "") !== (v[k] || ""));
    if (moved) setErr("");
    onChange(moved ? { ...next, verified: false, confirmed: false, match: "" } : next);
  };
  const verify = async () => {
    setBusy(true); setErr("");
    try {
      const { data } = await api.post("/geo/verify", { address: v.address, city: v.city, postal_code: v.postal_code, country: v.country });
      onChange({ ...v, lat: data.lat, lng: data.lng, match: data.display_name, verified: true, confirmed: false });
    } catch (e) { setErr(addrErrKey(e.response?.data?.detail) || "av_fail"); }
    finally { setBusy(false); }
  };
  const missing = !addressComplete(v, needVenue);
  const canOverride = err === "av_fail" || err === "av_unavailable";
  return (
    <div className="w-full space-y-2" data-testid={testid}>
      {needVenue && <Input data-testid={`${testid}-venue`} value={v.venue || ""} onChange={e => onChange({ ...v, venue: e.target.value })} placeholder={t("av_venue_ph", lang)} className="bg-white/5 border-white/10 h-9" />}
      <AddressPicker value={v} onChange={change} testid={`${testid}-addr`} />
      <p className="text-[11px] text-slate-500">{t(needVenue ? "av_required" : "av_required_nv", lang)}</p>
      <div className="flex flex-wrap items-center gap-2">
        <Button type="button" data-testid={`${testid}-verify`} disabled={busy || missing || v.verified} onClick={verify} variant="outline" className="h-9 bg-sky-500/10 border-sky-500/40 text-sky-200 hover:bg-sky-500/20">
          {busy ? <Loader2 size={14} className="me-1 animate-spin" /> : <MapPinned size={14} className="me-1" />}{t("av_verify", lang)}
        </Button>
        {v.verified && <span className="inline-flex items-center gap-1 text-xs text-emerald-300" data-testid={`${testid}-ok`}><CheckCircle2 size={14} />{t("av_ok", lang)}</span>}
      </div>
      {v.verified && v.match && <div className="text-[11px] text-slate-400 flex flex-wrap items-center gap-2" data-testid={`${testid}-match`}>{v.match} <MapsLink loc={v} testid={`${testid}-maps`} /></div>}
      {err && <div className="flex items-start gap-1.5 text-[11px] text-rose-200 rounded-lg border border-rose-500/30 bg-rose-500/10 p-2" data-testid={`${testid}-error`}><AlertTriangle size={13} className="mt-0.5 shrink-0" />{t(err, lang)}</div>}
      {canOverride && !missing && (
        <label className="flex items-start gap-2 rounded-lg border border-amber-500/40 bg-amber-500/10 p-2.5 cursor-pointer" data-testid={`${testid}-confirm-box`}>
          <Checkbox data-testid={`${testid}-confirm`} checked={!!v.confirmed} onCheckedChange={(c) => onChange({ ...v, confirmed: !!c, lat: null, lng: null })} className="mt-0.5 border-amber-400 data-[state=checked]:bg-amber-500 data-[state=checked]:text-black" />
          <span className="text-[11px] leading-relaxed">
            <b className="block text-amber-100">{t("av_confirm", lang)}</b>
            <span className="text-amber-200/90">{t("av_confirm_note", lang)}</span>
          </span>
        </label>
      )}
    </div>
  );
}

export const UnverifiedNote = ({ show, testid }) => {
  const { lang } = useApp();
  if (!show) return null;
  return <div className="mt-1 inline-flex items-center gap-1 text-[11px] text-amber-300" data-testid={testid}><AlertTriangle size={11} />{t("av_unverified_tag", lang)}</div>;
};
