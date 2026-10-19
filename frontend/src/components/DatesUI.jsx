import React from "react";
import { useNavigate } from "react-router-dom";
import { CalendarHeart, ArrowRight, Inbox, Send, CalendarClock, Ban, History } from "lucide-react";
import { useApp } from "../context/AppContext";
import { t } from "../lib/i18n";
import { DATE_FILTERS, DATE_TABS } from "../lib/dateFilters";

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

const TAB_META = {
  requests: { icon: Inbox, label: "vb_requests", tone: "text-rose-300", ring: "border-rose-500/50 bg-rose-500/10" },
  mine: { icon: Send, label: "vb_mine", tone: "text-sky-300", ring: "border-sky-500/50 bg-sky-500/10" },
  confirmed: { icon: CalendarClock, label: "vb_confirmed", tone: "text-emerald-300", ring: "border-emerald-500/50 bg-emerald-500/10" },
  cancelled: { icon: Ban, label: "vb_cancel_refused", tone: "text-red-300", ring: "border-red-500/50 bg-red-500/10" },
  past: { icon: History, label: "vb_past", tone: "text-slate-300", ring: "border-white/30 bg-white/[0.06]" },
};

export function DatesStatTiles({ value, onChange, counts }) {
  const { lang } = useApp();
  return (
    <div className="grid grid-cols-2 sm:grid-cols-5 gap-3 mb-6" data-testid="dates-stat-tiles">
      {DATE_TABS.map(k => { const m = TAB_META[k]; const Icon = m.icon; const on = value === k; return (
        <button key={k} type="button" onClick={() => onChange(k)} data-testid={`dates-tile-${k}`}
          className={`text-start rounded-xl border px-4 py-3 transition-[background-color,border-color,transform] duration-200 hover:-translate-y-0.5 ${on ? m.ring : "border-white/10 bg-white/[0.03] hover:bg-white/[0.06]"}`}>
          <Icon size={15} className={m.tone} />
          <div className={`font-mono-num text-3xl mt-1 ${on ? "text-white" : m.tone}`} data-testid={`dates-tile-count-${k}`}>{counts[k] || 0}</div>
          <div className="text-[10px] uppercase tracking-wider text-slate-500 truncate">{t(m.label, lang)}</div>
        </button>
      ); })}
    </div>
  );
}

export function DatesTabBar({ value, onChange, counts }) {
  const { lang } = useApp();
  return (
    <div className="sticky top-16 z-20 -mx-4 px-4 py-2 bg-[#0D0B12]/85 backdrop-blur-xl border-b border-white/10">
      <div className="flex gap-1 overflow-x-auto flex-nowrap" role="tablist" data-testid="dates-tabs">
        {DATE_TABS.map(k => { const m = TAB_META[k]; const Icon = m.icon; const on = value === k; const n = counts[k] || 0; return (
          <button key={k} type="button" role="tab" aria-selected={on} onClick={() => onChange(k)} data-testid={`dates-tab-${k}`}
            className={`shrink-0 inline-flex items-center rounded-full px-4 py-2 text-sm border transition-colors ${on ? "bg-white/[0.07] border-amber-400/40 text-amber-100" : "border-transparent text-slate-400 hover:text-white"}`}>
            <Icon size={14} className="me-1.5" />{t(m.label, lang)}
            {n > 0 && <span className={`ms-1.5 text-[10px] rounded-full px-1.5 py-0.5 font-mono-num ${k === "requests" ? "bg-rose-500 text-white" : "bg-white/10 text-slate-200"}`}>{n}</span>}
          </button>
        ); })}
      </div>
    </div>
  );
}

export function TabEmpty({ tab }) {
  const { lang } = useApp();
  const m = TAB_META[tab]; const Icon = m.icon;
  return (
    <div className="rounded-2xl border border-dashed border-white/10 px-6 py-12 text-center" data-testid={`dates-empty-${tab}`}>
      <Icon className={`mx-auto mb-3 ${m.tone}`} size={24} />
      <div className="text-sm text-slate-300">{t("dp_empty", lang)}</div>
      <div className="text-xs text-slate-500 mt-1">{t(`dp_hint_${tab}`, lang)}</div>
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
