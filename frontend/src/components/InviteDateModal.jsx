import React, { useEffect, useState } from "react";
import DateCommitmentNote from "./DateCommitmentNote";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "./ui/dialog";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { Calendar } from "./ui/calendar";
import { toast } from "sonner";
import { ShieldAlert, Sparkles, Clock } from "lucide-react";
import { api } from "../lib/api";
import { useApp } from "../context/AppContext";
import { t } from "../lib/i18n";
import { toKey, fromKey, minHm, dayWins, openDayKeys, bestDayKeys } from "../lib/availability";
import TimeChooser from "./TimeChooser";
import AvailabilityOverview from "./AvailabilityOverview";

export default function InviteDateModal({ open, onOpenChange, target, initialDay = null }) {
  const { user, lang, refreshUser } = useApp();
  const tr = (k, vars) => { let s = t(k, lang); if (vars) Object.entries(vars).forEach(([n, v]) => (s = s.replace(`{${n}}`, v))); return s; };
  const floor = Math.max(150, target?.date_price || 0);
  const [activities, setActivities] = useState(["", "", ""]);
  const [coins, setCoins] = useState(floor);
  const [ack, setAck] = useState(false);
  const [agree, setAgree] = useState(false);
  const [busy, setBusy] = useState(false);
  const [avail, setAvail] = useState({ available_days: [], busy_days: [] });
  const [day, setDay] = useState(null);
  const [start, setStart] = useState(null);

  useEffect(() => {
    if (open) {
      setActivities(["", "", ""]); setCoins(floor); setAck(false); setAgree(false); setDay(initialDay); setStart(null);
      if (target?.id) api.get(`/profiles/${target.id}/availability`).then(r => setAvail(r.data)).catch(() => {});
    }
  }, [open]); // eslint-disable-line

  const setAct = (i, v) => setActivities(a => a.map((x, idx) => idx === i ? v : x));
  const busySet = new Set(avail.busy_days || []);
  const wins = dayWins(avail, day);
  const taken = (avail.busy_slots || {})[day] || [];
  const isDisabled = (d) => {
    const k = toKey(d);
    if (d < new Date(new Date().setHours(0, 0, 0, 0))) return true;
    if (busySet.has(k)) return true;
    return !openDayKeys(avail).includes(k) && avail.restricted !== false;
  };
  const timeOk = day && start != null;

  const send = async () => {
    const acts = activities.map(a => a.trim());
    if (acts.some(a => !a)) { toast.error(tr("activities_required_err")); return; }
    if (!day || !timeOk) { toast.error(tr("iv_pick_slot_err")); return; }
    if (!ack) { toast.error(tr("iv_accept_safety")); return; }
    if (coins < floor) { toast.error(tr("iv_min_is", { n: floor })); return; }
    if (((user?.coins || 0) + (user?.withdrawable || 0)) < coins) { toast.error(tr("not_enough_coins")); return; }
    setBusy(true);
    try {
      const dt = fromKey(day); dt.setHours(0, start, 0, 0);
      await api.post("/invites", {
        recipient_id: target.id,
        activity_option_1: acts[0], activity_option_2: acts[1], activity_option_3: acts[2],
        scheduled_start: dt.toISOString(), local_day: day, local_time: minHm(start), coins, safety_ack: true,
      });
      await refreshUser();
      toast.success(tr("iv_sent_success"));
      onOpenChange(false);
    } catch (e) {
      const d = e.response?.data?.detail || "";
      toast.error(d === "ACTIVITIES_REQUIRED" ? tr("activities_required_err")
        : d === "DAY_UNAVAILABLE" ? tr("day_unavailable_err")
        : d === "TIME_PASSED" ? tr("err_time_passed")
        : d.startsWith("SLOT_LOCKED") ? tr("iv_slot_locked_err")
        : d.startsWith("SLOT_BUSY") ? tr("iv_slot_taken_err")
        : d === "TIME_CONFLICT" ? tr("iv_slot_taken_err")
        : d.startsWith("TIME_UNAVAILABLE:") ? tr("time_unavailable_err").replace("{w}", d.split(":").slice(1).join(":"))
        : d.startsWith("MIN_COINS:") ? tr("iv_min_is", { n: d.split(":")[1] })
        : d || tr("failed"));
    } finally { setBusy(false); }
  };

  const allFilled = activities.every(a => a.trim());

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="bg-[#161320] border-white/10 text-white max-w-2xl max-h-[90vh] overflow-y-auto" data-testid="invite-date-modal">
        <DialogHeader>
          <DialogTitle className="font-serif-luxe text-2xl">{tr("iv_title", { name: target?.name })}</DialogTitle>
          <DialogDescription className="text-slate-400 text-sm">{tr("date_ideas_hint")}</DialogDescription>
        </DialogHeader>

        <div className="flex items-start gap-2 rounded-xl border border-amber-500/30 bg-amber-500/5 p-3 text-xs text-amber-200/90" data-testid="invite-safety-notice">
          <ShieldAlert size={16} className="mt-0.5 shrink-0 text-amber-300" />
          <span>{tr("iv_safety")}</span>
        </div>

        <div className="rounded-xl border border-emerald-500/20 bg-emerald-500/[0.03] p-3" data-testid="invite-availability">
          <div className="text-sm text-slate-200 mb-2 font-semibold">{t("ao_title", lang).replace("{name}", target?.name || "")}</div>
          <AvailabilityOverview avail={avail} selected={day} onPick={setDay} max={8} testid="invite-avail" />
        </div>
        <div>
          <label className="block text-xs text-slate-400">{tr("pick_day")}</label>
          <div className="mt-1 rounded-xl border border-white/10 bg-white/5 inline-block" data-testid="invite-calendar">
            <Calendar key={day ? day.slice(0, 7) : "now"} defaultMonth={day ? fromKey(day) : undefined} mode="single" selected={day ? fromKey(day) : undefined} onSelect={(d) => d && setDay(toKey(d))} disabled={isDisabled}
              modifiers={{ available: openDayKeys(avail).map(fromKey), best: bestDayKeys(avail).map(fromKey) }}
              modifiersClassNames={{ available: "ring-1 ring-emerald-400/50 rounded-md", best: "!ring-2 !ring-amber-300 rounded-md font-semibold" }}
              classNames={{ day_selected: "bg-rose-500 text-white hover:bg-rose-500 focus:bg-rose-500" }} />
          </div>
        </div>
        <div>
          <label className="text-xs text-slate-400 flex items-center gap-1"><Clock size={12} /> {tr("pick_start_time")}{day ? ` · ${day}` : ""}</label>
          {!day ? <div className="mt-2 text-xs text-slate-500">{tr("pick_day")}…</div>
            : <TimeChooser key={day} day={day} wins={wins} taken={taken} value={start} onChange={setStart} testid="invite-time" />}
        </div>

        <div className="space-y-3" data-testid="invite-activities">
          <div className="flex items-center gap-2 text-sm text-slate-200">
            <Sparkles size={15} className="text-rose-300" />
            <span className="font-semibold">{tr("date_ideas_label")}</span>
          </div>
          {[0, 1, 2].map(i => (
            <div key={i}>
              <label className="text-xs text-slate-400">{tr("date_idea_slot", { n: i + 1 })}</label>
              <Input data-testid={`invite-activity-${i}`} value={activities[i]} onChange={e => setAct(i, e.target.value)} placeholder={tr(`date_idea_ph_${i}`)} maxLength={120} className="bg-white/5 border-white/10 mt-1" />
            </div>
          ))}
        </div>

        <div className="grid sm:grid-cols-2 gap-3 items-end pt-2 border-t border-white/10">
          <div>
            <label className="text-xs text-slate-400">{tr("iv_coins_label", { n: floor })}</label>
            <Input data-testid="invite-coins" type="number" min={floor} step="50" value={coins} onChange={e => setCoins(parseInt(e.target.value || 0))} className="bg-white/5 border-white/10 mt-1" />
          </div>
          <label className="flex items-start gap-2 text-xs text-slate-300 cursor-pointer" data-testid="invite-ack">
            <input type="checkbox" checked={ack} onChange={e => setAck(e.target.checked)} className="mt-0.5" />
            {tr("iv_ack_label")}
          </label>
        </div>

        <div className="mt-3"><DateCommitmentNote testid="invite-commitment" checked={agree} onCheckedChange={setAgree} /></div>
        <Button data-testid="invite-send-button" disabled={busy || !allFilled || !ack || !agree || !day || !timeOk} onClick={send} className="rose-btn text-white border-0 w-full h-11">
          {tr("iv_send")} · 🪙 {coins}
        </Button>
      </DialogContent>
    </Dialog>
  );
}
