import React, { useEffect, useRef, useState } from "react";
import { Navigation, MapPin, Radio, LifeBuoy, Heart, Siren } from "lucide-react";
import { toast } from "sonner";
import { Button } from "./ui/button";
import { Switch } from "./ui/switch";
import { api } from "../lib/api";
import { useApp } from "../context/AppContext";
import { t } from "../lib/i18n";

const dirUrl = (dest) => `https://www.google.com/maps/dir/?api=1&destination=${encodeURIComponent(dest)}&travelmode=driving`;
const ago = (iso) => Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 60000));

export default function LiveLocation({ kind, id, otherName, venue }) {
  const { lang } = useApp();
  otherName = otherName || t("ll_your_date", lang);
  const [info, setInfo] = useState(null);
  const [sharing, setSharing] = useState(false);
  const [to, setTo] = useState({ to_date: true, to_support: false });
  const [sosBusy, setSosBusy] = useState(false);
  const watch = useRef(null), last = useRef(0), pos = useRef(null), toRef = useRef(to);
  const base = `/live-location/${kind}/${id}`;

  const load = () => api.get(base).then(r => {
    setInfo(r.data);
    if (r.data.me && watch.current == null) { const v = { to_date: r.data.me.to_date ?? true, to_support: !!r.data.me.to_support }; setTo(v); toRef.current = v; }
  }).catch(() => {});
  useEffect(() => { load(); const iv = setInterval(load, 20000); return () => clearInterval(iv); }, [id]); // eslint-disable-line
  useEffect(() => () => { if (watch.current != null) navigator.geolocation.clearWatch(watch.current); }, []);

  const stop = async () => {
    if (watch.current != null) navigator.geolocation.clearWatch(watch.current);
    watch.current = null; setSharing(false);
    await api.post(base, { lat: 0, lng: 0, sharing: false }).catch(() => {});
    load();
  };
  const start = () => {
    if (!navigator.geolocation) { toast.error(t("ll_no_gps", lang)); return; }
    setSharing(true);
    watch.current = navigator.geolocation.watchPosition(async (p) => {
      if (Date.now() - last.current < 15000) return;
      last.current = Date.now();
      pos.current = { lat: p.coords.latitude, lng: p.coords.longitude };
      try { await api.post(base, { ...pos.current, ...toRef.current, sharing: true }); load(); }
      catch (e) { toast.error(e.response?.data?.detail === "LIVE_LOCATION_CLOSED" ? t("ll_closed", lang) : t("failed", lang)); stop(); }
    }, () => { toast.error(t("ll_denied", lang)); stop(); }, { enableHighAccuracy: true, maximumAge: 10000 });
  };

  const toggleTo = async (k) => {
    const v = { ...toRef.current, [k]: !toRef.current[k] };
    setTo(v); toRef.current = v;
    if (!v.to_date && !v.to_support) { if (sharing) stop(); return; }
    if (sharing && pos.current) await api.post(base, { ...pos.current, ...v, sharing: true }).then(load).catch(() => {});
  };
  const sendSos = async () => {
    if (!window.confirm(t("sos_confirm", lang))) return;
    setSosBusy(true);
    const p = await new Promise(res => navigator.geolocation
      ? navigator.geolocation.getCurrentPosition(x => res({ lat: x.coords.latitude, lng: x.coords.longitude }), () => res({}), { enableHighAccuracy: true, timeout: 8000 })
      : res({}));
    try {
      const r = await api.post(`/sos/${kind}/${id}`, p);
      toast.success(t("sos_sent", lang) + (r.data.contacts_alerted ? " " + t("sos_contacts", lang).replace("{n}", r.data.contacts_alerted) : ""), { duration: 10000 });
      const v = { ...toRef.current, to_support: true }; setTo(v); toRef.current = v;
      if (p.lat != null) { pos.current = p; await api.post(base, { ...p, ...v, sharing: true }).catch(() => {}); }
      if (watch.current == null) start();
      load();
    } catch (e) { toast.error(e.response?.data?.detail || t("failed", lang)); }
    finally { setSosBusy(false); }
  };
  const chip = (k, Icon, label) => (
    <button type="button" onClick={() => toggleTo(k)} data-testid={`live-loc-share-${k === "to_date" ? "date" : "support"}-${id}`}
      className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-[11px] transition-colors ${to[k] ? "border-sky-400/50 bg-sky-500/15 text-sky-100" : "border-white/10 bg-white/5 text-slate-400 hover:bg-white/10"}`}>
      <Icon size={11} />{label}
    </button>
  );

  if (!info) return null;
  if (!info.open) return info.opens_at && new Date(info.opens_at) > new Date()
    ? <div className="w-full text-[11px] text-slate-500 flex items-center gap-1" data-testid={`live-loc-closed-${id}`}><Navigation size={11} />{t("ll_opens", lang).replace("{t}", new Date(info.opens_at).toLocaleString(lang, { weekday: "short", hour: "2-digit", minute: "2-digit" }))}</div>
    : null;

  const o = info.other;
  return (
    <div className="w-full rounded-xl border border-sky-500/30 bg-sky-500/5 p-3 space-y-2.5" data-testid={`live-loc-${id}`}>
      <div className="flex items-center gap-2 text-sm">
        <Navigation size={14} className="text-sky-300" />
        <span className="text-sky-100 font-semibold">{t("ll_title", lang)}</span>
        <span className="text-[10px] text-slate-400">({t("ll_optional", lang)})</span>
        <label className="ms-auto flex items-center gap-2 text-xs text-slate-300">
          {sharing && <Radio size={12} className="text-emerald-300 animate-pulse" />}
          {t("ll_share", lang)}
          <Switch checked={sharing} disabled={!to.to_date && !to.to_support} onCheckedChange={(v) => (v ? start() : stop())} data-testid={`live-loc-toggle-${id}`} />
        </label>
      </div>
      <div className="flex flex-wrap items-center gap-1.5" data-testid={`live-loc-share-with-${id}`}>
        <span className="text-[11px] text-slate-400">{t("ll_share_with", lang)}</span>
        {chip("to_date", Heart, otherName)}
        {chip("to_support", LifeBuoy, t("ll_support", lang))}
      </div>
      {o ? (
        <div className="space-y-2" data-testid={`live-loc-other-${id}`}>
          <div className="text-xs text-slate-300">{t("ll_other_here", lang).replace("{name}", otherName || "")} · {t("ll_updated", lang).replace("{n}", ago(o.at))}</div>
          <iframe title="live-location" className="w-full h-48 rounded-lg border border-white/10" loading="lazy"
            src={`https://maps.google.com/maps?q=${o.lat},${o.lng}&z=15&output=embed`} />
        </div>
      ) : <div className="text-xs text-slate-500" data-testid={`live-loc-waiting-${id}`}>{t("ll_not_shared", lang).replace("{name}", otherName || "")}</div>}
      <div className="flex items-center gap-2 rounded-lg border border-red-500/40 bg-red-500/10 p-2" data-testid={`sos-block-${id}`}>
        <span className="text-[11px] text-red-200 flex-1">{t("sos_hint", lang)}</span>
        <Button size="sm" disabled={sosBusy} onClick={sendSos} data-testid={`sos-btn-${id}`} className="h-8 bg-red-600 hover:bg-red-500 text-white border-0 font-bold tracking-wider active:scale-95 transition-transform">
          <Siren size={14} className={`me-1 ${sosBusy ? "animate-pulse" : ""}`} />{t("sos_btn", lang)}</Button>
      </div>
      <div className="flex flex-wrap gap-2">
        {o && <a href={dirUrl(`${o.lat},${o.lng}`)} target="_blank" rel="noreferrer" data-testid={`live-loc-dir-other-${id}`}>
          <Button size="sm" className="h-8 bg-sky-500 hover:bg-sky-400 text-white border-0"><Navigation size={13} className="me-1" />{t("ll_dir_other", lang).replace("{name}", otherName || "")}</Button></a>}
        {venue && <a href={dirUrl(venue)} target="_blank" rel="noreferrer" data-testid={`live-loc-dir-venue-${id}`}>
          <Button size="sm" variant="outline" className="h-8 bg-white/5 border-white/15"><MapPin size={13} className="me-1" />{t("ll_dir_venue", lang)}</Button></a>}
      </div>
    </div>
  );
}
