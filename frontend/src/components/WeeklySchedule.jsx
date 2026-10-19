import React from "react";
import { Copy } from "lucide-react";
import { toast } from "sonner";
import { Switch } from "./ui/switch";
import RangeList from "./RangeList";
import { DEFAULT_WIN } from "../lib/availability";
import { useApp } from "../context/AppContext";
import { t } from "../lib/i18n";

export default function WeeklySchedule({ weekly = {}, onChange }) {
  const { lang } = useApp();
  const setDay = (d, ranges) => { const w = { ...weekly }; if (ranges.length) w[d] = ranges; else delete w[d]; onChange(w); };
  const copyAll = (d) => {
    onChange(Object.fromEntries(["0", "1", "2", "3", "4", "5", "6"].map(k => [k, weekly[d].map(r => ({ ...r }))])));
    toast.success(t("av_copied", lang));
  };
  return (
    <div className="divide-y divide-white/5" data-testid="weekly-schedule">
      {["0", "1", "2", "3", "4", "5", "6"].map(d => {
        const open = !!(weekly[d] && weekly[d].length);
        return (
          <div key={d} className="py-3 flex flex-wrap items-start gap-4">
            <div className="w-32 flex items-center gap-3 pt-1.5">
              <Switch checked={open} onCheckedChange={v => setDay(d, v ? [DEFAULT_WIN] : [])} data-testid={`weekly-toggle-${d}`} />
              <span className={`text-sm ${open ? "text-white" : "text-slate-500"}`}>{t(`wd_${d}`, lang)}</span>
            </div>
            {open
              ? <div className="flex-1 min-w-[240px] flex flex-wrap items-start justify-between gap-2">
                  <RangeList ranges={weekly[d]} onChange={r => setDay(d, r)} testid={`weekly-ranges-${d}`} />
                  <button type="button" onClick={() => copyAll(d)} data-testid={`weekly-copy-all-${d}`}
                    className="inline-flex items-center gap-1.5 h-8 px-2.5 rounded-md text-xs text-slate-300 border border-white/10 bg-white/5 hover:bg-white/10 hover:text-white transition-colors">
                    <Copy size={12} />{t("av_copy_all", lang)}
                  </button>
                </div>
              : <span className="text-xs text-slate-500 pt-2.5">{t("av_closed", lang)}</span>}
          </div>
        );
      })}
    </div>
  );
}
