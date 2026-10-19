import React, { useState } from "react";
import { Calendar } from "./ui/calendar";
import RangeList from "./RangeList";
import { toKey, fromKey, weekdayOf, DEFAULT_WIN } from "../lib/availability";
import { useApp } from "../context/AppContext";
import { t } from "../lib/i18n";

export default function SpecificDays({ days = [], ranges = {}, onChange, weekly = {}, fallback }) {
  const { lang } = useApp();
  const [edit, setEdit] = useState(null);
  const rangesFor = (k) => ranges[k] || [fallback(k) || DEFAULT_WIN];
  const onSelect = (sel) => {
    const keys = (sel || []).map(toKey).sort();
    const r = Object.fromEntries(keys.map(k => [k, rangesFor(k)]));
    const added = keys.find(k => !days.includes(k));
    onChange(keys, r);
    setEdit(added || (keys.includes(edit) ? edit : null));
  };
  const setRanges = (k, list) => {
    if (!list.length) { onSelect(days.filter(d => d !== k).map(fromKey)); return; }
    onChange(days, { ...ranges, [k]: list });
  };
  const weeklyOpen = (d) => !!(weekly[weekdayOf(toKey(d))] || []).length;

  return (
    <div className="flex flex-wrap gap-6 items-start">
      <div data-testid="profile-availability-calendar" className="rounded-xl border border-white/10 bg-white/5">
        <Calendar mode="multiple" selected={days.map(fromKey)} onSelect={onSelect} disabled={{ before: new Date() }}
          modifiers={{ weekly: weeklyOpen }} modifiersClassNames={{ weekly: "ring-1 ring-emerald-400/40 rounded-md" }}
          classNames={{ day_selected: "bg-rose-500 text-white hover:bg-rose-500 focus:bg-rose-500" }} />
      </div>
      <div className="flex-1 min-w-[260px] space-y-4">
        <div className="text-xs text-slate-400">{t("av_specific_days", lang)} · <b className="text-white" data-testid="profile-availability-count">{days.length}</b></div>
        <div className="flex flex-wrap gap-1.5">
          {days.slice(0, 40).map(k => (
            <button key={k} type="button" data-testid={`profile-day-chip-${k}`} onClick={() => setEdit(edit === k ? null : k)}
              className={`px-2 py-0.5 rounded-full border text-xs font-mono-num transition-colors ${edit === k ? "bg-rose-500 text-white border-rose-500" : "bg-rose-500/15 border-rose-500/30 hover:bg-rose-500/25"}`}>
              {k} · {rangesFor(k).map(r => `${r.from}–${r.to}`).join(", ")}
            </button>
          ))}
        </div>
        {edit && (
          <div className="rounded-xl border border-violet-500/30 bg-violet-500/5 p-4" data-testid="profile-day-slot-editor">
            <div className="text-xs text-violet-300 mb-2">{t("custom_time_for", lang).replace("{d}", edit)}</div>
            <RangeList ranges={rangesFor(edit)} onChange={l => setRanges(edit, l)} testid="day-ranges" />
          </div>
        )}
        <p className="text-[11px] text-slate-500">{t("av_specific_hint", lang)}</p>
      </div>
    </div>
  );
}
