import React from "react";
import { useApp } from "../context/AppContext";
import { t } from "../lib/i18n";

// Tiny 6-month bar chart of coins earned; current month highlighted.
export default function EarningsChart({ data = [] }) {
  const { lang } = useApp();
  const max = Math.max(1, ...data.map((d) => d.earned));
  const label = (m) => { const [y, mo] = m.split("-").map(Number); return new Date(y, mo - 1, 1).toLocaleDateString(undefined, { month: "short" }); };
  return (
    <div className="mt-2.5 pt-2.5 border-t border-amber-500/15" data-testid="vs-earnings-chart">
      <div className="text-[9px] uppercase tracking-wider text-slate-500 mb-1.5">{t("er_chart", lang)}</div>
      <div className="flex items-end gap-1.5 h-12">
        {data.map((d, i) => {
          const cur = i === data.length - 1;
          return (
            <div key={d.month} className="flex-1 flex flex-col justify-end items-center gap-1 h-full group" title={`${label(d.month)} · 🪙 ${d.earned.toLocaleString()}`} data-testid={`vs-earnings-bar-${d.month}`}>
              <div className={`w-full rounded-sm transition-all duration-500 ${cur ? "bg-amber-400" : "bg-amber-500/35 group-hover:bg-amber-500/60"}`}
                style={{ height: `${Math.max(d.earned ? 4 : 2, Math.round((d.earned / max) * 34))}px` }} />
              <span className={`text-[9px] leading-none ${cur ? "text-amber-200" : "text-slate-500"}`}>{label(d.month)}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
