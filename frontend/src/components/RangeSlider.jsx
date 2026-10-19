import React from "react";
import * as SliderPrimitive from "@radix-ui/react-slider";

/**
 * Two-thumb range slider for min–max filters.
 * Empty string ("") for lo/hi means "no limit" — thumbs sit at the outer bounds.
 * onChange(lo, hi) returns "" for a side that is back at its bound, so no filter is sent.
 */
export default function RangeSlider({ testid, label, min, max, step = 1, unit = "", lo, hi, onChange, anyLabel = "Any", disabled, format }) {
  const a = lo === "" || lo == null ? min : Number(lo);
  const b = hi === "" || hi == null ? max : Number(hi);
  const isAny = a <= min && b >= max;
  const fmt = (v, bound) => `${format ? format(v) : v}${bound === max && v >= max ? "+" : ""}`;
  return (
    <div className="min-w-[230px] flex-1 max-w-[340px]" data-testid={testid}>
      <div className="flex items-center justify-between text-xs">
        <span className="text-slate-400">{label}</span>
        <span data-testid={`${testid}-value`} className={`font-mono-num ${isAny ? "text-slate-500" : "text-rose-200"}`}>
          {isAny ? anyLabel : `${fmt(a, min)} – ${fmt(b, max)} ${unit}`}
        </span>
      </div>
      <SliderPrimitive.Root
        className="relative flex w-full touch-none select-none items-center h-9 mt-1 data-[disabled]:opacity-50"
        min={min} max={max} step={step} minStepsBetweenThumbs={1}
        value={[a, b]} disabled={disabled}
        onValueChange={([x, y]) => onChange(x <= min ? "" : String(x), y >= max ? "" : String(y))}
      >
        <SliderPrimitive.Track className="relative h-1.5 w-full grow overflow-hidden rounded-full bg-white/10">
          <SliderPrimitive.Range className="absolute h-full bg-gradient-to-r from-rose-500 to-rose-400" />
        </SliderPrimitive.Track>
        {[0, 1].map(i => (
          <SliderPrimitive.Thumb key={i} data-testid={`${testid}-thumb-${i}`} aria-label={`${label} ${i === 0 ? "min" : "max"}`}
            className="block h-5 w-5 rounded-full border-2 border-rose-400 bg-[#161320] shadow-[0_0_0_4px_rgba(244,63,94,0.15)] transition-[box-shadow,background-color] hover:bg-rose-500/30 focus-visible:outline-none focus-visible:shadow-[0_0_0_6px_rgba(244,63,94,0.3)] cursor-grab active:cursor-grabbing" />
        ))}
      </SliderPrimitive.Root>
    </div>
  );
}
