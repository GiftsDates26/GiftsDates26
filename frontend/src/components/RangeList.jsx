import React from "react";
import { Plus, X, Moon } from "lucide-react";
import { Input } from "./ui/input";
import { Button } from "./ui/button";
import { crossesMidnight, hmMin, minHm, DEFAULT_WIN } from "../lib/availability";
import { useApp } from "../context/AppContext";
import { t } from "../lib/i18n";

const nextRange = (ranges) => {
  if (!ranges.length) return DEFAULT_WIN;
  const s = hmMin(ranges[ranges.length - 1].to) + 60;
  return { from: minHm(s), to: minHm(s + 180) };
};

export default function RangeList({ ranges = [], onChange, testid }) {
  const { lang } = useApp();
  const set = (i, k, v) => onChange(ranges.map((r, idx) => (idx === i ? { ...r, [k]: v } : r)));
  return (
    <div className="space-y-2" data-testid={testid}>
      {ranges.map((r, i) => (
        <div key={i} className="flex items-center gap-2">
          <Input type="time" step="900" value={r.from} onChange={e => set(i, "from", e.target.value)} data-testid={`${testid}-from-${i}`} className="bg-white/5 border-white/10 h-9 w-[7.5rem]" />
          <span className="text-slate-500">—</span>
          <Input type="time" step="900" value={r.to} onChange={e => set(i, "to", e.target.value)} data-testid={`${testid}-to-${i}`} className="bg-white/5 border-white/10 h-9 w-[7.5rem]" />
          {crossesMidnight(r) && <Moon size={13} className="text-sky-300" title={t("overnight_note", lang)} />}
          <button type="button" onClick={() => onChange(ranges.filter((_, idx) => idx !== i))} data-testid={`${testid}-remove-${i}`}
            className="p-1.5 rounded-md text-slate-400 hover:text-rose-300 hover:bg-white/5 transition-colors"><X size={14} /></button>
        </div>
      ))}
      {ranges.length < 8 && (
        <Button type="button" size="sm" variant="ghost" onClick={() => onChange([...ranges, nextRange(ranges)])} data-testid={`${testid}-add`}
          className="h-8 text-rose-300 hover:text-rose-200 hover:bg-rose-500/10 px-2"><Plus size={14} className="mr-1" />{t("av_add_range", lang)}</Button>
      )}
    </div>
  );
}
