import React from "react";
import { CalendarClock } from "lucide-react";
import { useApp } from "../context/AppContext";
import { t } from "../lib/i18n";

// items: [{ id, start, name, place, tab }] — dates happening today, any role.
export default function DatesToday({ items, onOpen }) {
  const { lang } = useApp();
  const today = new Date().toDateString();
  const now = Date.now();
  const list = items.filter(x => x.start && new Date(x.start).toDateString() === today && x.tab !== "cancelled")
    .sort((a, b) => new Date(a.start) - new Date(b.start));
  const hm = (d) => d.toLocaleTimeString(lang, { hour: "2-digit", minute: "2-digit" });
  return (
    <div className="rounded-2xl border border-white/10 bg-white/[0.02] px-4 py-3 flex items-center gap-3 h-full" data-testid="dates-today-strip">
      <div className="shrink-0 flex items-center gap-2 pe-3 border-e border-white/10">
        <CalendarClock size={16} className="text-amber-300" />
        <div className="leading-tight">
          <div className="text-xs font-semibold text-white">{t("td_today", lang)}</div>
          <div className="text-[10px] text-slate-500">{new Date().toLocaleDateString(lang, { weekday: "short", day: "numeric", month: "short" })}</div>
        </div>
      </div>
      {list.length === 0 ? <span className="text-xs text-slate-500" data-testid="dates-today-empty">{t("td_none", lang)}</span> : (
        <div className="flex gap-2 overflow-x-auto py-0.5" data-testid="dates-today-list">
          {list.map(x => {
            const s = new Date(x.start), e = new Date(s.getTime() + (x.mins || 150) * 60000);
            const live = now >= s.getTime() && now < e.getTime();
            return (
              <button key={x.id} type="button" onClick={() => onOpen(x)} data-testid={`dates-today-${x.id}`}
                className={`shrink-0 flex items-center gap-2 rounded-full border px-3 py-1.5 text-xs transition-colors hover:bg-white/10 ${live ? "border-emerald-400/50 bg-emerald-500/10" : "border-white/10 bg-white/[0.03]"}`}>
                <span className={`h-1.5 w-1.5 rounded-full ${live ? "bg-emerald-400 animate-pulse" : x.tab === "confirmed" ? "bg-sky-400" : x.tab === "past" ? "bg-slate-400" : "bg-amber-400"}`} />
                <span className="font-mono-num text-white">{hm(s)}</span>
                <span className="text-slate-500">–{hm(e)}</span>
                <span className="text-slate-300 truncate max-w-[120px]">{x.name}</span>
                {x.place && <span className="text-slate-500 truncate max-w-[110px]">· {x.place}</span>}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
