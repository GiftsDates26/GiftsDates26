import React, { useEffect, useState } from "react";
import { TrendingUp, CalendarHeart, Crown, KeyRound, Gift } from "lucide-react";
import { api } from "../lib/api";
import { useApp } from "../context/AppContext";
import { t } from "../lib/i18n";
import EarningsChart from "./EarningsChart";

const PARTS = [
  ["regular", "te_regular", CalendarHeart, "text-rose-300"],
  ["vip", "te_vip", Crown, "text-amber-300"],
  ["unlocks", "te_unlocks", KeyRound, "text-violet-300"],
  ["gifts", "te_gifts", Gift, "text-pink-300"],
];

export default function TotalEarnings() {
  const { lang } = useApp();
  const [e, setE] = useState(null);
  useEffect(() => { api.get("/earnings/total").then(r => setE(r.data)).catch(() => {}); }, []);
  if (!e) return null;
  return (
    <div className="rounded-2xl border border-amber-500/30 bg-gradient-to-br from-amber-500/10 via-transparent to-rose-500/5 p-5 grid gap-5 md:grid-cols-[1.2fr_1fr_1fr]" data-testid="wallet-total-earnings">
      <div>
        <div className="flex items-center gap-2 text-[11px] uppercase tracking-wider text-amber-300/80"><TrendingUp size={14} />{t("te_title", lang)}</div>
        <div className="font-mono-num text-4xl text-amber-200 mt-2" data-testid="wallet-earnings-month">🪙 {e.earned.toLocaleString()}</div>
        <div className="text-xs text-slate-400 mt-1">{t("er_month", lang)}</div>
        <div className="text-[11px] text-slate-400 mt-3" data-testid="wallet-earnings-held">🔒 {e.held.toLocaleString()} · {t("er_held", lang)}</div>
        <div className="text-[11px] text-slate-500 mt-1" data-testid="wallet-earnings-6m">{t("te_six", lang)}: 🪙 {e.six_month_total.toLocaleString()}</div>
      </div>
      <div className="space-y-2" data-testid="wallet-earnings-breakdown">
        {PARTS.map(([k, label, Icon, tone]) => (
          <div key={k} className="flex items-center justify-between rounded-xl border border-white/10 bg-white/[0.03] px-3 py-2" data-testid={`wallet-earnings-${k}`}>
            <span className="flex items-center gap-2 text-xs text-slate-300"><Icon size={14} className={tone} />{t(label, lang)}</span>
            <span className="font-mono-num text-sm text-white">🪙 {(e.breakdown[k] || 0).toLocaleString()}</span>
          </div>
        ))}
      </div>
      <div className="self-end"><EarningsChart data={e.by_month} /></div>
    </div>
  );
}
