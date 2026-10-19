import React from "react";
import { CalendarClock, Moon, Repeat, Star } from "lucide-react";
import { useApp } from "../context/AppContext";
import { t } from "../lib/i18n";
import { toKey, fromKey, freeStarts, freeRanges, crossesMidnight, bestDayKeys, minStartFor } from "../lib/availability";

const wdName = (i, lang) => new Date(2024, 0, 1 + i).toLocaleDateString(lang, { weekday: "short" }); // 1 Jan 2024 = Mon
const Range = ({ w }) => (
  <span className="px-2 py-0.5 rounded-md bg-emerald-500/15 border border-emerald-500/30 text-emerald-200 font-mono-num text-[11px] whitespace-nowrap">
    {w.from}–{w.to}{crossesMidnight(w) && <Moon size={9} className="inline ml-1" />}
  </span>
);

export default function AvailabilityOverview({ avail, selected, onPick, max = 14, testid = "avail-overview" }) {
  const { lang } = useApp();
  if (!avail) return null;
  const today = toKey(new Date());
  const busy = new Set(avail.busy_days || []);
  const weekly = Object.entries(avail.weekly || {}).filter(([, r]) => r?.length).sort(([a], [b]) => a - b);
  const days = Object.entries(avail.day_windows || {})
    .filter(([k]) => k >= today && !busy.has(k))
    .map(([k, w]) => { const taken = (avail.busy_slots || {})[k] || []; const m = minStartFor(k); return { k, wins: freeRanges(w, taken, m), n: freeStarts(w, taken, m).length }; })
    .filter(d => d.n > 0).sort((a, b) => a.k.localeCompare(b.k)).slice(0, max);

  const best = new Set(bestDayKeys(avail, today));
  if (!avail.restricted) return <div className="text-xs text-emerald-200" data-testid={`${testid}-open`}>{t("ao_open_any", lang)}</div>;
  return (
    <div className="space-y-4 text-xs" data-testid={testid}>
      {weekly.length > 0 && (
        <div data-testid={`${testid}-weekly`}>
          <div className="text-slate-400 mb-1.5 flex items-center gap-1"><Repeat size={11} />{t("ao_every_week", lang)}</div>
          <div className="flex flex-wrap gap-x-4 gap-y-1.5">
            {weekly.map(([d, r]) => <div key={d} className="flex items-center gap-1.5"><span className="text-slate-300 w-8">{wdName(+d, lang)}</span>{r.map((w, i) => <Range key={i} w={w} />)}</div>)}
          </div>
        </div>
      )}
      <div>
        <div className="text-slate-400 mb-1.5 flex flex-wrap items-center gap-x-3 gap-y-1"><span className="flex items-center gap-1"><CalendarClock size={11} />{t("ao_next_open", lang)}</span>
          {best.size > 0 && <span className="flex items-center gap-1 text-amber-200/80"><Star size={10} className="fill-amber-300 text-amber-300" />{t("ao_best_hint", lang)}</span>}</div>
        {!days.length ? <div className="text-slate-500" data-testid={`${testid}-none`}>{t("no_slots", lang)}</div> : (
          <div className="divide-y divide-white/5 rounded-xl border border-white/10 max-h-72 overflow-y-auto">
            {days.map(({ k, wins, n }) => {
              const Tag = onPick ? "button" : "div";
              return (
                <Tag key={k} type={onPick ? "button" : undefined} onClick={onPick ? () => onPick(k) : undefined} data-testid={`${testid}-day-${k}`}
                  className={`w-full text-left flex flex-wrap items-center gap-2 px-3 py-2 transition-colors ${selected === k ? "bg-rose-500/15" : best.has(k) ? "bg-amber-400/[0.06] hover:bg-amber-400/10" : onPick ? "hover:bg-white/5" : ""}`}>
                  <span className="w-24 shrink-0 text-slate-200">{fromKey(k).toLocaleDateString(lang, { weekday: "short", day: "numeric", month: "short" })}</span>
                  <span className="flex flex-wrap gap-1.5 flex-1">{wins.map((w, i) => <Range key={i} w={w} />)}
                  </span>
                  {best.has(k) && <span data-testid={`${testid}-best-${k}`} className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-amber-400/15 border border-amber-400/40 text-amber-200 text-[11px] whitespace-nowrap"><Star size={10} className="fill-amber-300 text-amber-300" />{t("ao_best", lang)}</span>}
                  <span className={`whitespace-nowrap ${best.has(k) ? "text-amber-200/80" : "text-slate-500"}`}>{t("ao_starts", lang).replace("{n}", n)}</span>
                </Tag>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
