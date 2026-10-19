import React, { useState } from "react";
import { minHm } from "../lib/availability";

const C = 120, R_OUT = 98, R_IN = 64;
const pos = (i, r) => { const a = (i / 12) * 2 * Math.PI - Math.PI / 2; return [C + r * Math.cos(a), C + r * Math.sin(a)]; };
const startFor = (starts, hm) => starts.find(s => s % 1440 === hm);

function Dot({ x, y, label, on, active, onClick, testid, small }) {
  return (
    <g onClick={on ? onClick : undefined} className={on ? "cursor-pointer" : "cursor-not-allowed"} data-testid={testid}>
      <circle cx={x} cy={y} r={small ? 13 : 16} className={`transition-colors ${active ? "fill-rose-500" : on ? "fill-white/5 hover:fill-white/15" : "fill-transparent"}`} />
      <text x={x} y={y} dy="0.35em" textAnchor="middle" className={`select-none font-mono-num ${small ? "text-[10px]" : "text-[12px]"} ${active ? "fill-white" : on ? "fill-slate-100" : "fill-slate-600"}`}>{label}</text>
    </g>
  );
}

export default function ClockTimePicker({ starts = [], value, onChange }) {
  const [mode, setMode] = useState("h");
  const hm = value == null ? null : value % 1440;
  const selH = hm == null ? null : Math.floor(hm / 60);
  const hourOn = (h) => starts.some(s => Math.floor((s % 1440) / 60) === h);
  const pickHour = (h) => {
    const keep = hm != null && startFor(starts, h * 60 + (hm % 60));
    onChange(keep ?? starts.find(s => Math.floor((s % 1440) / 60) === h)); setMode("m");
  };
  const hand = hm == null ? null : mode === "h" ? pos(selH % 12, selH < 12 ? R_OUT : R_IN) : pos((hm % 60) / 5, R_OUT);
  const tab = (m, txt) => (
    <button type="button" onClick={() => setMode(m)} data-testid={`clock-mode-${m}`}
      className={`px-1.5 rounded-md transition-colors ${mode === m ? "bg-rose-500/20 text-rose-200" : "text-slate-300 hover:text-white"}`}>{txt}</button>
  );
  return (
    <div className="flex flex-col items-center" data-testid="clock-time-picker">
      <div className="text-3xl font-mono-num mb-2 flex items-center" data-testid="clock-display">
        {tab("h", hm == null ? "--" : minHm(hm).slice(0, 2))}<span className="text-slate-500">:</span>{tab("m", hm == null ? "--" : minHm(hm).slice(3))}
      </div>
      <svg viewBox="0 0 240 240" className="w-56 h-56">
        <circle cx={C} cy={C} r={116} className="fill-white/[0.03] stroke-white/10" />
        {hand && <line x1={C} y1={C} x2={hand[0]} y2={hand[1]} className="stroke-rose-400/70" strokeWidth="2" />}
        <circle cx={C} cy={C} r={3} className="fill-rose-400" />
        {mode === "h"
          ? Array.from({ length: 24 }, (_, h) => { const [x, y] = pos(h % 12, h < 12 ? R_OUT : R_IN);
              return <Dot key={h} x={x} y={y} small={h >= 12} label={String(h).padStart(2, "0")} on={hourOn(h)} active={selH === h} onClick={() => pickHour(h)} testid={`clock-hour-${h}`} />; })
          : [0, 15, 30, 45].map(m => { const [x, y] = pos(m / 5, R_OUT); const s = selH == null ? undefined : startFor(starts, selH * 60 + m);
              return <Dot key={m} x={x} y={y} label={String(m).padStart(2, "0")} on={s != null} active={hm != null && hm % 60 === m} onClick={() => onChange(s)} testid={`clock-minute-${m}`} />; })}
      </svg>
    </div>
  );
}
