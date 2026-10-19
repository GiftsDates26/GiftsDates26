import React, { useEffect, useMemo } from "react";
import { Clock, Moon } from "lucide-react";
import ClockTimePicker from "./ClockTimePicker";
import { freeStarts, freeRanges, quickSlots, minHm, SLOT, crossesMidnight, minStartFor } from "../lib/availability";
import { useApp } from "../context/AppContext";
import { t } from "../lib/i18n";

const fmt = (m) => `${minHm(m)}${m >= 1440 ? " +1" : ""}`;

export default function TimeChooser({ day, wins = [], taken = [], value, onChange, testid = "time-chooser", slot = SLOT, note, vertical = false }) {
  const { lang } = useApp();
  const minStart = minStartFor(day);
  const starts = useMemo(() => freeStarts(wins, taken, minStart, slot), [JSON.stringify(wins), JSON.stringify(taken), minStart, slot]); // eslint-disable-line
  const quick = quickSlots(wins, slot).filter(s => starts.includes(s));
  useEffect(() => { if (!starts.includes(value)) onChange(starts[0] ?? null); }, [starts]); // eslint-disable-line

  const pastNote = minStart >= 0 && <p className="text-[11px] text-amber-300/80" data-testid={`${testid}-past-note`}>{t("tc_past_note", lang)}</p>;
  if (!starts.length) return (
    <div className="mt-2 space-y-2 text-xs">
      <div className="text-slate-500" data-testid={`${testid}-no-slots`}>{t("no_slots", lang)}</div>{pastNote}
    </div>
  );
  return (
    <div className={`mt-2 grid gap-4 ${vertical ? "justify-items-center" : "sm:grid-cols-[auto_1fr] items-start"}`} data-testid={testid}>
      <ClockTimePicker starts={starts} value={value} onChange={onChange} />
      <div className="space-y-3 text-xs w-full">
        <div className="rounded-xl border border-rose-500/30 bg-rose-500/5 p-3" data-testid={`${testid}-summary`}>
          <div className="flex justify-between"><span className="text-slate-400">{t("clock_starts", lang)}</span><b className="font-mono-num text-white">{value == null ? "—" : fmt(value)}</b></div>
          <div className="flex justify-between mt-1"><span className="text-slate-400">{t("clock_ends", lang)}</span><b className="font-mono-num text-white">{value == null ? "—" : fmt(value + slot)}</b></div>
        </div>
        <div>
          <div className="text-slate-400 mb-1 flex items-center gap-1"><Clock size={11} /> {t("av_open_hours", lang)}</div>
          <div className="flex flex-wrap gap-1.5">
            {freeRanges(wins, taken, minStart, slot).map((w, i) => <span key={i} className="px-2 py-0.5 rounded-md bg-emerald-500/15 border border-emerald-500/30 text-emerald-200 font-mono-num">{w.from}–{w.to}{crossesMidnight(w) && <Moon size={10} className="inline ml-1" />}</span>)}
          </div>
        </div>
        {quick.length > 0 && (
          <div>
            <div className="text-slate-400 mb-1">{slot === SLOT ? t("quick_slots", lang) : t("quick_slots_n", lang).replace("{h}", slot / 60)}</div>
            <div className="flex flex-wrap gap-1.5">
              {quick.map(s => (
                <button key={s} type="button" onClick={() => onChange(s)} data-testid={`${testid}-quick-${minHm(s)}`}
                  className={`px-2 py-1 rounded-md border font-mono-num transition-colors ${value === s ? "bg-rose-500 border-rose-500 text-white" : "bg-white/5 border-white/10 text-slate-200 hover:bg-white/10"}`}>
                  {fmt(s)}–{fmt(s + slot)}
                </button>
              ))}
            </div>
          </div>
        )}
        {pastNote}
        {note !== null && <p className="text-[11px] text-slate-500">{note || t("any_time_note", lang)}</p>}
      </div>
    </div>
  );
}
