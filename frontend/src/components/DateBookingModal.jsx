import React, { useEffect, useState } from "react";
import DateCommitmentNote from "./DateCommitmentNote";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "./ui/dialog";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { Label } from "./ui/label";
import { Calendar } from "./ui/calendar";
import { toast } from "sonner";
import { api } from "../lib/api";
import { useApp } from "../context/AppContext";
import { t } from "../lib/i18n";
import { toKey, fromKey, minHm, dayWins, openDayKeys, bestDayKeys } from "../lib/availability";
import TimeChooser from "./TimeChooser";
import AvailabilityOverview from "./AvailabilityOverview";
import AddressPicker from "./AddressPicker";

export default function DateBookingModal({ open, onOpenChange, target }) {
  const { user, meta, lang, refreshUser } = useApp();
  const [venue, setVenue] = useState("");
  const [city, setCity] = useState(target?.city || "");
  const [loc, setLoc] = useState({ address: "", postal_code: "", country: target?.country || "", lat: null, lng: null });
  const [day, setDay] = useState(null);
  const [start, setStart] = useState(null);
  const [coins, setCoins] = useState(target?.date_price || meta?.date_min_coins || 300);
  const [activities, setActivities] = useState(["", "", ""]);
  const [avail, setAvail] = useState({ available_days: [], busy_days: [] });
  const [busy, setBusy] = useState(false);
  const [agree, setAgree] = useState(false);

  useEffect(() => {
    setCity(target?.city || ""); setLoc({ address: "", postal_code: "", country: target?.country || "", lat: null, lng: null }); setCoins(target?.date_price || meta?.date_min_coins || 300); setDay(null); setActivities(["", "", ""]);
    if (open && target?.id) api.get(`/profiles/${target.id}/availability`).then(r => setAvail(r.data)).catch(() => {});
  }, [target, meta, open]);

  const busySet = new Set(avail.busy_days);
  const wins = dayWins(avail, day);
  const taken = (avail.busy_slots || {})[day] || [];
  const timeOk = day && start != null;
  const isDisabled = (d) => {
    const k = toKey(d);
    if (d < new Date(new Date().setHours(0, 0, 0, 0))) return true;
    if (busySet.has(k)) return true;
    return !openDayKeys(avail).includes(k) && avail.restricted !== false;
  };

  const submit = async () => {
    if (!venue || !timeOk) { toast.error(t("fill_all", lang)); return; }
    const acts = activities.map(a => a.trim());
    if (acts.some(a => !a)) { toast.error(t("activities_required_err", lang)); return; }
    if (user.coins < coins) { toast.error(t("not_enough_coins", lang)); return; }
    setBusy(true);
    try {
      const dt = fromKey(day); dt.setHours(0, start, 0, 0);
      await api.post("/dates/book", { target_id: target.id, venue, city, scheduled_at: dt.toISOString(), coins, local_time: minHm(start), local_day: day, address: loc.address, postal_code: loc.postal_code, country: loc.country, lat: loc.lat, lng: loc.lng, activities: acts });
      await refreshUser();
      toast.success(t("date_booked", lang));
      onOpenChange(false);
    } catch (e) {
      const d = e.response?.data?.detail || "";
      toast.error(
        d === "DAY_UNAVAILABLE" ? t("day_unavailable_err", lang)
        : d === "ACTIVITIES_REQUIRED" ? t("activities_required_err", lang)
        : d === "DAY_BUSY" ? t("day_busy_err", lang)
        : d === "TIME_PASSED" ? t("err_time_passed", lang)
        : d.startsWith("SLOT_LOCKED:") ? t("iv_slot_locked_err", lang)
        : d.startsWith("SLOT_BUSY:") ? t("slot_busy_err", lang).replace("{w}", d.split(":").slice(1).join(":"))
        : d.startsWith("TIME_UNAVAILABLE:") ? t("time_unavailable_err", lang).replace("{w}", d.split(":").slice(1).join(":"))
        : d || t("failed", lang));
    } finally { setBusy(false); }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="bg-[#161320] border-white/10 text-white max-w-3xl max-h-[90vh] overflow-y-auto">
        <DialogHeader><DialogTitle className="font-serif-luxe text-2xl">{t("book_date", lang)} · {target?.name}</DialogTitle></DialogHeader>
        <div className="rounded-xl border border-emerald-500/20 bg-emerald-500/[0.03] p-3" data-testid="date-availability">
          <div className="text-sm text-slate-200 mb-2 font-semibold">{t("ao_title", lang).replace("{name}", target?.name || "")}</div>
          <AvailabilityOverview avail={avail} selected={day} onPick={setDay} max={8} testid="date-avail" />
        </div>
        <div className="grid sm:grid-cols-[auto_1fr] gap-5">
          <div>
            <Label className="text-xs text-slate-400">{t("pick_day", lang)}</Label>
            <div className="mt-1 rounded-xl border border-white/10 bg-white/5" data-testid="date-calendar">
              <Calendar key={day ? day.slice(0, 7) : "now"} defaultMonth={day ? fromKey(day) : undefined} mode="single" selected={day ? fromKey(day) : undefined} onSelect={(d) => d && setDay(toKey(d))} disabled={isDisabled}
                modifiers={{ available: openDayKeys(avail).map(fromKey), best: bestDayKeys(avail).map(fromKey) }}
                modifiersClassNames={{ available: "ring-1 ring-emerald-400/50 rounded-md", best: "!ring-2 !ring-amber-300 rounded-md font-semibold" }}
                classNames={{ day_selected: "bg-rose-500 text-white hover:bg-rose-500 focus:bg-rose-500" }} />
            </div>
            <div className="flex gap-3 mt-2 text-[11px] text-slate-400">
              <span><span className="inline-block w-2.5 h-2.5 rounded-sm ring-1 ring-emerald-400/60 me-1" />{t("availability", lang)}</span>
            </div>
            <div className="mt-4">
              <Label className="text-xs text-slate-400">{t("pick_start_time", lang)}{day ? ` · ${day}` : ""}</Label>
              <p className="text-[11px] text-amber-300/80 mt-0.5" data-testid="date-buffer-note">🔒 {t("buffer_note", lang)}</p>
              {!day ? <div className="mt-2 text-xs text-slate-500">{t("pick_day", lang)}…</div>
                : <TimeChooser key={day} day={day} wins={wins} taken={taken} value={start} onChange={setStart} testid="date-time" />}
            </div>
          </div>
          <div className="space-y-3">
            <div><Label className="text-xs text-slate-400">{t("venue", lang)}</Label>
              <Input data-testid="date-venue-input" value={venue} onChange={e => setVenue(e.target.value)} placeholder="Le Bernardin" className="bg-white/5 border-white/10 mt-1" /></div>
            <div><Label className="text-xs text-slate-400">{t("address", lang)}</Label>
              <div className="mt-1"><AddressPicker testid="date-address" manualFields={false} value={loc} onChange={(l) => { setLoc({ ...loc, ...l }); if (l.city) setCity(l.city); if (!venue && l.venue) setVenue(l.venue); }} /></div></div>
            <div className="grid grid-cols-3 gap-2">
              <div><Label className="text-xs text-slate-400">{t("city", lang)}</Label>
                <Input data-testid="date-city-input" value={city} onChange={e => setCity(e.target.value)} className="bg-white/5 border-white/10 mt-1" /></div>
              <div><Label className="text-xs text-slate-400">{t("postal_code", lang)}</Label>
                <Input data-testid="date-postal-input" value={loc.postal_code} onChange={e => setLoc({ ...loc, postal_code: e.target.value })} className="bg-white/5 border-white/10 mt-1" /></div>
              <div><Label className="text-xs text-slate-400">{t("country", lang)}</Label>
                <Input data-testid="date-country-input" value={loc.country} onChange={e => setLoc({ ...loc, country: e.target.value })} className="bg-white/5 border-white/10 mt-1" /></div>
            </div>
            <div>
              <Label className="text-xs text-slate-400">{t("when", lang)}</Label>
              <div data-testid="date-selected-day" className="mt-1 h-10 flex items-center px-3 rounded-md bg-white/5 border border-white/10 text-sm font-mono-num">{day || "—"}</div>
            </div>
            <div data-testid="date-activities">
              <Label className="text-xs text-slate-400">{t("date_ideas_label", lang)}</Label>
              <p className="text-[11px] text-slate-500 mt-0.5">{t("date_ideas_hint", lang)}</p>
              <div className="space-y-2 mt-1.5">
                {[0, 1, 2].map(i => (
                  <Input key={i} data-testid={`date-activity-${i}`} value={activities[i]}
                    onChange={e => setActivities(a => a.map((v, idx) => idx === i ? e.target.value : v))}
                    placeholder={t(`date_idea_ph_${i}`, lang)} maxLength={120}
                    className="bg-white/5 border-white/10" />
                ))}
              </div>
            </div>
            <div><Label className="text-xs text-slate-400">{t("coins", lang)} (min {meta?.date_min_coins})</Label>
              <p className="text-[11px] text-slate-500 mt-0.5" data-testid="date-price-note">{t("date_price_note", lang)}</p>
              <Input data-testid="date-coins-input" type="number" min={meta?.date_min_coins || 300} step="50" value={coins} onChange={e => setCoins(parseInt(e.target.value || 0))} className="bg-white/5 border-white/10 mt-1" /></div>
            <div className="text-xs text-slate-400 glass rounded-lg p-3">🔒 {t("commission_note", lang)}</div>
            <DateCommitmentNote testid="date-booking-commitment" checked={agree} onCheckedChange={setAgree} />
            <Button data-testid="date-booking-submit-button" disabled={busy || !agree || !day || !timeOk || activities.some(a => !a.trim())} onClick={submit} className="rose-btn text-white border-0 w-full h-11">
              {t("book_date", lang)} · 🪙 {coins}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
