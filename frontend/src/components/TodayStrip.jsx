import React from "react";
import { CalendarClock } from "lucide-react";
import { useApp } from "../context/AppContext";
import { t } from "../lib/i18n";
import { toKey } from "../lib/availability";

const DOT = { pending: "bg-amber-400", confirmed: "bg-sky-400", completed: "bg-emerald-400" };

// items: [{ b, who }] — shows every active date happening today, ordered by start time.
export default function TodayStrip({ items }) {
  const { lang } = useApp();
  const today = toKey(new Date());
  const list = items.filter(({ b }) => b.date === today && ["pending", "confirmed", "completed"].includes(b.status))
    .sort((x, y) => x.b.start.localeCompare(y.b.start));
  const nowHm = new Date().toTimeString().slice(0, 5);
  return (
    <div className="rounded-2xl border border-white/10 bg-white/[0.02] px-4 py-2.5 mb-5 flex items-center gap-3" data-testid="vs-today-strip">
      <div className="shrink-0 flex items-center gap-2 pe-3 border-e border-white/10">
        <CalendarClock size={15} className="text-amber-300" />
        <div className="leading-tight">
          <div className="text-xs font-semibold text-white">{t("td_today", lang)}</div>
          <div className="text-[10px] text-slate-500">{new Date().toLocaleDateString(undefined, { weekday: "short", day: "numeric", month: "short" })}</div>
        </div>
      </div>
      {list.length === 0 ? <span className="text-xs text-slate-500" data-testid="vs-today-empty">{t("td_none", lang)}</span> : (
        <div className="flex gap-2 overflow-x-auto py-0.5" data-testid="vs-today-list">
          {list.map(({ b, who }) => {
            const name = who === "incoming" ? b.requester?.name : b.vip_card?.name;
            const isNow = b.start <= nowHm && (b.end > nowHm || b.end <= b.start);
            return (
              <div key={b.id} data-testid={`vs-today-${b.id}`}
                className={`shrink-0 flex items-center gap-2 rounded-full border px-3 py-1 text-xs ${isNow ? "border-emerald-400/50 bg-emerald-500/10" : "border-white/10 bg-white/[0.03]"}`}>
                <span className={`h-1.5 w-1.5 rounded-full ${DOT[b.status] || "bg-slate-400"}`} />
                <span className="font-mono-num text-white">{b.start}</span>
                <span className="text-slate-500">–{b.end}</span>
                <span className="text-slate-300 truncate max-w-[120px]">{name}</span>
                {(b.late || b.client_late) && <span className="text-[10px] text-amber-300">+{Math.max(b.late?.minutes || 0, b.client_late?.minutes || 0)}′</span>}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
