import React, { useEffect, useState } from "react";
import { Timer, Hourglass } from "lucide-react";
import { useApp } from "../context/AppContext";
import { t } from "../lib/i18n";

const SLOT_MS = 150 * 60000;
const BUF_MS = 15 * 60000;
const pad = (n) => String(n).padStart(2, "0");
const clock = (ms) => { const s = Math.floor(Math.abs(ms) / 1000); return `${pad(Math.floor(s / 3600))}:${pad(Math.floor((s % 3600) / 60))}:${pad(s % 60)}`; };
const long = (ms) => {
  const s = Math.floor(ms / 1000), d = Math.floor(s / 86400), h = Math.floor((s % 86400) / 3600), m = Math.floor((s % 3600) / 60);
  return d > 0 ? `${d}d ${h}h ${pad(m)}m` : clock(ms);
};
const RED = "bg-red-500/20 border-red-500/60 text-red-100";

export default function CountdownBadge({ to, testid }) {
  const { lang } = useApp();
  const [now, setNow] = useState(Date.now());
  useEffect(() => { const id = setInterval(() => setNow(Date.now()), 1000); return () => clearInterval(id); }, []);
  const start = new Date(to).getTime();
  if (!to || isNaN(start)) return null;
  const end = start + SLOT_MS;
  const badge = (cls, icon, text, phase) => (
    <span data-testid={testid} data-phase={phase} title={new Date(to).toLocaleString()}
      className={`inline-flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-full border font-mono-num ${cls}`}>{icon}{text}</span>
  );
  if (now >= end + BUF_MS) return null;
  // 15-min buffer after the date: red countdown
  if (now >= end) return badge(RED, <Hourglass size={12} className="animate-pulse" />, `${t("cd_after", lang)} ${clock(end + BUF_MS - now)}`, "after");
  // during the date: yellow clock counting forward
  if (now >= start) return badge("bg-yellow-400/15 border-yellow-400/60 text-yellow-200", <Timer size={12} />, `${t("cd_in_progress", lang)} ${clock(now - start)}`, "during");
  // last 15 min before the start: red countdown
  if (start - now <= BUF_MS) return badge(RED, <Timer size={12} className="animate-pulse" />, `${t("cd_starts_in", lang)} ${clock(start - now)}`, "soon");
  return badge("bg-amber-500/10 border-amber-500/30 text-amber-200", <Timer size={12} />, `${t("cd_starts_in", lang)} ${long(start - now)}`, "upcoming");
}
