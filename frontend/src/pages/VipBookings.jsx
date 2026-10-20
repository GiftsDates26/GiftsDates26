import React, { useEffect, useState, useCallback } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "../components/ui/tabs";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import { Calendar, Clock, Check, X, Crown, Loader2, CalendarClock, Inbox, Send, Ban, MapPin, CalendarDays } from "lucide-react";
import { toast } from "sonner";
import { api } from "../lib/api";
import { useApp } from "../context/AppContext";
import VipAvailabilityEditor from "../components/VipAvailabilityEditor";
import VipDateBookModal from "../components/VipDateBookModal";
import AddToCalendar from "../components/AddToCalendar";
import CancelPreviewDialog from "../components/CancelPreviewDialog";
import DirectionsButton from "../components/DirectionsButton";
import VipTaxiBlock from "../components/VipTaxiBlock";
import VipPickupBlock from "../components/VipPickupBlock";
import ArrivedButton from "../components/ArrivedButton";
import TodayStrip from "../components/TodayStrip";
import EarningsChart from "../components/EarningsChart";
import NoShowReport, { NoShowCase } from "../components/NoShowReport";
import DeclineReasonDialog from "../components/DeclineReasonDialog";
import RunningLateButton from "../components/RunningLateButton";
import ExtendDateButton from "../components/ExtendDateButton";
import { t } from "../lib/i18n";
import { MapsLink } from "../components/AddressPicker";
import { UnverifiedNote } from "../components/VerifiedAddressForm";
import { placeLabel } from "../lib/vipCatalog";
import CancelledDates from "../components/CancelledDates";

const fmtDay = (d) => { try { const [y, m, dd] = d.split("-").map(Number); return new Date(y, m - 1, dd).toLocaleDateString(undefined, { weekday: "long", month: "long", day: "numeric" }); } catch { return d; } };

const ACCENT = { reported: "border-s-amber-500/80", pending: "border-s-amber-400/70", confirmed: "border-s-sky-400/70", completed: "border-s-emerald-400/70", declined: "border-s-rose-400/50", cancelled: "border-s-slate-500/50" };
const STATUS_BADGE = {
  reported: "bg-amber-500/15 border-amber-500/50 text-amber-200",
  pending: "bg-amber-500/15 border-amber-500/40 text-amber-300",
  confirmed: "bg-sky-500/15 border-sky-500/40 text-sky-300",
  declined: "bg-rose-500/15 border-rose-500/40 text-rose-300",
  cancelled: "bg-slate-500/15 border-slate-500/40 text-slate-300",
  completed: "bg-emerald-500/15 border-emerald-500/40 text-emerald-300",
};

function Avatar({ card }) {
  const p = card?.photo;
  const src = p ? `${api.defaults.baseURL}/files/${p}?auth=${encodeURIComponent(localStorage.getItem("gd_token") || "")}` : null;
  return src ? (
    <img src={src} alt="" className="w-11 h-11 rounded-full object-cover gold-hairline" />
  ) : (
    <div className="w-11 h-11 rounded-full bg-gradient-to-br from-rose-500 to-violet-500 flex items-center justify-center text-sm font-semibold">
      {card?.name?.[0]?.toUpperCase() || "U"}
    </div>
  );
}

const bookingTimes = (b) => {
  const start = new Date(`${b.date}T${b.start}:00`);
  const [sh, sm] = b.start.split(":").map(Number), [eh, em] = b.end.split(":").map(Number);
  let mins = eh * 60 + em - (sh * 60 + sm); if (mins <= 0) mins += 1440;
  return { start, end: new Date(start.getTime() + mins * 60000) };
};

function BookingPlace({ b, lang, who }) {
  const loc = b.location || {};
  if (!b.place && !loc.address) return null;
  return (
    <div className="text-xs text-slate-400 mt-1 flex flex-wrap items-center gap-1.5" data-testid={`vs-booking-place-${b.id}`}>
      <MapPin size={12} className="text-rose-300" />
      {b.place && <span className="text-slate-200">{who === "outgoing" && b.place === "own" ? t("place_vip", lang) : placeLabel(b.place, lang)}</span>}
      {loc.address ? <><span>· {[loc.address, loc.postal_code, loc.city, loc.country].filter(Boolean).join(", ")}</span> <MapsLink loc={loc} testid={`vs-booking-maps-${b.id}`} /></>
        : b.address_hidden ? <span className="text-amber-300/80">· {t("addr_hidden", lang)}</span> : null}
    </div>
  );
}

function VipUpsell({ onGo }) {
  return (
    <div className="glass rounded-2xl p-6 border border-amber-500/20" data-testid="vs-vip-upsell">
      <div className="flex items-start gap-3">
        <Crown className="text-amber-300 shrink-0 mt-0.5" size={20} />
        <div>
          <div className="font-semibold text-white">Availability Calendar is a VIP feature</div>
          <p className="text-sm text-slate-400 mt-1">Become a VIP to publish your availability and let members book exact time slots with you.</p>
          <Button onClick={onGo} className="rose-btn text-white border-0 mt-3" data-testid="vs-get-vip">Get VIP</Button>
        </div>
      </div>
    </div>
  );
}

function RescheduleProposal({ b, who, onDone }) {
  const { lang } = useApp();
  const [busy, setBusy] = useState(false);
  const p = b.reschedule_proposal;
  const when = `${new Date(`${p.date}T00:00:00`).toLocaleDateString(lang, { weekday: "short", day: "numeric", month: "short" })} · ${p.start}–${p.end}`;
  const answer = async (a) => {
    setBusy(true);
    try { await api.post(`/vip/schedule/bookings/${b.id}/reschedule/${a}`); toast.success(t(a === "accept" ? "rp_accepted" : "rp_declined", lang)); onDone?.(); }
    catch (e) { toast.error(e.response?.data?.detail || "Error"); }
    finally { setBusy(false); }
  };
  return (
    <div className="mt-3 rounded-xl border border-amber-500/40 bg-amber-500/10 p-3 flex flex-wrap items-center gap-2 text-xs" data-testid={`vs-resched-proposal-${b.id}`}>
      <CalendarClock size={14} className="text-amber-300" />
      <span className="text-amber-100">{t(who === "outgoing" ? "rp_vip_asks" : "rp_waiting", lang)} <b className="font-mono-num">{when}</b></span>
      {who === "outgoing" && (
        <div className="flex gap-2 ms-auto">
          <Button size="sm" disabled={busy} onClick={() => answer("accept")} className="bg-emerald-600 hover:bg-emerald-500 text-white border-0 h-8" data-testid={`vs-resched-accept-${b.id}`}>{busy ? <Loader2 size={14} className="animate-spin" /> : <><Check size={14} className="me-1" />{t("rp_accept", lang)}</>}</Button>
          <Button size="sm" variant="outline" disabled={busy} onClick={() => answer("decline")} className="bg-white/5 border-white/15 text-slate-300 h-8" data-testid={`vs-resched-decline-${b.id}`}>{t("rp_keep", lang)}</Button>
        </div>
      )}
    </div>
  );
}

function BookingCard({ b, who, onConfirm, onDecline, onCancel, onReschedule, onReload, busyId }) {
  const { lang } = useApp();
  const card = who === "incoming" ? b.requester : b.vip_card;
  const loading = busyId === b.id;
  const { start, end } = bookingTimes(b);
  const now = Date.now();
  const live = b.status === "confirmed" && now >= start.getTime() && now < end.getTime();
  const checkInOpen = b.status === "confirmed" && now >= start.getTime() - 2 * 3600000 && now < end.getTime();
  const lateOpen = b.status === "confirmed" && now >= start.getTime() - 3 * 3600000 && now < end.getTime();
  const noShowOpen = b.status === "confirmed" && now >= start.getTime() + 15 * 60000 && now < end.getTime();
  return (
    <div className={`glass rounded-2xl p-4 border-s-2 ${ACCENT[b.status] || "border-s-white/10"} transition-colors hover:bg-white/[0.04]`} data-testid={`vs-booking-${b.id}`}>
    <div className="flex flex-col sm:flex-row sm:items-center gap-4">
      <div className="flex items-center gap-3 flex-1 min-w-0">
        <Avatar card={card} />
        <div className="min-w-0">
          <div className="font-semibold text-white truncate">{card?.name}{card?.age ? `, ${card.age}` : ""}</div>
          <div className="text-xs text-slate-400 flex items-center gap-1.5 mt-0.5">
            <Calendar size={12} /> {fmtDay(b.date)}
          </div>
          <div className="text-xs text-slate-400 flex items-center gap-1.5 mt-0.5 font-mono-num">
            <Clock size={12} /> <span data-testid={`vs-booking-time-${b.id}`}>{t("bk_start", lang)} {b.start} → {t("bk_finish", lang)} {b.end}{end.getDate() !== start.getDate() ? " (+1)" : ""}</span> <span className="text-slate-600">·</span> {b.tz}
            {live && <span className="ms-1 text-[10px] px-1.5 py-0.5 rounded-full bg-emerald-500/20 text-emerald-300" data-testid={`vs-live-${b.id}`}>{t("ext_in_progress", lang)}</span>}
          </div>
          <BookingPlace b={b} lang={lang} who={who} />
          {b.activity ? <div className="text-xs text-slate-300 mt-0.5 truncate">{b.activity}</div> : null}
        </div>
      </div>
      <div className="flex items-center gap-2 shrink-0 flex-wrap justify-end">
        {b.status === "confirmed" && <AddToCalendar id={b.id} title={`GiftsDates VIP: ${b.activity || card?.name || "Date"}`} place={[b.location?.address, b.location?.city].filter(Boolean).join(", ") || b.venue || b.activity} start={start} end={end} link="/vip-bookings" />}
        {b.status === "confirmed" && b.location?.address && <DirectionsButton loc={b.location} testid={`vs-directions-${b.id}`} />}
        <UnverifiedNote show={b.location?.unverified} testid={`vs-unverified-${b.id}`} />
        {who === "outgoing" && checkInOpen && !b.arrived_at && <ArrivedButton b={b} onDone={onReload} />}
        {lateOpen && <RunningLateButton b={b} onDone={onReload} />}
        {who === "outgoing" && noShowOpen && <NoShowReport b={b} onDone={onReload} />}
        {b.late && b.status === "confirmed" && <span className="inline-flex items-center h-9 px-3 rounded-md text-xs bg-amber-500/15 border border-amber-500/40 text-amber-200" data-testid={`vs-late-badge-${b.id}`}>⏱ {t("lt_badge", lang).replace("{m}", b.late.minutes)}</span>}
        {b.client_late && b.status === "confirmed" && <span className="inline-flex items-center h-9 px-3 rounded-md text-xs bg-amber-500/15 border border-amber-500/40 text-amber-200" data-testid={`vs-client-late-badge-${b.id}`}>⏱ {t("lt_badge_client", lang).replace("{m}", b.client_late.minutes)}</span>}
        {b.arrived_at && <span className="inline-flex items-center h-9 px-3 rounded-md text-xs bg-emerald-500/15 border border-emerald-500/40 text-emerald-200" data-testid={`vs-arrived-badge-${b.id}`}>📍 {t("ar_arrived_at", lang).replace("{t}", new Date(b.arrived_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }))}</span>}
        {who === "outgoing" && live && <ExtendDateButton id={b.id} url={`/vip/schedule/bookings/${b.id}/extend`} price={b.extra_hour_price || 250} onDone={onReload} />}
        <div className="text-right me-1">
          <div className="text-amber-300 font-mono-num text-sm">🪙 {b.coins}</div>
          <span className={`inline-block mt-1 text-[10px] px-2 py-0.5 rounded-full border ${STATUS_BADGE[b.status]}`} data-testid={`vs-status-${b.id}`}>{t(`vb_st_${b.status}`, lang)}</span>
        </div>
        {who === "incoming" && ["pending", "confirmed"].includes(b.status) && !b.reschedule_proposal && (
          <Button data-testid={`vs-vip-reschedule-${b.id}`} size="sm" variant="outline" disabled={loading} onClick={() => onReschedule(b)} className="bg-white/5 border-amber-500/40 text-amber-300 hover:bg-amber-500/10 h-9">{t("vb_reschedule", lang)}</Button>
        )}
        {who === "incoming" && b.status === "pending" && (
          <>
            <Button data-testid={`vs-confirm-${b.id}`} size="sm" disabled={loading} onClick={() => onConfirm(b.id)} className="bg-emerald-600 hover:bg-emerald-500 text-white border-0 h-9">
              {loading ? <Loader2 size={14} className="animate-spin" /> : <><Check size={14} className="me-1" /> {t("vb_confirm", lang)}</>}
            </Button>
            <Button data-testid={`vs-decline-${b.id}`} size="sm" variant="outline" disabled={loading} onClick={() => onDecline(b.id)} className="bg-white/5 border-rose-500/40 text-rose-300 hover:bg-rose-500/10 h-9">
              <X size={14} className="me-1" /> {t("vb_decline", lang)}
            </Button>
          </>
        )}
        {who === "incoming" && b.status === "confirmed" && (
          <Button data-testid={`vs-cancel-${b.id}`} size="sm" variant="outline" disabled={loading} onClick={() => onCancel(b, who)} className="bg-white/5 border-white/15 text-slate-300 hover:bg-white/10 h-9">{t("vb_cancel", lang)}</Button>
        )}
        {who === "outgoing" && (b.status === "pending" || b.status === "confirmed") && (
          <>
            {b.status === "pending" && (
              <Button data-testid={`vs-reschedule-${b.id}`} size="sm" variant="outline" disabled={loading} onClick={() => onReschedule(b)} className="bg-white/5 border-amber-500/40 text-amber-300 hover:bg-amber-500/10 h-9">{t("vb_reschedule", lang)}</Button>
            )}
            <Button data-testid={`vs-cancel-${b.id}`} size="sm" variant="outline" disabled={loading} onClick={() => onCancel(b, who)} className="bg-white/5 border-white/15 text-slate-300 hover:bg-white/10 h-9">{t("vb_cancel", lang)}</Button>
          </>
        )}
      </div>
    </div>
    {b.reschedule_proposal && ["pending", "confirmed"].includes(b.status) && <RescheduleProposal b={b} who={who} onDone={onReload} />}
    {b.status === "reported" && <NoShowCase b={b} who={who} onDone={onReload} />}
    <VipPickupBlock b={b} who={who} onDone={onReload} onCancel={onCancel} />
    <VipTaxiBlock b={b} who={who} onDone={onReload} />
    </div>
  );
}

function Empty({ icon: Icon, text }) {
  return (
    <div className="text-center py-12 text-slate-500">
      <Icon size={30} className="mx-auto mb-3 opacity-60" />
      <p className="text-sm">{text}</p>
    </div>
  );
}

export default function VipBookings() {
  const { refreshUser, lang } = useApp();
  const nav = useNavigate();
  const [searchParams] = useSearchParams();
  const [tab, setTab] = useState(searchParams.get("tab"));
  const [sched, setSched] = useState(null);
  const [mine, setMine] = useState([]);
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState(null);
  const [reschedule, setReschedule] = useState(null); // booking being rescheduled
  const [cancelFor, setCancelFor] = useState(null); // { b, who }

  const load = useCallback(async () => {
    try {
      const [a, b] = await Promise.all([
        api.get("/vip/schedule/me"),
        api.get("/vip/schedule/bookings/mine"),
      ]);
      setSched(a.data);
      setMine(b.data.requests || []);
    } catch { /* ignore */ } finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const act = async (fn, id) => {
    setBusyId(id);
    try { await fn(); await load(); await refreshUser(); } finally { setBusyId(null); }
  };
  const confirm = (id) => act(async () => { await api.post(`/vip/schedule/bookings/${id}/confirm`); toast.success(t("vb_confirmed_toast", lang)); }, id);
  const [declineFor, setDeclineFor] = useState(null);
  const decline = (id) => setDeclineFor(id);
  const doDecline = (id, reason) => act(async () => { await api.post(`/vip/schedule/bookings/${id}/decline`, null, { params: { reason } }); toast.success(t("vb_declined_toast", lang)); }, id);
  const cancel = (b, who) => setCancelFor({ b, who });
  const doCancel = (id) => act(async () => { await api.post(`/vip/schedule/bookings/${id}/cancel`); toast.success(t("vb_cancelled_toast", lang)); }, id);

  if (loading) return <div className="min-h-[60vh] flex items-center justify-center text-slate-400"><Loader2 className="animate-spin" /></div>;

  const isVip = sched?.is_vip;
  const pending = sched?.pending || [];
  const confirmed = sched?.confirmed || [];
  const CLOSED = ["declined", "cancelled"];
  const past = (sched?.past || []).filter((b) => !CLOSED.includes(b.status));
  const closedIn = (sched?.past || []).filter((b) => CLOSED.includes(b.status));
  const mineActive = mine.filter((m) => ["pending", "confirmed", "reported", "completed"].includes(m.status));
  const closedOut = mine.filter((m) => CLOSED.includes(m.status));
  const closedCount = closedIn.length + closedOut.length;
  const closedList = (
    <div className="space-y-3" data-testid="vs-cancelled-list">
      {closedCount === 0 ? <Empty icon={Ban} text={t("vb_none_cancelled", lang)} /> : (
        <>
          {closedIn.map((b) => <BookingCard key={b.id} b={b} who="incoming" busyId={busyId} />)}
          {closedOut.map((b) => <BookingCard key={b.id} b={b} who="outgoing" busyId={busyId} />)}
        </>
      )}
    </div>
  );

  const cards = (list, who) => list.map((b) => (
    <BookingCard key={b.id} b={b} who={who} onConfirm={confirm} onDecline={decline} onCancel={cancel} onReschedule={setReschedule} onReload={load} busyId={busyId} />
  ));
  const tabs = [
    ...(isVip ? [{ v: "requests", label: t("vb_requests", lang), icon: Inbox, n: pending.length, hot: true, body: pending.length ? cards(pending, "incoming") : <Empty icon={Inbox} text={t("vb_none_pending", lang)} /> }] : []),
    { v: "mine", label: t("vb_mine", lang), icon: Send, n: mineActive.length, body: mineActive.length ? cards(mineActive, "outgoing") : <Empty icon={Send} text={t("vb_none_mine", lang)} /> },
    ...(isVip ? [{ v: "confirmed", label: t("vb_confirmed", lang), icon: CalendarClock, n: confirmed.length, body: confirmed.length ? cards(confirmed, "incoming") : <Empty icon={CalendarClock} text={t("vb_none_confirmed", lang)} /> }] : []),
    { v: "cancelled", label: t("vb_cancel_refused", lang), icon: Ban, n: closedCount, body: closedList },
    ...(isVip ? [{ v: "past", label: t("vb_past", lang), icon: Calendar, n: past.length, body: past.length ? cards(past, "incoming") : <Empty icon={Calendar} text={t("vb_none_past", lang)} /> }] : []),
    { v: "availability", label: t("vb_availability", lang), icon: CalendarDays, body: isVip ? <VipAvailabilityEditor blocks={sched?.blocks || []} onChanged={load} /> : <VipUpsell onGo={() => nav("/wallet?premium=1")} /> },
  ];
  const earn = sched?.earnings || { earned: 0, held: 0 };
  const todayItems = [...pending.map((b) => ({ b, who: "incoming" })), ...confirmed.map((b) => ({ b, who: "incoming" })), ...past.map((b) => ({ b, who: "incoming" })), ...mineActive.map((b) => ({ b, who: "outgoing" }))];
  const stats = isVip
    ? [[t("vb_requests", lang), pending.length, "text-rose-300"], [t("vb_confirmed", lang), confirmed.length, "text-emerald-300"], [t("vb_mine", lang), mineActive.length, "text-sky-300"], [t("vb_past", lang), past.length, "text-slate-300"]]
    : [[t("vb_mine", lang), mineActive.length, "text-sky-300"], [t("vb_cancel_refused", lang), closedCount, "text-slate-300"]];

  return (
    <div className="max-w-5xl mx-auto px-4 py-8">
      <header className="space-y-5 mb-6">
        <div>
          <div className="text-[11px] uppercase tracking-[0.25em] text-amber-300/80 mb-1.5">GiftsDates · VIP</div>
          <h1 className="font-serif-luxe text-4xl gold-text flex items-center gap-2.5"><Crown size={28} className="text-amber-300" /> {t("vb_title", lang)}</h1>
          <p className="text-sm text-slate-400 mt-1.5">{t("vb_intro", lang)}</p>
        </div>
        <div className={`grid gap-2 ${isVip ? "grid-cols-2 sm:grid-cols-6" : "grid-cols-2 sm:grid-cols-4"}`}>
        {isVip && (
          <div className="col-span-2 rounded-xl border border-amber-500/30 bg-gradient-to-br from-amber-500/10 to-transparent px-4 py-2.5" data-testid="vs-earnings-tile">
            <div className="text-[10px] uppercase tracking-wider text-amber-300/80">{t("er_month", lang)}</div>
            <div className="font-mono-num text-2xl leading-tight text-amber-200 mt-0.5" data-testid="vs-earnings-month">🪙 {earn.earned.toLocaleString()}</div>
            <div className="text-[11px] text-slate-400 mt-1" data-testid="vs-earnings-held">🔒 {earn.held.toLocaleString()} · {t("er_held", lang)}</div>
            {earn.by_month?.length > 0 && <EarningsChart data={earn.by_month} />}
          </div>
        )}
        <div className="contents" data-testid="vs-stats">
          {stats.map(([label, n, c]) => (
            <div key={label} className="rounded-xl border border-white/10 bg-white/[0.03] px-4 py-3 flex flex-col justify-center gap-2">
              <div className={`font-mono-num text-4xl leading-none ${c}`}>{n}</div>
              <div className="text-[10px] uppercase tracking-wider text-slate-500 mt-1.5 truncate">{label}</div>
            </div>
          ))}
        </div>
        </div>
      </header>

      <TodayStrip items={todayItems} />

      <Tabs value={tabs.some((x) => x.v === tab) ? tab : tabs[0].v} onValueChange={setTab} className="w-full">
        <div className="sticky top-16 z-20 -mx-4 px-4 py-2 bg-[#0D0B12]/85 backdrop-blur-xl border-b border-white/10">
          <TabsList className="bg-transparent p-0 h-auto w-full justify-start gap-1 overflow-x-auto flex-nowrap" data-testid="vs-tabs">
            {tabs.map(({ v, label, icon: Icon, n, hot }) => (
              <TabsTrigger key={v} value={v} data-testid={`vs-tab-${v}`}
                className="shrink-0 rounded-full px-4 py-2 text-sm text-slate-400 border border-transparent hover:text-white transition-colors data-[state=active]:bg-white/[0.07] data-[state=active]:border-amber-400/40 data-[state=active]:text-amber-100 data-[state=active]:shadow-none">
                <Icon size={14} className="me-1.5" />{label}
                {n > 0 && <span className={`ms-1.5 text-[10px] rounded-full px-1.5 py-0.5 font-mono-num ${hot ? "bg-rose-500 text-white" : "bg-white/10 text-slate-200"}`}>{n}</span>}
              </TabsTrigger>
            ))}
          </TabsList>
        </div>
        {tabs.map(({ v, body }) => (
          <TabsContent key={v} value={v} className="mt-6 space-y-3" data-testid={`vs-panel-${v}`}>{body}</TabsContent>
        ))}
      </Tabs>


      <DeclineReasonDialog open={!!declineFor} onClose={() => setDeclineFor(null)} onConfirm={(r) => doDecline(declineFor, r)} testid="vs-decline-dialog" />
      <CancelPreviewDialog open={!!cancelFor} onOpenChange={(o) => !o && setCancelFor(null)} total={cancelFor?.b.coins || 0} taxi={cancelFor?.b.taxi_coins || 0}
        byRequester={cancelFor?.who === "outgoing"} onConfirm={() => { const id = cancelFor.b.id; setCancelFor(null); doCancel(id); }} />
      {reschedule && (
        <VipDateBookModal
          open={!!reschedule}
          rescheduleHours={reschedule.hours}
          onOpenChange={(o) => { if (!o) setReschedule(null); }}
          target={{ id: reschedule.vip_id, name: reschedule.vip_card?.name || "VIP" }}
          rescheduleId={reschedule.id}
          onDone={() => { setReschedule(null); load(); }}
        />
      )}

      <div className="mt-8">
        <CancelledDates />
      </div>
    </div>
  );
}
