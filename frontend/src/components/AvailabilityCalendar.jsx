import React from "react";
import { CalendarDays, Repeat } from "lucide-react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "./ui/tabs";
import WeeklySchedule from "./WeeklySchedule";
import SpecificDays from "./SpecificDays";
import { useApp } from "../context/AppContext";
import { t } from "../lib/i18n";

export { toKey, fromKey, crossesMidnight } from "../lib/availability";

export default function AvailabilityCalendar({ value = [], ranges = {}, weekly = {}, legacySlots = {}, timeWindow, onChange }) {
  const { lang } = useApp();
  const fallback = (k) => legacySlots[k] || timeWindow;
  const weeklyCount = Object.values(weekly).filter(r => r && r.length).length;
  const trig = "data-[state=active]:bg-rose-500 data-[state=active]:text-white gap-1.5";
  return (
    <div className="glass rounded-2xl p-6 mb-6" data-testid="profile-availability-section">
      <h2 className="font-serif-luxe text-2xl">{t("availability", lang)}</h2>
      <p className="text-xs text-slate-400 mt-1 mb-4">{t("av_new_hint", lang)}</p>
      <Tabs defaultValue="weekly">
        <TabsList className="bg-white/5 border border-white/10 mb-4">
          <TabsTrigger value="weekly" className={trig} data-testid="availability-tab-weekly"><Repeat size={13} />{t("av_weekly", lang)} · {weeklyCount}</TabsTrigger>
          <TabsTrigger value="days" className={trig} data-testid="availability-tab-days"><CalendarDays size={13} />{t("av_specific_days", lang)} · {value.length}</TabsTrigger>
        </TabsList>
        <TabsContent value="weekly">
          <p className="text-[11px] text-slate-500 mb-2">{t("av_weekly_hint", lang)}</p>
          <WeeklySchedule weekly={weekly} onChange={w => onChange({ availability_weekly: w })} />
        </TabsContent>
        <TabsContent value="days">
          <SpecificDays days={value} ranges={ranges} weekly={weekly} fallback={fallback}
            onChange={(days, r) => onChange({ availability: days, availability_ranges: r })} />
        </TabsContent>
      </Tabs>
      <p className="text-[11px] text-amber-300/80 mt-4">🔒 {t("buffer_note", lang)}</p>
    </div>
  );
}
