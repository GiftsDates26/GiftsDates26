import React, { useEffect, useState, useCallback, useRef } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { toast } from "sonner";
import { CalendarHeart, MapPin, Clock, Coins, ShieldAlert, Flag, Camera, Car, Check, X, MessageCircle, Send, CalendarPlus, Lock } from "lucide-react";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { api, fileUrl } from "../lib/api";
import { useApp } from "../context/AppContext";
import { t } from "../lib/i18n";
import { MapsLink } from "../components/AddressPicker";
import DirectionsButton from "../components/DirectionsButton";
import DateBookingList from "../components/DateBookingList";
import CancelledDates from "../components/CancelledDates";
import { EmptyDates, DatesStatTiles, DatesTabBar, TabEmpty } from "../components/DatesUI";
import CountdownBadge from "../components/CountdownBadge";
import LiveLocation from "../components/LiveLocation";
import DateReportForm, { DateStartedNote, ReportReplyBlock, ReportStatusNote } from "../components/DateReportForm";
import { DATE_TABS, tabOf, countByTab } from "../lib/dateFilters";
import AddToCalendar from "../components/AddToCalendar";
import VerifiedAddressForm, { addressReady, addrErrKey, addrPayload, UnverifiedNote } from "../components/VerifiedAddressForm";
import DatesToday from "../components/DatesToday";
import DatesEarnings from "../components/DatesEarnings";
import CancelPreviewDialog from "../components/CancelPreviewDialog";

const FALLBACK = "https://images.unsplash.com/photo-1544005313-94ddf0286df2?w=200&q=80";
const TERMINAL = ["COMPLETED", "COMPLETED_AUTO", "CANCELLED", "CANCELLED_TRANSPORTATION", "REFUNDED"];
const CHAT_STATUSES = ["DATE_CONFIRMED", "DATE_COMPLETED_PENDING_VERIFICATION", "PHOTO_VERIFICATION_PENDING", "COMPLETED", "COMPLETED_AUTO", "REPORTED", "UNDER_ADMIN_REVIEW"];

function DateChat({ did, meId, lang }) {
  const tr = (k) => t(k, lang);
  const [msgs, setMsgs] = useState([]);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const endRef = React.useRef(null);
  const load = useCallback(() => { api.get(`/invites/${did}/messages`).then(r => setMsgs(r.data.messages || [])).catch(() => {}); }, [did]);
  useEffect(() => { load(); const id = setInterval(load, 10000); return () => clearInterval(id); }, [load]);
  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth" }); }, [msgs.length]);
  const send = async () => {
    const t2 = text.trim(); if (!t2) return;
    setBusy(true);
    try { const r = await api.post(`/invites/${did}/messages`, { text: t2 }); setMsgs(m => [...m, r.data.message]); setText(""); }
    catch (e) { toast.error(e.response?.data?.detail || t("failed", lang)); }
    finally { setBusy(false); }
  };
  return (
    <div className="mt-3 rounded-lg border border-sky-500/30 bg-sky-500/5 p-3" data-testid={`date-chat-${did}`}>
      <div className="text-xs font-semibold text-sky-200 mb-2 flex items-center gap-1"><MessageCircle size={13} />{tr("id_chat")}</div>
      <div className="max-h-48 overflow-y-auto space-y-1.5 mb-2" data-testid={`date-chat-messages-${did}`}>
        {msgs.length === 0 && <div className="text-[11px] text-slate-500 py-2">{tr("id_chat_empty")}</div>}
        {msgs.map(m => {
          const mine = m.from_id === meId;
          return <div key={m.id} className={`flex ${mine ? "justify-end" : "justify-start"}`}>
            <span className={`text-xs px-2.5 py-1.5 rounded-2xl max-w-[80%] break-words ${mine ? "bg-rose-500/25 text-rose-50" : "bg-white/10 text-slate-200"}`}>{m.text}</span>
          </div>;
        })}
        <div ref={endRef} />
      </div>
      <div className="flex gap-2">
        <Input data-testid={`date-chat-input-${did}`} value={text} onChange={e => setText(e.target.value)} onKeyDown={e => e.key === "Enter" && send()} placeholder={tr("id_chat_ph")} className="bg-white/5 border-white/10 h-9" />
        <Button data-testid={`date-chat-send-${did}`} disabled={busy || !text.trim()} onClick={send} className="rose-btn text-white border-0 h-9"><Send size={14} /></Button>
      </div>
    </div>
  );
}

function DateTimeRange({ id, start }) {
  const { lang } = useApp();
  const s = new Date(start), e = new Date(s.getTime() + 150 * 60000);
  const hm = (x) => x.toLocaleTimeString(lang, { hour: "2-digit", minute: "2-digit" });
  const nextDay = e.toDateString() !== s.toDateString();
  return (
    <div className="mt-1.5 inline-flex flex-wrap items-center gap-x-2 gap-y-1 rounded-lg border border-white/10 bg-white/[0.04] px-2.5 py-1.5 text-xs" data-testid={`date-time-range-${id}`}>
      <Clock size={12} className="text-rose-300" />
      <span className="text-slate-200">{s.toLocaleDateString(lang, { weekday: "short", day: "numeric", month: "short" })}</span>
      <span className="text-slate-500">·</span>
      <span className="text-slate-400">{t("dt_starts", lang)}</span><b className="font-mono-num text-white" data-testid={`date-time-start-${id}`}>{hm(s)}</b>
      <span className="text-rose-300">→</span>
      <span className="text-slate-400">{t("dt_ends", lang)}</span><b className="font-mono-num text-white" data-testid={`date-time-end-${id}`}>{hm(e)}{nextDay ? " +1" : ""}</b>
      <span className="text-slate-500">(2.5h)</span>
    </div>
  );
}

function SwitchToTaxi({ d, busy, onSend }) {
  const { lang } = useApp();
  const tr = (k, vars) => { let s = t(k, lang); if (vars) Object.entries(vars).forEach(([n, v]) => (s = s.replace(`{${n}}`, v))); return s; };
  const n = Number(d.transportation?.taxi_amount || 0);
  if (n <= 0) return null;
  return (
    <div className="w-full rounded-lg border border-amber-500/30 bg-amber-500/5 p-3 space-y-2" data-testid={`date-switch-taxi-panel-${d.id}`}>
      <div className="text-xs text-amber-100">{tr("sw_hint", { n })}</div>
      <Button data-testid={`date-switch-taxi-${d.id}`} disabled={busy} onClick={() => window.confirm(tr("sw_confirm", { n })) && onSend()} variant="outline" className="h-9 bg-amber-500/10 border-amber-500/40 text-amber-200 hover:bg-amber-500/20"><Car size={14} className="me-1" />{tr("sw_btn")} 🪙{n}</Button>
    </div>
  );
}

function Countdown({ to, label }) {
  const [now, setNow] = useState(Date.now());
  useEffect(() => { const id = setInterval(() => setNow(Date.now()), 1000); return () => clearInterval(id); }, []);
  const ms = new Date(to).getTime() - now;
  if (ms <= 0) return null;
  const s = Math.floor(ms / 1000), h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), ss = s % 60;
  return <span className="font-mono-num text-amber-300">{label} {String(h).padStart(2, "0")}:{String(m).padStart(2, "0")}:{String(ss).padStart(2, "0")}</span>;
}


function DateCard({ d, reload }) {
  const { lang, user } = useApp();
  const tr = (k, vars) => { let s = t(k, lang); if (vars) Object.entries(vars).forEach(([n, v]) => (s = s.replace(`{${n}}`, v))); return s; };
  const nav = useNavigate();
  const [busy, setBusy] = useState(false);
  const [choose, setChoose] = useState("");
  const [loc, setLoc] = useState({});
  const [taxi, setTaxi] = useState(""); const [pickup, setPickup] = useState({});
  const [showReport, setShowReport] = useState(false);
  const [showVerify, setShowVerify] = useState(false); const [vfile, setVfile] = useState(null); const [vok, setVok] = useState(false);
  const isInv = d.role === "inviter";
  const w = d.windows || {};
  const nowMs = Date.now();
  const reportOpen = w.report_open && nowMs >= new Date(w.report_open).getTime() && nowMs <= new Date(w.report_close).getTime();
  const canVerify = w.verify_at && nowMs >= new Date(w.verify_at).getTime();
  const chatEnabled = CHAT_STATUSES.includes(d.status);
  const [showChat, setShowChat] = useState(false);
  const _calEvent = () => {
    const loc = d.location || {};
    const title = `GiftsDates: ${d.chosen_idea?.name || "Date"} · ${d.other?.name || ""}`.trim();
    const place = [loc.venue, loc.address, loc.city, loc.country].filter(Boolean).join(", ");
    const s = loc.scheduled_start ? new Date(loc.scheduled_start) : null;
    const e = loc.scheduled_end ? new Date(loc.scheduled_end) : (s ? new Date(s.getTime() + 3 * 3600 * 1000) : null);
    return { title, place, s, e };
  };
  const showCal = !!d.location?.scheduled_start && !["CANCELLED", "CANCELLED_TRANSPORTATION", "REFUNDED"].includes(d.status);

  const statusLabel = () => { const l = t(`ds_${d.status}`, lang); return l === `ds_${d.status}` ? d.status_label : l; };
  const stepText = () => {
    const o = d.other?.name || "…";
    const rk = isInv ? `dni_${d.status}` : `dnr_${d.status}`;
    let s = t(rk, lang);
    if (s === rk) s = t(`dn_${d.status}`, lang);
    if (s === `dn_${d.status}`) return d.next_step;
    return s.replace("{o}", o);
  };

  const act = async (fn) => { setBusy(true); try { await fn(); await reload(); } catch (e) { const dt = e.response?.data?.detail; toast.error(addrErrKey(dt) ? tr(addrErrKey(dt)) : dt || tr("failed")); } finally { setBusy(false); } };
  const post = (path, body) => api.post(`/invites/${d.id}${path}`, body);
  const cancelLocked = !!d.location?.scheduled_start && Date.now() >= new Date(d.location.scheduled_start).getTime() - 30 * 60000;

  const refuseSplit = () => {
    const total = Number(d.total_hold || d.coins || 0);
    const tp = d.transportation || {};
    const taxi = tp.type === "taxi" && tp.status === "confirmed" ? Math.min(total, Number(tp.taxi_amount || 0)) : 0;
    const base = total - taxi, inv = Math.floor(base / 2), rec = Math.floor(base / 4);
    return { total, taxi, inv: inv + taxi, rec, fee: base - inv - rec };
  };
  const refuseWarningText = () => {
    const { total, inv, rec, fee } = refuseSplit();
    return tr("id_refuse_warning", { total, inv, rec, fee });
  };
  const refuseTransport = () => {
    if (window.confirm(refuseWarningText() + "\n\n" + tr("id_refuse_confirm"))) act(() => post("/transport/refuse"));
  };
  const rejectLocation = () => {
    const total = Number(d.total_hold || d.coins || 0);
    if (window.confirm(tr("id_reject_location_warning", { total }) + "\n\n" + tr("id_reject_location_confirm"))) act(() => post("/location/reject"));
  };
  const rejectPickup = () => {
    const total = Number(d.total_hold || d.coins || 0);
    if (window.confirm(tr("id_reject_date_warning", { total }) + "\n\n" + tr("id_reject_location_confirm"))) act(() => post("/pickup/reject"));
  };
  const [cancelOpen, setCancelOpen] = useState(false);
  const cancelDate = () => setCancelOpen(true);
  const cancelInfo = () => {
    const { total, inv, rec, fee, taxi } = refuseSplit();
    return { total, taxi, split: isInv ? { refund: inv, comp: rec, fee } : { refund: total, comp: 0, fee: 0 } };
  };

  const started = !!d.location?.scheduled_start && nowMs >= new Date(d.location.scheduled_start).getTime();
  const submitReport = async (payload) => { await post("/report", payload); setShowReport(false); await reload(); };
  const submitVerify = () => act(async () => {
    if (!vfile || !vok) { throw { response: { data: { detail: tr("id_verify_required") } } }; }
    const fd = new FormData(); fd.append("file", vfile); fd.append("confirm", "true"); fd.append("note", "");
    await api.post(`/invites/${d.id}/verify`, fd, { headers: { "Content-Type": "multipart/form-data" } });
    toast.success(tr("id_verify_sent")); setShowVerify(false);
  });

  return (
    <div className="rounded-2xl border border-white/10 bg-[#161320] p-4" data-testid={`date-card-${d.id}`}>
      <div className="flex gap-3">
        <img src={d.other?.photo ? fileUrl(d.other.photo) : FALLBACK} onError={e => e.currentTarget.src = FALLBACK} alt=""
          onClick={() => nav(`/profile/${d.other?.id}`)} data-testid={`date-card-photo-${d.id}`}
          className="w-16 h-16 rounded-xl object-cover cursor-pointer flex-shrink-0" />
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between gap-2">
            <h4 className="font-serif-luxe text-lg truncate">{d.other?.name}{d.other?.age ? `, ${d.other.age}` : ""}</h4>
            <span className="text-[10px] px-2 py-0.5 rounded-full bg-white/10 text-slate-300 uppercase tracking-wide" data-testid={`date-status-${d.id}`}>{statusLabel()}</span>
          </div>
          {["DATE_CONFIRMED", "DATE_COMPLETED_PENDING_VERIFICATION"].includes(d.status) && d.location?.scheduled_start && <div className="mt-1.5"><CountdownBadge to={d.location.scheduled_start} testid={`date-countdown-${d.id}`} /></div>}
          <p className="text-xs text-slate-400 mt-0.5" data-testid={`date-next-${d.id}`}>➜ {stepText()}</p>
          {d.chosen_idea && <div className="text-sm text-rose-200 mt-1"><CalendarHeart size={13} className="inline me-1" />{d.chosen_idea.name}</div>}
          {!d.chosen_idea && d.options && <div className="text-xs text-slate-300 mt-1">{tr("id_options")}: {d.options.map(o => o.name).join(" · ")}</div>}
          {d.location?.venue && <div className="text-xs text-slate-400 mt-1"><MapPin size={12} className="inline me-1" />{[d.location.venue, d.location.address, d.location.city].filter(Boolean).join(", ")} <MapsLink loc={d.location} testid={`date-maps-${d.id}`} /><UnverifiedNote show={d.location?.unverified} testid={`date-loc-unverified-${d.id}`} /></div>}
          {!isInv && (d.location?.scheduled_start || d.proposed_start) ? <DateTimeRange id={d.id} start={d.location?.scheduled_start || d.proposed_start} />
            : d.location?.scheduled_start && <div className="text-xs text-slate-400"><Clock size={12} className="inline me-1" />{new Date(d.location.scheduled_start).toLocaleString()} (3h)</div>}
          {d.transportation?.status && <div className="text-xs text-sky-300 mt-0.5"><Car size={12} className="inline me-1" />{d.transportation.type}: {d.transportation.status}{d.transportation.taxi_amount ? ` · 🪙${d.transportation.taxi_amount}` : ""}{d.transportation.pickup_address ? ` · ${d.transportation.pickup_address}` : ""}<UnverifiedNote show={d.transportation?.pickup_unverified} testid={`date-pickup-unverified-${d.id}`} /></div>}
          <div className="text-xs text-amber-300/90 mt-0.5"><Coins size={12} className="inline me-1" />🪙 {d.total_hold || d.coins}{d.gift ? ` + ${tr("id_gift")} ${d.gift.icon || ""}` : ""}</div>
          {reportOpen && <div className="text-[11px] mt-1"><Countdown to={w.report_close} label={tr("id_report_closes")} /></div>}
        </div>
      </div>

      {/* Actions */}
      <div className="mt-3 flex flex-wrap gap-2">
        {d.status === "INVITATION_SENT" && !isInv && (
          <div className="w-full space-y-2" data-testid={`date-choose-${d.id}`}>
            <div className="text-[11px] text-slate-400">{tr("id_choose_or_reject")}</div>
            <div className="flex flex-wrap gap-2">{d.options.map(o => (
              <button key={o.idea_id} data-testid={`date-choose-opt-${o.idea_id}`} onClick={() => setChoose(o.idea_id)}
                className={`text-xs px-3 py-1.5 rounded-full border ${choose === o.idea_id ? "bg-rose-500/20 border-rose-500/50 text-rose-200" : "bg-white/5 border-white/10 text-slate-300"}`}>{o.name}</button>))}</div>
            <div className="flex flex-wrap gap-2 items-center">
              <Button data-testid={`date-choose-confirm-${d.id}`} disabled={busy || !choose} onClick={() => act(() => post("/choose", { idea_id: choose }))} className="rose-btn text-white border-0 h-9"><Check size={14} className="me-1" />{tr("id_confirm_choice")}</Button>
              <Button data-testid={`date-reject-${d.id}`} disabled={busy} onClick={() => { const when = (d.location?.scheduled_start || d.proposed_start) ? new Date(d.location?.scheduled_start || d.proposed_start).toLocaleString() : ""; if (window.confirm(tr("id_reject_confirm_lock").replace("{when}", when))) act(() => post("/cancel")); }} variant="outline" className="h-9 bg-rose-500/10 border-rose-500/40 text-rose-300 hover:bg-rose-500/20"><X size={14} className="me-1" />{tr("id_reject")}</Button>
            </div>
            <div className="flex items-start gap-1.5 text-[11px] text-amber-200/90 rounded-lg border border-amber-500/30 bg-amber-500/5 p-2" data-testid={`date-reject-warning-${d.id}`}>
              <ShieldAlert size={13} className="mt-0.5 shrink-0 text-amber-300" />
              <span>{tr("id_reject_warning").replace("{coins}", d.total_hold || d.coins)}</span>
            </div>
            {(d.location?.scheduled_start || d.proposed_start) && (
              <div className="flex items-start gap-1.5 text-[11px] text-rose-200/90 rounded-lg border border-rose-500/30 bg-rose-500/5 p-2" data-testid={`date-reject-lock-note-${d.id}`}>
                <Lock size={13} className="mt-0.5 shrink-0 text-rose-300" />
                <span>{tr("id_reject_slot_lock").replace("{when}", new Date(d.location?.scheduled_start || d.proposed_start).toLocaleString())}</span>
              </div>
            )}
          </div>
        )}
        {d.status === "DATE_ACTIVITY_SELECTED" && isInv && (
          <div className="w-full space-y-2 rounded-lg border border-white/10 p-2" data-testid={`date-location-${d.id}`}>
            <div className="text-xs text-amber-200">{tr("id_choose_location")}</div>
            {d.proposed_start && (
              <div className="flex items-center gap-1.5 text-[11px] text-slate-300 rounded-md bg-white/5 border border-white/10 px-2 py-1.5" data-testid={`date-fixed-time-${d.id}`}>
                <Clock size={12} className="text-rose-300 shrink-0" />
                <span>{tr("id_location_fixed_time").replace("{when}", new Date(d.proposed_start).toLocaleString())}</span>
              </div>
            )}
            <VerifiedAddressForm value={loc} onChange={setLoc} testid={`date-location-addr-${d.id}`} />
            <Button data-testid={`date-location-submit-${d.id}`} disabled={busy || !addressReady(loc)} onClick={() => act(() => post("/location", { venue: loc.venue, ...addrPayload(loc) }))} className="rose-btn text-white border-0 h-9">{tr("id_propose_location")}</Button>
          </div>
        )}
        {d.status === "LOCATION_PROPOSED" && !isInv && (
          <div className="w-full space-y-2" data-testid={`date-confirm-loc-${d.id}`}>
            <div className="flex flex-wrap gap-2">
              <Button data-testid={`date-confirm-location-${d.id}`} disabled={busy} onClick={() => act(() => post("/location/confirm"))} className="rose-btn text-white border-0 h-9"><Check size={14} className="me-1" />{tr("id_confirm_location")}</Button>
              <Button data-testid={`date-reject-location-${d.id}`} disabled={busy} onClick={rejectLocation} variant="outline" className="h-9 bg-rose-500/10 border-rose-500/40 text-rose-300"><X size={14} className="me-1" />{tr("id_reject_location")}</Button>
            </div>
            <div className="text-[11px] text-amber-200/90 rounded-lg border border-amber-500/30 bg-amber-500/5 p-2 space-y-2" data-testid={`date-reject-location-warning-${d.id}`}>
              <div className="flex items-start gap-1.5">
                <ShieldAlert size={13} className="mt-0.5 shrink-0 text-amber-300" />
                <span>{tr("id_reject_location_note", { total: Number(d.total_hold || d.coins || 0) })}</span>
              </div>
              <div className="flex flex-wrap gap-2 items-center ps-5" data-testid={`date-taxi-shortcut-${d.id}`}>
                <Input data-testid={`date-taxi-amount-${d.id}`} type="number" min="1" value={taxi} onChange={e => setTaxi(e.target.value)} placeholder={tr("id_taxi_amount_ph")} className="bg-white/5 border-amber-500/30 h-9 max-w-[160px] text-slate-100" />
                <Button data-testid={`date-taxi-request-${d.id}`} disabled={busy || !(parseInt(taxi) > 0)} onClick={() => act(async () => { await post("/taxi/request", { amount: parseInt(taxi) }); toast.success(tr("taxi_requested_toast")); })} className="h-9 bg-amber-500 hover:bg-amber-400 text-black border-0 font-semibold transition-colors"><Car size={14} className="me-1" />{tr("id_request_taxi")}</Button>
              </div>
            </div>
          </div>
        )}
        {d.status === "TAXI_REQUESTED" && isInv && (
          <div className="w-full space-y-2" data-testid={`date-transport-${d.id}`}>
            <div className="flex flex-wrap gap-2">
              <Button data-testid={`date-taxi-confirm-${d.id}`} disabled={busy} onClick={() => act(() => post("/taxi/confirm"))} className="rose-btn text-white border-0 h-9">{tr("id_confirm_pay_taxi")} 🪙{d.transportation?.taxi_amount}</Button>
              <Button data-testid={`date-pickup-offer-${d.id}`} disabled={busy} onClick={() => act(() => post("/pickup/offer"))} variant="outline" className="h-9 bg-white/5 border-white/15">{tr("id_offer_pickup")}</Button>
              <Button data-testid={`date-transport-refuse-${d.id}`} disabled={busy} onClick={refuseTransport} variant="outline" className="h-9 bg-rose-500/10 border-rose-500/40 text-rose-300">{tr("id_refuse")}</Button>
            </div>
            <div className="flex items-start gap-1.5 text-[11px] text-amber-200/90 rounded-lg border border-amber-500/30 bg-amber-500/5 p-2" data-testid={`date-refuse-warning-${d.id}`}>
              <ShieldAlert size={13} className="mt-0.5 shrink-0 text-amber-300" />
              <span>{refuseWarningText()}</span>
            </div>
          </div>
        )}
        {d.status === "PICKUP_ADDRESS_PENDING" && !isInv && (
          <div className="w-full space-y-2 rounded-lg border border-white/10 p-2" data-testid={`date-pickup-addr-${d.id}`}>
            <div className="text-xs text-amber-200">{tr("id_pickup_share_hint")}</div>
            <VerifiedAddressForm value={pickup} onChange={setPickup} testid={`date-pickup-addr-form-${d.id}`} />
            <div className="flex flex-wrap gap-2">
              <Button data-testid={`date-pickup-submit-${d.id}`} disabled={busy || !addressReady(pickup)} onClick={() => act(() => post("/pickup/address", {
                pickup_address: [pickup.venue, pickup.address, pickup.city, pickup.postal_code, pickup.country].filter(Boolean).join(", "),
                venue: pickup.venue, street: pickup.address, ...addrPayload(pickup),
              }))} className="rose-btn text-white border-0 h-9"><Check size={14} className="me-1" />{tr("id_accept_share_pickup")}</Button>
              <Button data-testid={`date-pickup-reject-${d.id}`} disabled={busy} onClick={rejectPickup} variant="outline" className="h-9 bg-rose-500/10 border-rose-500/40 text-rose-300"><X size={14} className="me-1" />{tr("id_reject_date")}</Button>
            </div>
            <div className="flex items-start gap-1.5 text-[11px] text-amber-200/90 rounded-lg border border-amber-500/30 bg-amber-500/5 p-2" data-testid={`date-pickup-reject-warning-${d.id}`}>
              <ShieldAlert size={13} className="mt-0.5 shrink-0 text-amber-300" />
              <span>{tr("id_reject_date_note", { total: Number(d.total_hold || d.coins || 0) })}</span>
            </div>
          </div>
        )}
        {d.status === "PICKUP_ADDRESS_SELECTED" && isInv && (
          <div className="w-full space-y-2">
            <div className="flex flex-wrap gap-2">
              <Button data-testid={`date-pickup-confirm-${d.id}`} disabled={busy} onClick={() => act(() => post("/pickup/confirm"))} className="rose-btn text-white border-0 h-9">{tr("id_confirm_pickup")}</Button>
              <Button data-testid={`date-pay-taxi-instead-${d.id}`} disabled={busy} onClick={() => act(() => post("/taxi/confirm"))} variant="outline" className="h-9 bg-white/5 border-white/15">{tr("id_pay_taxi_instead")}{Number(d.transportation?.taxi_amount) > 0 && <span className="ms-1 font-mono-num text-amber-300" data-testid={`date-pay-taxi-amount-${d.id}`}>🪙{d.transportation.taxi_amount}</span>}</Button>
              <Button data-testid={`date-transport-refuse-${d.id}`} disabled={busy} onClick={refuseTransport} variant="outline" className="h-9 bg-rose-500/10 border-rose-500/40 text-rose-300">{tr("id_refuse")}</Button>
            </div>
            <div className="flex items-start gap-1.5 text-[11px] text-amber-200/90 rounded-lg border border-amber-500/30 bg-amber-500/5 p-2" data-testid={`date-refuse-warning-${d.id}`}>
              <ShieldAlert size={13} className="mt-0.5 shrink-0 text-amber-300" />
              <span>{refuseWarningText()}</span>
            </div>
          </div>
        )}
        {d.status === "DATE_CONFIRMED" && isInv && d.transportation?.type === "pickup" && !cancelLocked && <SwitchToTaxi d={d} busy={busy} onSend={() => act(async () => { const r = await post("/pickup/switch-to-taxi"); toast.success(tr("sw_sent_toast", { n: r.data.taxi_amount })); })} />}
        {!TERMINAL.includes(d.status) && d.status !== "PHOTO_VERIFICATION_PENDING" && !(d.status === "INVITATION_SENT" && !isInv) && !started && (
          <Button data-testid={`date-cancel-${d.id}`} disabled={busy} onClick={cancelDate} variant="outline" className="h-9 bg-rose-500/10 border-rose-500/40 text-rose-300 hover:bg-rose-500/20"><X size={14} className="me-1" />{tr("id_cancel_date")}</Button>
        )}
        {cancelOpen && (() => { const c = cancelInfo(); return (
          <CancelPreviewDialog open={cancelOpen} onOpenChange={setCancelOpen} total={c.total} taxi={c.taxi} split={c.split} byRequester={isInv}
            onConfirm={() => { setCancelOpen(false); act(() => post("/cancel")); }} />
        ); })()}
        {started && !TERMINAL.includes(d.status) && <DateStartedNote id={d.id} />}
        {d.report && <span className="text-[11px] px-2 py-1 rounded-full border border-rose-500/40 bg-rose-500/10 text-rose-200 self-center" data-testid={`date-reported-${d.id}`}>{tr("rp_under_review")}</span>}
        {reportOpen && !d.report && <Button data-testid={`date-report-${d.id}`} onClick={() => setShowReport(v => !v)} variant="outline" className="h-9 bg-rose-500/10 border-rose-500/40 text-rose-300"><Flag size={14} className="me-1" />{tr("id_report_this")}</Button>}
        {canVerify && ["DATE_CONFIRMED", "DATE_COMPLETED_PENDING_VERIFICATION"].includes(d.status) &&
          <Button data-testid={`date-verify-${d.id}`} onClick={() => setShowVerify(v => !v)} variant="outline" className="h-9 bg-emerald-500/10 border-emerald-500/40 text-emerald-300"><Camera size={14} className="me-1" />{tr("id_send_photo_conf")}</Button>}
        {chatEnabled && <Button data-testid={`date-chat-toggle-${d.id}`} onClick={() => setShowChat(v => !v)} variant="outline" className="h-9 bg-sky-500/10 border-sky-500/40 text-sky-300"><MessageCircle size={14} className="me-1" />{tr("id_chat")}</Button>}
        {showCal && (() => { const ev = _calEvent(); return <AddToCalendar id={d.id} title={ev.title} place={ev.place} start={ev.s} end={ev.e} />; })()}
        {d.status === "DATE_CONFIRMED" && (d.location?.address || d.location?.lat != null) && <DirectionsButton loc={d.location} testid={`invite-directions-${d.id}`} />}
        {isInv && d.transportation?.type === "pickup" && d.transportation?.pickup_address && ["PICKUP_ADDRESS_SELECTED", "DATE_CONFIRMED"].includes(d.status) &&
          <DirectionsButton loc={{ lat: d.transportation.pickup_lat, lng: d.transportation.pickup_lng, address: d.transportation.pickup_address }} label="dir_pickup" testid={`date-pickup-directions-${d.id}`} />}
      </div>
      {d.status === "DATE_CONFIRMED" && <div className="mt-3"><LiveLocation kind="invite" id={d.id} otherName={d.other?.name}
        venue={d.location?.lat != null && d.location?.lng != null ? `${d.location.lat},${d.location.lng}` : [d.location?.venue, d.location?.address, d.location?.city, d.location?.country].filter(Boolean).join(", ")} /></div>}

      {showReport && <DateReportForm id={d.id} onSubmit={submitReport} role={isInv ? "inviter" : "recipient"} />}
      {d.report_info?.by_me && <div className="mt-3"><ReportStatusNote id={d.id} info={d.report_info} /></div>}
      {d.report_info && !d.report_info.by_me && <div className="mt-3"><ReportReplyBlock id={d.id} info={d.report_info} onSubmit={async (p) => { await post("/report/reply", p); await reload(); }} /></div>}
      {showVerify && (
        <div className="mt-3 rounded-lg border border-emerald-500/30 bg-emerald-500/5 p-3 space-y-2" data-testid={`verify-form-${d.id}`}>
          <div className="text-xs text-emerald-200">{tr("id_verify_hint")}</div>
          <input data-testid={`verify-file-${d.id}`} type="file" accept="image/*" onChange={e => setVfile(e.target.files[0])} className="text-xs text-slate-300" />
          <label className="flex items-start gap-2 text-xs text-slate-300"><input type="checkbox" checked={vok} onChange={e => setVok(e.target.checked)} className="mt-0.5" />{tr("id_verify_confirm")}</label>
          <Button data-testid={`verify-submit-${d.id}`} disabled={busy} onClick={submitVerify} className="bg-emerald-600 hover:bg-emerald-500 text-white border-0 h-9">{tr("id_verify_send")}</Button>
        </div>
      )}
      {showChat && chatEnabled && <DateChat did={d.id} meId={user?.id} lang={lang} />}
    </div>
  );
}

export default function InviteDates() {
  const { lang } = useApp();
  const [params, setParams] = useSearchParams();
  const [data, setData] = useState(null);
  const load = useCallback(async () => { try { const r = await api.get("/invites"); setData(r.data); } catch {} }, []);
  useEffect(() => { load(); const id = setInterval(load, 20000); return () => clearInterval(id); }, [load]);

  const [booked, setBooked] = useState(null);
  const urlTab = DATE_TABS.includes(params.get("tab")) ? params.get("tab") : null;
  const [tab, setTabState] = useState(urlTab || "requests");
  const setTab = (k) => { setTabState(k); setParams({ tab: k }, { replace: true }); };
  const inv = data ? [...data.incoming.map(d => ({ d, inc: true })), ...data.outgoing.map(d => ({ d, inc: false }))] : [];
  const counts = countByTab([...inv.map(x => ({ status: x.d.status, inc: x.inc })), ...(booked || [])]);
  const picked = useRef(!!urlTab);
  useEffect(() => {
    if (picked.current || !data || !booked) return;
    picked.current = true;
    if (!counts.requests) { const first = DATE_TABS.find(k => counts[k]); if (first) setTabState(first); }
  }, [data, booked]); // eslint-disable-line
  const nothing = data && booked && inv.length + booked.length === 0;
  const shown = inv.filter(x => tabOf(x.d.status, x.inc) === tab)
    .sort((a, b) => String(b.d.created_at || "").localeCompare(String(a.d.created_at || "")));
  const bookedShown = (booked || []).filter(x => tabOf(x.status, x.inc) === tab).length;
  const todayItems = [
    ...inv.map(({ d, inc }) => ({ id: d.id, start: d.location?.scheduled_start || d.proposed_start, name: d.other?.name, place: d.location?.venue, tab: tabOf(d.status, inc), card: `date-card-${d.id}` })),
    ...(booked || []).map(b => ({ id: b.id, start: b.start, name: b.name, place: b.place, tab: tabOf(b.status, b.inc), card: `date-row-${b.id}` })),
  ];
  const openToday = (x) => { setTab(x.tab); setTimeout(() => document.querySelector(`[data-testid="${x.card}"]`)?.scrollIntoView({ behavior: "smooth", block: "center" }), 150); };
  return (
    <div className="max-w-5xl mx-auto px-4 sm:px-6 py-10" data-testid="dates-page">
      <header className="mb-6 grid gap-4 md:grid-cols-[1fr_300px] items-end">
        <div>
          <h1 className="font-serif-luxe text-4xl sm:text-5xl flex items-center gap-3"><CalendarHeart className="text-rose-400" size={30} /> {t("dates", lang)}</h1>
          <p className="text-sm text-slate-400 mt-2">{t("dates_page_sub", lang)}</p>
        </div>
        <DatesEarnings />
      </header>

      {nothing ? <EmptyDates /> : <>
        <div className="mb-4"><DatesToday items={todayItems} onOpen={openToday} /></div>
        <DatesStatTiles value={tab} onChange={setTab} counts={counts} />
        <DatesTabBar value={tab} onChange={setTab} counts={counts} />
        <div className="mt-6 space-y-6" data-testid={`dates-panel-${tab}`} key={tab}>
          <p className="text-xs text-slate-500">{t(`dp_hint_${tab}`, lang)}</p>
          {shown.length > 0 && <div className="space-y-3">
            {shown.map(({ d, inc }) => (
              <div key={d.id} className="relative">
                <span className="absolute -top-2 start-4 z-10 text-[10px] uppercase tracking-wider px-2 py-0.5 rounded-full bg-[#0D0B12] border border-white/10 text-slate-400" data-testid={`date-dir-${d.id}`}>{t(inc ? "tag_invited_you" : "tag_you_booked", lang)}</span>
                <DateCard d={d} reload={load} />
              </div>
            ))}
          </div>}
          <DateBookingList mode="regular" onItems={setBooked} tab={tab} />
          {data && booked && shown.length + bookedShown === 0 && <TabEmpty tab={tab} />}
          {tab === "cancelled" && <CancelledDates />}
        </div>
      </>}
    </div>
  );
}
