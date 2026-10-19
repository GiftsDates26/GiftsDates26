import React from "react";

/**
 * Reusable multi-select chip/tag component.
 * Props:
 *  - value: array of selected values
 *  - onChange: (nextArray) => void
 *  - options: [{ value, label }]
 *  - testid: base data-testid
 *  - accent: "rose" | "amber" (visual accent for active chips)
 */
export default function ChipMultiSelect({ value = [], onChange, options = [], testid = "chips", accent = "rose" }) {
  const toggle = (v) => {
    const on = value.includes(v);
    onChange(on ? value.filter((x) => x !== v) : [...value, v]);
  };
  const activeCls =
    accent === "amber"
      ? "bg-amber-500/20 border-amber-500/50 text-amber-200"
      : "bg-rose-500/20 border-rose-500/50 text-rose-200";
  return (
    <div className="flex flex-wrap gap-2 mt-2" data-testid={testid}>
      {options.map((o) => {
        const on = value.includes(o.value);
        return (
          <button
            type="button"
            key={o.value}
            data-testid={`${testid}-${o.value}`}
            aria-pressed={on}
            onClick={() => toggle(o.value)}
            className={`px-3 py-1.5 rounded-full text-xs border transition-colors ${
              on ? activeCls : "bg-white/5 border-white/10 text-slate-400 hover:bg-white/10"
            }`}
          >
            {o.label}
          </button>
        );
      })}
    </div>
  );
}
