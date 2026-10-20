import React, { useState } from "react";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { Label } from "./ui/label";
import { Calendar } from "./ui/calendar";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "./ui/tabs";
import { Plus, Trash2, CalendarClock, Loader2, Repeat } from "lucide-react";
import { toast } from "sonner";
import { api } from "../lib/api";
import { useApp } from "../context/AppContext";
import RangeList from "./RangeList";
import WeeklySchedule from "./WeeklySchedule";
import { toKey, fromKey, crossesMidnight, DEFAULT_WIN } from "../lib/availability";
import { t } from "../lib/i18n";

const fmtDay = (d) => { try { return fromKey(d).toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" }); } catch { return d; } };
const toApi = (rs) => rs.map((r) => ({ start: r.from, end: r.to }));
const ERR = { VIP_REQUIRED: "vs_vip_required", NO_WEEKDAYS: "vs_pick_day_err", NOTHING_TO_ADD: "vs_pick_day_err", HAS_BOOKINGS: "vs_has_bookings", TIME_OVERLAP: "vs_overlap_err" };

function PublishedList({ blocks, onRemove, onRemoveAll, onRemoveDay, lang }) {
  const byDate = {};
  blocks.forEach((b) => { (byDate[b.date] = byDate[b.date] || []).push(b); });
  const dates = Object.keys(byDate).sort();
  return (
    <div>
      <div className="flex items-center justify-between gap-2 mb-2">
        <div className="text-xs text-slate-400">{t("vs_published", lang)} · <b className="text-white" data-testid="vs-avail-count">{blocks.length}</b></div>
        {blocks.length > 0 && <button type="button" onClick={onRemoveAll} data-testid="vs-avail-delete-all"
          className="inline-flex items-center gap-1 rounded-full border border-rose-500/40 bg-rose-500/10 px-3 py-1 text-xs text-rose-200 hover:bg-rose-500/20 transition-colors">
          <Trash2 size={12} />{t("vs_delete_all", lang)}</button>}
      </div>
      {dates.length === 0 ? <div className="text-xs text-slate-500">{t("vs_none_yet", lang)}</div> : (
        <div className="space-y-2" data-testid="vs-avail-list">
          {dates.map((d) => (
            <div key={d} className="rounded-xl border border-white/10 bg-white/5 p-3">
              <div className="flex items-center justify-between mb-1.5">
                <div className="text-xs font-semibold text-white">{fmtDay(d)}</div>
                <button type="button" onClick={() => onRemoveDay(d)} data-testid={`vs-avail-del-day-${d}`} title={t("vs_delete_day", lang)}
                  className="inline-flex items-center gap-1 text-[11px] text-rose-300/80 hover:text-rose-200 transition-colors"><Trash2 size={12} />{t("vs_delete_day", lang)}</button>
              </div>
              <div className="flex flex-wrap gap-1.5">
                {byDate[d].sort((a, b) => a.start.localeCompare(b.start)).map((b) => (
                  <span key={b.id} data-testid={`vs-avail-block-${b.id}`} className="inline-flex items-center gap-1.5 text-[11px] px-2 py-1 rounded-lg bg-emerald-500/15 border border-emerald-500/30 text-emerald-200 font-mono-num">
                    {b.recurring ? <Repeat size={10} /> : null}{b.start}–{b.end}{crossesMidnight({ from: b.start, to: b.end }) ? " 🌙" : ""}
                    <button onClick={() => onRemove(b.id)} data-testid={`vs-avail-del-${b.id}`} className="text-rose-300 hover:text-rose-200"><Trash2 size={12} /></button>
                  </span>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default function VipAvailabilityEditor({ blocks = [], onChanged }) {
  const { lang } = useApp();
  const [days, setDays] = useState([]);
  const [ranges, setRanges] = useState([DEFAULT_WIN]);
  const [weekly, setWeekly] = useState({});
  const [weeks, setWeeks] = useState(8);
  const slotLen = 60;
  const [saving, setSaving] = useState(false);
  const tz = Intl.DateTimeFormat().resolvedOptions().timeZone;

  const run = async (fn) => {
    setSaving(true);
    try {
      const r = await fn();
      if (r.data.created || !r.data.skipped_overlap) toast.success(t("vs_added", lang).replace("{n}", r.data.created));
      if (r.data.skipped_overlap) toast.warning(t("vs_overlap_skipped", lang).replace("{n}", r.data.skipped_overlap));
      onChanged?.();
    }
    catch (e) { const d = e.response?.data?.detail || ""; toast.error(ERR[d] ? t(ERR[d], lang) : d || "Error"); }
    finally { setSaving(false); }
  };
  // two ranges in the same form may not cover the same time of day
  const clash = (rs) => { const iv = toApi(rs).map(({ start, end }) => { const [a, b] = [start, end].map((x) => +x.slice(0, 2) * 60 + +x.slice(3, 5)); return [a, b > a ? b : b + 1440]; }).sort((x, y) => x[0] - y[0]); return iv.some((x, i) => i && x[0] < iv[i - 1][1]); };
  const addDays = () => clash(ranges) ? toast.error(t("vs_overlap_err", lang)) : days.length ? run(() => api.post("/vip/schedule/availability/bulk", { dates: days.map(toKey), ranges: toApi(ranges), slot_len: slotLen, tz })) : toast.error(t("vs_pick_day_err", lang));
  const addWeekly = () => Object.values(weekly).some(clash) ? toast.error(t("vs_overlap_err", lang)) : run(() => api.post("/vip/schedule/availability/weekly", { weekly: Object.fromEntries(Object.entries(weekly).map(([k, v]) => [k, toApi(v)])), weeks, slot_len: slotLen, tz }));
  const remove = async (id) => {
    try { await api.delete(`/vip/schedule/availability/${id}`); toast.success(t("vs_removed", lang)); onChanged?.(); }
    catch (e) { const d = e.response?.data?.detail || ""; toast.error(ERR[d] ? t(ERR[d], lang) : d || "Error"); }
  };
  const removeAll = async () => {
    if (!window.confirm(t("vs_delete_all_confirm", lang))) return;
    try {
      const r = await api.delete("/vip/schedule/availability");
      toast.success(t("vs_deleted_all", lang).replace("{n}", r.data.deleted));
      if (r.data.kept) toast.warning(t("vs_kept_booked", lang).replace("{n}", r.data.kept));
      onChanged?.();
    } catch (e) { toast.error(e.response?.data?.detail || "Error"); }
  };
  const removeDay = async (d) => {
    if (!window.confirm(t("vs_delete_day_confirm", lang).replace("{d}", fmtDay(d)))) return;
    try { const r = await api.delete("/vip/schedule/availability", { params: { date: d } }); toast.success(t("vs_deleted_all", lang).replace("{n}", r.data.deleted)); onChanged?.(); }
    catch (e) { const x = e.response?.data?.detail || ""; toast.error(ERR[x] ? t(ERR[x], lang) : x || "Error"); }
  };
  const btn = (onClick, label, testid) => (
    <Button data-testid={testid} onClick={onClick} disabled={saving} className="rose-btn text-white border-0 w-full mt-4 h-10">
      {saving ? <Loader2 size={15} className="animate-spin" /> : <><Plus size={15} className="me-1" /> {label}</>}
    </Button>
  );

  return (
    <div className="glass rounded-2xl p-6 space-y-5" data-testid="vip-schedule-manager">
      <div>
        <h2 className="font-serif-luxe text-2xl flex items-center gap-2"><CalendarClock size={20} className="text-amber-300" /> {t("vs_title", lang)}</h2>
        <p className="text-xs text-slate-400 mt-1">{t("vs_intro", lang)}</p>
      </div>
      <Tabs defaultValue="days">
        <TabsList className="bg-white/5 border border-white/10">
          <TabsTrigger value="days" data-testid="vs-avail-tab-days" className="data-[state=active]:bg-rose-500 data-[state=active]:text-white">{t("vs_mode_days", lang)}</TabsTrigger>
          <TabsTrigger value="weekly" data-testid="vs-avail-tab-weekly" className="data-[state=active]:bg-rose-500 data-[state=active]:text-white">{t("vs_mode_weekly", lang)}</TabsTrigger>
        </TabsList>
        <TabsContent value="days" className="mt-4">
          <div className="flex flex-wrap gap-6 items-start">
            <div className="rounded-xl border border-white/10 bg-white/5" data-testid="vip-schedule-calendar">
              <Calendar mode="multiple" selected={days} onSelect={(d) => setDays(d || [])} disabled={{ before: new Date(new Date().setHours(0, 0, 0, 0)) }}
                modifiers={{ has: blocks.map((b) => fromKey(b.date)) }} modifiersClassNames={{ has: "ring-1 ring-emerald-400/60 rounded-md" }}
                classNames={{ day_selected: "bg-rose-500 text-white hover:bg-rose-500 focus:bg-rose-500" }} />
            </div>
            <div className="flex-1 min-w-[260px] rounded-xl border border-white/10 bg-white/5 p-4">
              <div className="text-sm font-semibold text-white" data-testid="vs-avail-days-count">{t("vs_days_selected", lang).replace("{n}", days.length)}</div>
              <Label className="text-[11px] text-slate-400 mt-3 mb-1.5 block">{t("vs_time_ranges", lang)}</Label>
              <RangeList ranges={ranges} onChange={setRanges} testid="vs-avail-ranges" />
              {btn(addDays, t("vs_add_days", lang), "vs-avail-add")}
            </div>
          </div>
        </TabsContent>
        <TabsContent value="weekly" className="mt-4 rounded-xl border border-white/10 bg-white/5 p-4">
          <WeeklySchedule weekly={weekly} onChange={setWeekly} />
          <div className="flex items-center gap-2 mt-3">
            <Label className="text-[11px] text-slate-400">{t("vs_weeks", lang)}</Label>
            <Input data-testid="vs-avail-weeks" type="number" min={1} max={26} value={weeks} onChange={(e) => setWeeks(Math.max(1, Math.min(26, parseInt(e.target.value || 1))))} className="bg-white/5 border-white/10 h-8 w-16" />
          </div>
          {btn(addWeekly, t("vs_add_weekly", lang), "vs-avail-add-weekly")}
        </TabsContent>
      </Tabs>
      <PublishedList blocks={blocks} onRemove={remove} onRemoveAll={removeAll} onRemoveDay={removeDay} lang={lang} />
    </div>
  );
}
