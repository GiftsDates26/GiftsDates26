import React, { useState } from "react";
import { Car, Loader2, MapPin, Check, X, Send, Ban, Pencil, Hourglass } from "lucide-react";
import { toast } from "sonner";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import VerifiedAddressForm, { addressReady, addrPayload, addrErrKey } from "./VerifiedAddressForm";
import DirectionsButton from "./DirectionsButton";
import { api } from "../lib/api";
import { useApp } from "../context/AppContext";
import { t } from "../lib/i18n";

const errMsg = (e, lang) => {
  const d = e.response?.data?.detail || "";
  const k = addrErrKey(d) || { ADDRESS_REQUIRED: "pu_addr_err", PICKUP_PENDING: "pu_pending_err", NO_TAXI_REQUEST: "pu_no_taxi_err", "Insufficient coins": "not_enough_coins" }[d];
  return k ? t(k, lang) : d || "Error";
};

function AddressForm({ b, onDone, onClose, lang }) {
  const pu = b.pickup || {};
  const [loc, setLoc] = useState(pu.address ? { address: pu.address, city: pu.city, postal_code: pu.postal_code, country: pu.country, lat: pu.lat, lng: pu.lng, verified: pu.lat != null, confirmed: !!pu.unverified } : {});
  const [time, setTime] = useState(pu.time || b.start);
  const [note, setNote] = useState(pu.note || "");
  const [busy, setBusy] = useState(false);
  const send = async () => {
    if (!addressReady(loc, false)) { toast.error(t("av_required_nv", lang)); return; }
    setBusy(true);
    try { await api.post(`/vip/schedule/bookings/${b.id}/pickup/address`, { ...addrPayload(loc), time, note }); toast.success(t("pu_addr_sent_toast", lang)); onClose?.(); onDone?.(); }
    catch (e) { toast.error(errMsg(e, lang)); }
    finally { setBusy(false); }
  };
  return (
    <div className="space-y-2.5" data-testid={`vs-pickup-form-${b.id}`}>
      <p className="text-xs text-slate-300">{t("pu_addr_intro", lang)}</p>
      <VerifiedAddressForm value={loc} onChange={setLoc} needVenue={false} testid={`vs-pickup-addr-${b.id}`} />
      <div className="flex gap-2">
        <div className="w-28 shrink-0">
          <label className="text-[11px] text-slate-400">{t("pu_time", lang)}</label>
          <Input data-testid={`vs-pickup-time-${b.id}`} type="time" value={time} onChange={(e) => setTime(e.target.value)} className="bg-white/5 border-white/10 h-9 mt-1" />
        </div>
        <div className="flex-1">
          <label className="text-[11px] text-slate-400">{t("pu_note_label", lang)}</label>
          <Input data-testid={`vs-pickup-note-${b.id}`} value={note} onChange={(e) => setNote(e.target.value)} placeholder={t("pu_note_ph", lang)} className="bg-white/5 border-white/10 h-9 mt-1" />
        </div>
      </div>
      <div className="flex gap-2">
        <Button data-testid={`vs-pickup-send-${b.id}`} size="sm" disabled={busy || !addressReady(loc, false)} onClick={send} className="bg-sky-600 hover:bg-sky-500 text-white border-0 h-9">
          {busy ? <Loader2 size={14} className="animate-spin" /> : <><MapPin size={14} className="me-1" />{t("pu_addr_send", lang)}</>}
        </Button>
        {onClose && <Button data-testid={`vs-pickup-close-form-${b.id}`} size="sm" variant="outline" onClick={onClose} className="bg-white/5 border-white/15 text-slate-300 hover:bg-white/10 h-9"><X size={14} /></Button>}
      </div>
    </div>
  );
}

function InviterChoices({ b, onDone, onCancel, lang }) {
  const { refreshUser } = useApp();
  const [busy, setBusy] = useState(null);
  const post = async (key, url, msg) => {
    setBusy(key);
    try { await api.post(url); toast.success(t(msg, lang)); await refreshUser(); onDone?.(); }
    catch (e) { toast.error(errMsg(e, lang)); }
    finally { setBusy(null); }
  };
  const spin = (k, el) => (busy === k ? <Loader2 size={14} className="animate-spin" /> : el);
  return (
    <div className="flex flex-wrap gap-2 pt-1">
      <Button data-testid={`vs-pickup-accept-${b.id}`} size="sm" disabled={!!busy} onClick={() => post("ok", `/vip/schedule/bookings/${b.id}/pickup/accept`, "pu_accepted_toast")} className="bg-emerald-600 hover:bg-emerald-500 text-white border-0 h-9">
        {spin("ok", <><Check size={14} className="me-1" />{t("pu_confirm_loc", lang)}</>)}
      </Button>
      {b.taxi?.status === "pending" && (
        <Button data-testid={`vs-pickup-taxi-instead-${b.id}`} size="sm" disabled={!!busy} onClick={() => post("taxi", `/vip/schedule/bookings/${b.id}/taxi/send`, "vt_sent_toast")} className="bg-amber-500 hover:bg-amber-400 text-black border-0 h-9">
          {spin("taxi", <><Send size={14} className="me-1" />{t("pu_taxi_instead", lang).replace("{c}", b.taxi.coins)}</>)}
        </Button>
      )}
      <Button data-testid={`vs-pickup-cancel-date-${b.id}`} size="sm" variant="outline" disabled={!!busy} onClick={() => onCancel?.(b, "outgoing")} className="bg-white/5 border-rose-500/40 text-rose-300 hover:bg-rose-500/10 h-9">
        <Ban size={14} className="me-1" />{t("pu_cancel_date", lang)}
      </Button>
    </div>
  );
}

function OfferButton({ b, onDone, lang }) {
  const [busy, setBusy] = useState(false);
  const go = async () => {
    setBusy(true);
    try { await api.post(`/vip/schedule/bookings/${b.id}/pickup/offer`); toast.success(t("pu_sent_toast", lang)); onDone?.(); }
    catch (e) { toast.error(errMsg(e, lang)); }
    finally { setBusy(false); }
  };
  return (
    <div className="space-y-1.5">
      <p className="text-xs text-slate-400">{t("pu_form_note", lang)}</p>
      <Button data-testid={`vs-pickup-propose-${b.id}`} size="sm" variant="outline" disabled={busy} onClick={go} className="bg-white/5 border-sky-500/40 text-sky-200 hover:bg-sky-500/10 h-9">
        {busy ? <Loader2 size={14} className="animate-spin" /> : <><Car size={14} className="me-1" />{t("pu_propose", lang)}</>}
      </Button>
    </div>
  );
}

export default function VipPickupBlock({ b, who, onDone, onCancel }) {
  const { lang } = useApp();
  const [editing, setEditing] = useState(false);
  const pu = b.pickup;
  const st = pu?.status;
  const active = ["pending", "confirmed"].includes(b.status);
  const canOffer = who === "outgoing" && active && b.taxi?.status === "pending" && (!pu || st === "declined");
  if (!pu && !canOffer) return null;
  const addr = pu?.address && [pu.address, pu.postal_code, pu.city, pu.country].filter(Boolean).join(", ");
  const dim = ["taxi_instead", "declined"].includes(st);
  return (
    <div className="w-full mt-3 rounded-xl border border-sky-500/25 bg-sky-500/5 p-3 space-y-2" data-testid={`vs-pickup-${b.id}`}>
      {pu && st !== "declined" && (
        <div className={`text-xs space-y-1 ${dim ? "text-slate-500" : "text-sky-100"}`} data-testid={`vs-pickup-status-${b.id}`}>
          <div className="flex items-center gap-1.5 font-semibold">
            {st === "offered" ? <Hourglass size={13} /> : <Car size={13} />}
            {t(st === "offered" ? (who === "incoming" ? "pu_st_offered_vip" : "pu_st_offered") : `pu_st_${st}`, lang)}
          </div>
          {addr && <div className="flex items-start gap-1.5 text-slate-300"><MapPin size={12} className="mt-0.5 shrink-0" /> {addr} · {t("pu_time", lang)} {pu.time}</div>}
          {pu.note ? <div className="text-slate-400 italic">“{pu.note}”</div> : null}
        </div>
      )}
      {canOffer && <OfferButton b={b} onDone={onDone} lang={lang} />}
      {who === "incoming" && active && st === "offered" && <AddressForm b={b} onDone={onDone} lang={lang} />}
      {who === "incoming" && active && st === "address_set" && (editing ? <AddressForm b={b} onDone={onDone} onClose={() => setEditing(false)} lang={lang} /> : (
        <Button data-testid={`vs-pickup-edit-${b.id}`} size="sm" variant="outline" onClick={() => setEditing(true)} className="bg-white/5 border-white/15 text-slate-300 hover:bg-white/10 h-8 text-xs">
          <Pencil size={12} className="me-1" />{t("pu_edit", lang)}
        </Button>
      ))}
      {who === "outgoing" && active && st === "address_set" && <InviterChoices b={b} onDone={onDone} onCancel={onCancel} lang={lang} />}
      {who === "outgoing" && st === "accepted" && b.status === "confirmed" && <DirectionsButton loc={pu} testid={`vs-pickup-directions-${b.id}`} />}
    </div>
  );
}
