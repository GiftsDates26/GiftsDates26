import React, { useEffect, useState, useCallback } from "react";
import DateCommitmentNote from "./DateCommitmentNote";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "./ui/sheet";
import { Button } from "./ui/button";
import { Label } from "./ui/label";
import { Calendar, Clock, Loader2, Hourglass, MapPin } from "lucide-react";
import VerifiedAddressForm, { addrHintKey, addressReady, addrPayload, addrErrKey } from "./VerifiedAddressForm";
import { placeLabel } from "../lib/vipCatalog";
import { toast } from "sonner";
import { api } from "../lib/api";
import { useApp } from "../context/AppContext";
import TimeChooser from "./TimeChooser";
import ExtraHoursStepper from "./ExtraHoursStepper";
import { minHm } from "../lib/availability";
import { EXTRA_HOUR_MIN } from "../lib/vipCatalog";
import { t } from "../lib/i18n";

const LENGTHS = [1, 2, 3];

function Step({ n, icon: Icon, title, children, testid }) {
  return (
    <section className="relative ps-10" data-testid={testid}>
      <span className="absolute start-0 top-0 h-7 w-7 rounded-full bg-rose-500/15 border border-rose-500/40 text-rose-200 text-xs font-semibold flex items-center justify-center">{n}</span>
      <span className="absolute start-[13px] top-8 bottom-[-18px] w-px bg-white/10" aria-hidden />
      <h3 className="text-sm font-semibold text-white flex items-center gap-1.5 mb-2.5 min-h-7">{Icon && <Icon size={14} className="text-amber-300" />}{title}</h3>
      {children}
    </section>
  );
}
const fmtDay = (d) => { try { const [y, m, dd] = d.split("-").map(Number); return new Date(y, m - 1, dd).toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" }); } catch { return d; } };
const ERR = { SLOT_TAKEN: "bk_slot_taken", TIME_UNAVAILABLE: "bk_time_unavail", TIME_PASSED: "bk_time_passed", DURATION_CHANGED: "bk_same_len", "Insufficient coins": "not_enough_coins" };

function PriceSummary({ lang, length, extra, rate, extraPrice, total }) {
  return (
    <div className="rounded-xl border border-amber-500/25 bg-amber-500/5 p-3 text-xs space-y-1" data-testid="vs-book-price">
      <div className="flex justify-between"><span className="text-slate-400">{t("bk_rate_for", lang).replace("{h}", length)}</span><span className="font-mono-num text-white">🪙 {rate}</span></div>
      {extra > 0 && <div className="flex justify-between"><span className="text-slate-400">{t("bk_extra_hours", lang)} · {extra} × {extraPrice}</span><span className="font-mono-num text-white">🪙 {extra * extraPrice}</span></div>}
      <div className="flex justify-between border-t border-white/10 pt-1"><span className="text-amber-200 font-semibold">{t("bk_total", lang)}</span><b className="font-mono-num text-amber-300" data-testid="vs-book-total">🪙 {total}</b></div>
    </div>
  );
}

export default function VipDateBookModal({ open, onOpenChange, target, rescheduleId, rescheduleHours, onDone }) {
  const { user, refreshUser, lang } = useApp();
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState({ days: [], tz: "UTC", buffer: 15 });
  const [day, setDay] = useState(null);
  const [startMin, setStartMin] = useState(null);
  const [length, setLength] = useState(1);
  const [extra, setExtra] = useState(0);
  const [place, setPlace] = useState(null);
  const [agree, setAgree] = useState(false);
  const [loc, setLoc] = useState({});
  const [busy, setBusy] = useState(false);
  const isReschedule = !!rescheduleId;
  const dur = 60 * (length + extra);

  const load = useCallback(() => {
    if (!target?.id) return;
    setLoading(true);
    api.get(`/vip/schedule/${target.id}/slots`)
      .then((r) => { setData(r.data); setDay((r.data.days || [])[0]?.date || null); })
      .catch(() => setData({ days: [], tz: "UTC", buffer: 15 }))
      .finally(() => setLoading(false));
  }, [target]);

  useEffect(() => {
    if (!open) return;
    const h = rescheduleHours || 1;
    setStartMin(null); setLength(Math.min(3, h)); setExtra(Math.max(0, h - 3)); setPlace(null); setLoc({}); setAgree(false); load();
  }, [open, load, rescheduleHours]);

  const dayObj = (data.days || []).find((d) => d.date === day);
  const slot = startMin == null ? null : { start: minHm(startMin), end: minHm(startMin + dur) };
  const extraPrice = data.extra_hour_price || EXTRA_HOUR_MIN;
  const rate = data.rates?.[String(length)] || EXTRA_HOUR_MIN;
  const total = rate + extra * extraPrice;

  const submit = async () => {
    if (!slot) { toast.error(t("bk_pick_slot_err", lang)); return; }
    if (!isReschedule && !agree) { toast.error(t("commit_required", lang)); return; }
    const places = data.places || [];
    if (!isReschedule && places.length && !place) { toast.error(t("vip_select_place_first", lang)); return; }
    if (!isReschedule && place && place !== "own" && !addressReady(loc, false)) { toast.error(t(addrHintKey(loc, false), lang)); return; }
    if (!isReschedule && ((user?.coins || 0) + (user?.withdrawable || 0)) < total) { toast.error(t("not_enough_coins", lang)); return; }
    setBusy(true);
    try {
      if (isReschedule) {
        await api.post(`/vip/schedule/bookings/${rescheduleId}/reschedule`, { date: day, start: slot.start, end: slot.end });
        toast.success(t("bk_resched_sent", lang));
      } else {
        await api.post(`/vip/schedule/${target.id}/book`, { date: day, start: slot.start, end: slot.end, length, venue: place ? placeLabel(place, lang) : "", tz: dayObj?.tz,
          place, ...(place && place !== "own" ? addrPayload(loc) : {}) });
        toast.success(t("bk_sent", lang));
      }
      await refreshUser(); onDone?.(); onOpenChange(false);
    } catch (e) {
      const d = e.response?.data?.detail || "";
      toast.error(ERR[d] ? t(ERR[d], lang) : addrErrKey(d) ? t(addrErrKey(d), lang) : d || "Error");
      if (d === "SLOT_TAKEN") load();
    } finally { setBusy(false); }
  };

  const rowCls = (on) => `w-full flex items-center justify-between gap-3 px-3.5 py-2.5 rounded-xl border text-sm transition-colors ${on ? "bg-rose-500/15 border-rose-500/60 text-white" : "bg-white/[0.03] border-white/10 text-slate-200 hover:bg-white/[0.07]"}`;
  const winText = (d) => (d.windows || []).map((w) => `${w.from}–${w.to}`).join(" · ");
  let n = 0;

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="z-[70] bg-[#14111c] border-white/10 text-white w-full sm:max-w-md p-0 flex flex-col h-full" data-testid="vs-book-dialog">
        <SheetHeader className="px-6 pt-6 pb-4 border-b border-white/10 text-start">
          <SheetTitle className="font-serif-luxe text-2xl text-white flex items-center gap-2">
            <Calendar size={20} className="text-amber-300" /> {t(isReschedule ? "bk_reschedule_title" : "bk_title", lang)}
          </SheetTitle>
          <div className="text-xs text-slate-400">{target?.name}{target?.city ? ` · ${target.city}` : ""} · {t("bk_vip_local", lang).replace("{tz}", dayObj?.tz || data.tz)}</div>
        </SheetHeader>
        {loading ? (
          <div className="flex-1 flex items-center justify-center text-slate-400"><Loader2 className="animate-spin" /></div>
        ) : (data.days || []).length === 0 ? (
          <div className="flex-1 flex items-center justify-center px-6 text-center text-slate-400 text-sm" data-testid="vs-book-no-availability">{t("bk_no_avail", lang)}</div>
        ) : (
          <>
            <div className="flex-1 overflow-y-auto px-6 py-5 space-y-6">
              <Step n={++n} icon={Calendar} title={t("bk_choose_day", lang)} testid="vs-book-step-day">
                <div className="space-y-1.5 max-h-56 overflow-y-auto pe-1" data-testid="vs-book-days">
                  {data.days.map((d) => (
                    <button key={d.date} type="button" onClick={() => { setDay(d.date); setStartMin(null); }} data-testid={`vs-book-day-${d.date}`} className={rowCls(day === d.date)}>
                      <span className="flex flex-col items-start text-start min-w-0">
                        <span className="font-medium">{fmtDay(d.date)}</span>
                        <span className="text-[11px] font-mono-num text-emerald-300/90 truncate max-w-full">{winText(d)}</span>
                      </span>
                      {day === d.date && <span className="h-2 w-2 rounded-full bg-rose-400 shrink-0" />}
                    </button>
                  ))}
                </div>
              </Step>
              {!isReschedule && (
                <Step n={++n} icon={Hourglass} title={t("bk_how_long", lang)} testid="vs-book-step-length">
                  <div className="space-y-1.5" data-testid="vs-book-durations">
                    {LENGTHS.map((h) => (
                      <button key={h} type="button" onClick={() => { setLength(h); setStartMin(null); }} data-testid={`vs-book-dur-${h}h`} className={rowCls(length === h)}>
                        <span className="font-mono-num">{h}h</span>
                        <span className="font-mono-num text-amber-300">🪙 {data.rates?.[String(h)] || EXTRA_HOUR_MIN}</span>
                      </button>
                    ))}
                  </div>
                  <div className="mt-2.5">
                    <ExtraHoursStepper label={t("bk_extra_hours", lang)} each={t("bk_each", lang)} value={extra} onChange={(x) => { setExtra(x); setStartMin(null); }} price={extraPrice} testid="vs-book-extra-hours" />
                  </div>
                </Step>
              )}
              <Step n={++n} icon={Clock} title={t("bk_pick_start", lang)} testid="vs-book-step-time">
                <TimeChooser key={`${day}-${dur}`} vertical day={day} wins={dayObj?.windows || []} taken={dayObj?.taken || []} slot={dur}
                  value={startMin} onChange={setStartMin} testid="vs-book-time" note={null} />
              </Step>
              {!isReschedule && (data.places || []).length > 0 && (
                <Step n={++n} icon={MapPin} title={t("bk_where", lang)} testid="vs-book-step-place">
                  <div className="space-y-1.5" data-testid="vs-book-places">
                    {data.places.map((pv) => (
                      <button key={pv} type="button" onClick={() => setPlace(pv)} data-testid={`vs-book-place-${pv}`} className={rowCls(place === pv)}>
                        <span>{pv === "own" ? t("place_vip", lang) : placeLabel(pv, lang)}</span>{place === pv && <span className="h-2 w-2 rounded-full bg-rose-400 shrink-0" />}
                      </button>
                    ))}
                  </div>
                  {place === "own" && <p className="mt-2 text-[11px] text-sky-300 flex items-start gap-1" data-testid="vs-book-own-note"><MapPin size={11} className="mt-0.5 shrink-0" /> {t("own_addr_auto", lang)}</p>}
                  {place && place !== "own" && <div className="mt-2.5" data-testid="vs-book-address"><VerifiedAddressForm value={loc} onChange={setLoc} needVenue={false} testid="vs-book-addr" /></div>}
                </Step>
              )}
              <div className="text-xs text-slate-400 glass rounded-lg p-3">{t(isReschedule ? "bk_resched_note" : "bk_escrow_note", lang)}</div>
              {!isReschedule && <DateCommitmentNote testid="vs-book-commitment" />}
            </div>
            <div className="border-t border-white/10 px-6 py-4 space-y-3 bg-[#14111c]" data-testid="vs-book-footer">
              {!isReschedule && <PriceSummary lang={lang} length={length} extra={extra} rate={rate} extraPrice={extraPrice} total={total} />}
              {slot && <div className="text-xs text-slate-300 font-mono-num text-center" data-testid="vs-book-chosen">{fmtDay(day)} · {t("bk_start", lang)} {slot.start} → {t("bk_finish", lang)} {slot.end}</div>}
              {!isReschedule && (
                <label className={`flex items-start gap-2 cursor-pointer rounded-lg border px-2.5 py-2 text-xs transition-colors ${agree ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-100" : "border-amber-500/40 bg-amber-500/5 text-slate-200"}`}>
                  <input type="checkbox" data-testid="vs-book-commitment-checkbox" checked={agree} onChange={(e) => setAgree(e.target.checked)} className="mt-0.5 h-4 w-4 accent-rose-500 shrink-0" />
                  <span>{t("commit_agree", lang)}</span>
                </label>
              )}
              <Button data-testid="vs-book-submit" disabled={busy || !slot || (!isReschedule && !agree)} onClick={submit} className="rose-btn text-white border-0 w-full h-11">
                {busy ? <Loader2 size={16} className="animate-spin" /> : isReschedule ? t("bk_propose", lang) : <>{t("bk_request", lang)} · 🪙 {total}</>}
              </Button>
            </div>
          </>
        )}
      </SheetContent>
    </Sheet>
  );
}
