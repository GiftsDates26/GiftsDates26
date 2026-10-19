import React from "react";
import { useNavigate } from "react-router-dom";
import { CalendarHeart, ArrowRight } from "lucide-react";
import { useApp } from "../context/AppContext";
import { t } from "../lib/i18n";
import { DATE_FILTERS } from "../lib/dateFilters";

export const SectionTitle = ({ label, count }) => (
  <div className="flex items-center gap-2 mb-4">
    <h2 className="text-base md:text-lg font-semibold text-slate-100">{label}</h2>
    {count > 0 && <span className="text-xs font-mono-num px-2 py-0.5 rounded-full bg-rose-500/15 border border-rose-500/30 text-rose-200">{count}</span>}
  </div>
);

export const Stat = ({ label, value }) => (
  <div className="rounded-xl border border-white/10 bg-white/[0.03] px-4 py-2.5 min-w-[7.5rem]">
    <div className="text-[11px] uppercase tracking-wider text-slate-500">{label}</div>
    <div className="text-2xl font-mono-num text-white">{value}</div>
  </div>
);

export const EmptyLine = ({ text }) => (
  <p className="text-sm text-slate-500 rounded-xl border border-dashed border-white/10 px-4 py-6 text-center">{text}</p>
);

export function EmptyDates() {
  const { lang } = useApp();
  const nav = useNavigate();
  return (
    <div className="rounded-2xl border border-white/10 bg-white/[0.02] px-6 py-16 text-center" data-testid="dates-empty-state">
      <div className="mx-auto w-14 h-14 rounded-2xl bg-rose-500/10 border border-rose-500/30 flex items-center justify-center mb-4">
        <CalendarHeart className="text-rose-300" size={26} />
      </div>
      <h3 className="font-serif-luxe text-2xl">{t("dates_empty_title", lang)}</h3>
      <p className="text-sm text-slate-400 mt-2 max-w-sm mx-auto">{t("dates_empty_body", lang)}</p>
      <button type="button" onClick={() => nav("/browse")} data-testid="dates-empty-browse"
        className="mt-6 inline-flex items-center gap-2 h-10 px-5 rounded-full rose-btn text-white text-sm transition-transform hover:-translate-y-0.5">
        {t("dates_empty_cta", lang)} <ArrowRight size={15} />
      </button>
    </div>
  );
}

export function FilterBar({ value, onChange, counts }) {
  const { lang } = useApp();
  return (
    <div className="flex flex-wrap gap-2 mb-8" role="tablist" data-testid="dates-filter-bar">
      {DATE_FILTERS.map(f => (
        <button key={f} type="button" role="tab" aria-selected={value === f} onClick={() => onChange(f)} data-testid={`dates-filter-${f}`}
          className={`inline-flex items-center gap-2 h-9 px-4 rounded-full text-sm border transition-colors ${value === f ? "bg-rose-500 border-rose-500 text-white" : "bg-white/[0.03] border-white/10 text-slate-300 hover:bg-white/10 hover:text-white"}`}>
          {t(`df_${f}`, lang)}
          <span className={`text-[11px] font-mono-num px-1.5 rounded-full ${value === f ? "bg-white/20" : "bg-white/10 text-slate-400"}`}>{counts[f] || 0}</span>
        </button>
      ))}
    </div>
  );
}
