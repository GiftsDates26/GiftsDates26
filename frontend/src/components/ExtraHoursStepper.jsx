import React from "react";
import { Minus, Plus } from "lucide-react";

export default function ExtraHoursStepper({ label, each = "each", value, onChange, price, testid = "extra-hours" }) {
  return (
    <div className="rounded-xl border border-amber-500/25 bg-amber-500/5 p-3" data-testid={testid}>
      <div className="flex items-center justify-between gap-3">
        <div className="text-xs text-amber-200">
          {label} <span className="text-slate-400">· 🪙 {price} {each}</span>
        </div>
        <div className="flex items-center gap-2">
          <button type="button" data-testid={`${testid}-minus`} disabled={value <= 0} onClick={() => onChange(Math.max(0, value - 1))}
            className="h-7 w-7 rounded-full border border-white/15 bg-white/5 flex items-center justify-center text-slate-200 hover:bg-white/10 disabled:opacity-40 transition-colors">
            <Minus size={13} />
          </button>
          <span className="font-mono-num text-sm w-6 text-center text-white" data-testid={`${testid}-value`}>{value}</span>
          <button type="button" data-testid={`${testid}-plus`} onClick={() => onChange(value + 1)}
            className="h-7 w-7 rounded-full border border-amber-500/40 bg-amber-500/15 flex items-center justify-center text-amber-200 hover:bg-amber-500/25 transition-colors">
            <Plus size={13} />
          </button>
        </div>
      </div>
      {value > 0 && <div className="text-[11px] text-slate-400 mt-1.5" data-testid={`${testid}-total`}>+ 🪙 {value * price} ({value} × {price})</div>}
    </div>
  );
}
