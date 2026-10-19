import React, { useEffect, useState } from "react";
import DateCommitmentNote from "./DateCommitmentNote";
import { Crown, Lock, Calendar } from "lucide-react";
import { toast } from "sonner";
import { useNavigate } from "react-router-dom";
import { api, fileUrl } from "../lib/api";
import { useApp } from "../context/AppContext";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "./ui/dialog";
import { Button } from "./ui/button";
import VerifiedAddressForm, { addressReady, addrPayload, addrErrKey } from "./VerifiedAddressForm";
import { PRICE_KEYS, svcLabel, placeLabel, priceLabel, extraLabel, extraPrice, EXTRA_HOUR_MIN } from "../lib/vipCatalog";
import ExtraHoursStepper from "./ExtraHoursStepper";
import { t } from "../lib/i18n";

export default function VipSection({ userId, name, preview }) {
  const { user, refreshUser, lang } = useApp();
  const nav = useNavigate();
  const [data, setData] = useState(undefined); // undefined=loading, null=none
  const [slot, setSlot] = useState(null);
  const [place, setPlace] = useState(null);
  const [loc, setLoc] = useState({});
  const [busy, setBusy] = useState(false);
  const [unlocking, setUnlocking] = useState(false);
  const [extraHours, setExtraHours] = useState(0);
  const [agree, setAgree] = useState(false);

  const unlockSection = async () => {
    const price = data?.unlock_price || 100;
    if (((user?.coins || 0) + (user?.withdrawable || 0)) < price) {
      toast.error(t("vip_unlock_insufficient", lang), { action: { label: t("topup", lang), onClick: () => nav("/wallet") } });
      return;
    }
    setUnlocking(true);
    try {
      await api.post(`/vip/unlock/${userId}`);
      toast.success(t("vip_unlock_success", lang));
      await refreshUser();
      const q = preview ? `?preview=${preview}` : "";
      const r = await api.get(`/vip/profile/${userId}${q}`);
      setData(r.data);
    } catch (e) {
      toast.error(e.response?.data?.detail || "Error");
    } finally {
      setUnlocking(false);
    }
  };

  useEffect(() => {
    const q = preview ? `?preview=${preview}` : "";
    api.get(`/vip/profile/${userId}${q}`).then((r) => setData(r.data)).catch(() => setData(null));
  }, [userId, preview]);

  if (data === undefined || data === null) return null;

  if (data.locked) {
    return (
      <div className="mt-6 relative rounded-2xl overflow-hidden gold-hairline" data-testid="vip-locked">
        {data.teaser_photo ? (
          <img src={fileUrl(data.teaser_photo)} alt="" className="w-full h-56 object-cover blur-xl scale-110 select-none pointer-events-none" />
        ) : (
          <div className="p-8 blur-sm select-none pointer-events-none">
            <div className="h-4 w-40 bg-white/10 rounded mb-3" /><div className="h-3 w-full bg-white/10 rounded mb-2" /><div className="h-3 w-2/3 bg-white/10 rounded" />
          </div>
        )}
        <div className="absolute inset-0 flex flex-col items-center justify-center bg-black/50 text-center px-6">
          <Lock className="text-amber-300" size={26} />
          <div className="font-serif-luxe text-lg text-white mt-2">{t("vip_sensitive", lang)} 🔒</div>
          <p className="text-xs text-slate-300 mt-1 max-w-xs">{t("vip_unlock_note", lang)}</p>
          <div className="flex flex-row items-stretch gap-2 mt-3 w-full max-w-sm">
            <Button data-testid="vip-buy-vip-cta" onClick={() => nav("/wallet?premium=1")} className="rose-btn text-white border-0 flex-1">
              <Crown size={16} className="me-2" /> {t("vip_buy_vip", lang)}
            </Button>
            <Button data-testid="vip-unlock-one-cta" variant="outline" onClick={unlockSection} disabled={unlocking} className="flex-1 bg-white/5 border-amber-500/40 text-amber-200 hover:bg-amber-500/10 hover:text-amber-100">
              {t("vip_unlock_coins", lang).replace("{n}", data.unlock_price || 100)} 🪙
            </Button>
          </div>
        </div>
      </div>
    );
  }

  const v = data.vip || {};
  const priceFor = (k) => Math.max(EXTRA_HOUR_MIN, Number(v.prices?.[k]) || 0);
  const hasPlaces = (v.places?.length || 0) > 0;

  const extra = extraPrice(v.prices);
  const book = async (durKey) => {
    const coins = priceFor(durKey);
    if (!coins) { toast.error("Цена не указана"); return; }
    const total = coins + extraHours * extra;
    if (!agree) { toast.error(t("commit_required", lang)); return; }
    if (hasPlaces && !place) { toast.error(t("vip_select_place_first", lang)); return; }
    if (place && place !== "own" && !addressReady(loc, false)) { toast.error(t("av_required_nv", lang)); return; }
    if ((( user?.coins || 0) + (user?.withdrawable || 0)) < total) { toast.error("Недостаточно монет", { action: { label: "Пополнить", onClick: () => nav("/wallet") } }); return; }
    setBusy(true);
    try {
      const providerHosts = place === "own";
      await api.post("/vip/book", {
        target_id: userId,
        venue: place ? placeLabel(place, lang) : "VIP",
        place: place || null,
        city: (!providerHosts && loc.city) || data.city || "-",
        address: providerHosts ? "" : (loc.address || ""),
        postal_code: providerHosts ? "" : (loc.postal_code || ""),
        country: providerHosts ? "" : (loc.country || ""),
        lat: providerHosts ? null : (loc.lat ?? null),
        lng: providerHosts ? null : (loc.lng ?? null),
        address_confirmed: !providerHosts && addrPayload(loc).address_confirmed,
        scheduled_at: `${slot.date}T${slot.from}:00`,
        coins,
        extra_hours: extraHours,
        vip_length: { hour: 1, h2: 2, h3: 3 }[durKey],
      });
      toast.success(t("vip_booked_toast", lang));
      setSlot(null); setPlace(null); setLoc({}); setExtraHours(0);
      await refreshUser();
    } catch (e) { const d = e.response?.data?.detail; toast.error(addrErrKey(d) ? t(addrErrKey(d), lang) : d || "Ошибка"); } finally { setBusy(false); }
  };

  return (
    <div className="mt-6 glass rounded-2xl p-6 border border-rose-500/30 space-y-4" data-testid="vip-section">
      <h3 className="font-serif-luxe text-xl gold-text flex items-center gap-2"><Crown size={20} className="text-amber-300" /> {t("vip_priv", lang)}</h3>

      {v.photos?.length > 0 && (
        <div className="grid grid-cols-3 sm:grid-cols-4 gap-2" data-testid="vip-view-photos">
          {v.photos.map((p) => <img key={p} src={fileUrl(p)} alt="" className="w-full aspect-square object-cover rounded-lg gold-hairline" />)}
        </div>
      )}

      {v.private_photos?.length > 0 && (
        <div data-testid="vip-view-private-photos">
          <div className="text-sm font-semibold text-rose-200 mb-2 flex items-center gap-1.5"><Lock size={14} className="text-rose-300" /> {t("vip_private_photos", lang)}</div>
          <div className="grid grid-cols-3 sm:grid-cols-4 gap-2">
            {v.private_photos.map((p) => <img key={p} src={fileUrl(p)} alt="" className="w-full aspect-square object-cover rounded-lg border border-rose-500/40" />)}
          </div>
        </div>
      )}

      {v.services?.length > 0 && (
        <div className="flex flex-wrap gap-2" data-testid="vip-services">
          {v.services.map((s) => <span key={s} className="text-xs px-2.5 py-1 rounded-full bg-rose-500/15 border border-rose-500/30 text-rose-200">{svcLabel(s, lang)}</span>)}
        </div>
      )}
      {v.services_note && (
        <div className="text-sm text-slate-300" data-testid="vip-services-note-view"><span className="text-slate-500">{t("vip_services", lang)}: </span>{v.services_note}</div>
      )}

      {(v.height || v.weight || v.eye_color || v.hair_color || v.intimate_haircut || (Array.isArray(v.breast_size) ? v.breast_size.length : v.breast_size) || v.dick_size || v.dick_girth) && (
        <div className="rounded-xl border border-white/10 bg-white/5 p-4" data-testid="vip-view-appearance">
          <div className="text-sm font-semibold text-amber-200 mb-2">{t("vip_appearance", lang)}</div>
          <div className="grid grid-cols-2 gap-x-4">
            {[
              [t("height", lang), v.height ? `${v.height} cm` : ""],
              [t("weight", lang), v.weight ? `${v.weight} kg` : ""],
              [t("vip_eye_color", lang), v.eye_color],
              [t("vip_hair_color", lang), v.hair_color],
              [t("vip_intimate_haircut", lang), v.intimate_haircut],
              [t("vip_breast_size", lang), Array.isArray(v.breast_size) ? v.breast_size.join(", ") : v.breast_size],
              [t("vip_dick_size", lang), v.dick_size],
              [t("vip_dick_girth", lang), v.dick_girth],
            ].filter(([, val]) => val).map(([label, val]) => (
              <div key={label} className="flex justify-between gap-3 py-1.5 border-b border-white/5 text-sm">
                <span className="text-slate-400">{label}</span><span className="text-right text-slate-200">{val}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3" data-testid="vip-prices">
        {PRICE_KEYS.map((p) => priceFor(p.k) > 0 && (
          <div key={p.k} className="glass rounded-xl p-3 text-center">
            <div className="text-[11px] text-slate-400">{priceLabel(p.k, lang)}</div>
            <div className="font-mono-num text-amber-300">🪙 {priceFor(p.k)}</div>
          </div>
        ))}
        {PRICE_KEYS.some((p) => priceFor(p.k) > 0) && (
          <div className="glass rounded-xl p-3 text-center border border-amber-500/25" data-testid="vip-price-extra-view">
            <div className="text-[11px] text-slate-400">{extraLabel(lang)}</div>
            <div className="font-mono-num text-amber-300">+ 🪙 {extra}</div>
          </div>
        )}
      </div>

      {v.places?.length > 0 && (
        <div className="text-sm text-slate-300"><span className="text-slate-500">{t("vip_place", lang)}: </span>{v.places.map((pv) => placeLabel(pv, lang)).filter(Boolean).join(" · ")}</div>
      )}

      {v.client_wants && (
        <div className="text-sm text-slate-300"><span className="text-slate-500">{t("vip_wants", lang)}: </span>{v.client_wants}</div>
      )}

      {!data.is_owner && v.availability?.length > 0 && (
        <div>
          <div className="text-sm font-semibold text-amber-200 mb-2 flex items-center gap-1.5"><Calendar size={15} /> {t("vip_book_btn", lang)}</div>
          <div className="flex flex-wrap gap-2" data-testid="vip-slots">
            {v.availability.map((s, i) => (
              <button key={i} data-testid={`vip-book-slot-${i}`} onClick={() => setSlot(s)} className="text-xs bg-white/5 gold-hairline rounded-lg px-3 py-1.5 text-slate-200 hover:bg-white/10 transition-colors">{s.date} · {s.from}–{s.to}</button>
            ))}
          </div>
        </div>
      )}


      <Dialog open={!!slot} onOpenChange={(o) => { if (!o) { setSlot(null); setPlace(null); setLoc({}); setExtraHours(0); setAgree(false); } }}>
        <DialogContent className="bg-[#161018] border-white/10 text-white max-w-sm max-h-[85vh] overflow-y-auto" data-testid="vip-book-dialog">
          <DialogHeader><DialogTitle className="font-serif-luxe text-xl">{data.name || name}</DialogTitle></DialogHeader>
          {slot && <p className="text-sm text-slate-400"><Calendar size={13} className="inline me-1 -mt-0.5" />{slot.date} · {slot.from}–{slot.to}</p>}

          {hasPlaces && (
            <div data-testid="vip-book-place">
              <div className="text-xs font-semibold text-amber-200 mb-1.5">{t("vip_choose_place", lang)}</div>
              <div className="flex flex-wrap gap-2">
                {v.places.map((pv) => (
                  <button key={pv} data-testid={`vip-book-place-${pv}`} onClick={() => setPlace(pv)}
                    className={`text-xs px-3 py-1.5 rounded-full border transition-colors ${place === pv ? "bg-amber-500/20 border-amber-500/50 text-amber-200" : "bg-white/5 border-white/10 text-slate-300 hover:bg-white/10"}`}>{pv === "own" ? t("place_vip", lang) : placeLabel(pv, lang)}</button>
                ))}
              </div>
              {place && place !== "own" && (
                <div className="mt-2" data-testid="vip-book-address">
                  <div className="text-[11px] text-slate-400 mb-1">{t("vip_addr_hint", lang)}</div>
                  <VerifiedAddressForm value={loc} onChange={setLoc} needVenue={false} testid="vip-book-addr" />
                </div>
              )}
              {place === "own" && <div className="mt-2 text-[11px] text-sky-300 flex items-start gap-1"><Calendar size={11} className="mt-0.5 shrink-0" /> {t("own_addr_auto", lang)}</div>}
            </div>
          )}

          <ExtraHoursStepper label={extraLabel(lang)} each={t("bk_each", lang)} value={extraHours} onChange={setExtraHours} price={extra} testid="vip-book-extra-hours" />
          <DateCommitmentNote testid="vip-book-commitment" checked={agree} onCheckedChange={setAgree} />
          <div className="text-xs font-semibold text-amber-200">{t("vip_book_btn", lang)}</div>
          <div className="grid grid-cols-2 gap-2">
            {PRICE_KEYS.map((p) => priceFor(p.k) > 0 && (
              <Button key={p.k} data-testid={`vip-book-${p.k}`} onClick={() => book(p.k)} disabled={busy || !agree} className="rose-btn text-white border-0 h-auto py-2 flex-col">
                <span className="text-xs">{priceLabel(p.k, lang)}{extraHours > 0 ? ` + ${extraHours}h` : ""}</span><span className="font-mono-num">🪙 {priceFor(p.k) + extraHours * extra}</span>
              </Button>
            ))}
          </div>
          <p className="text-[11px] text-slate-500">Монеты удерживаются в эскроу до подтверждения встречи.</p>
        </DialogContent>
      </Dialog>
    </div>
  );
}
