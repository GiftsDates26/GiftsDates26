import React, { useEffect, useState } from "react";
import { api } from "../lib/api";
import { useApp } from "../context/AppContext";
import { t } from "../lib/i18n";
import EarningsChart from "./EarningsChart";

export default function DatesEarnings() {
  const { lang } = useApp();
  const [e, setE] = useState(null);
  useEffect(() => { api.get("/dates/earnings").then(r => setE(r.data)).catch(() => {}); }, []);
  if (!e) return null;
  return (
    <div className="rounded-2xl border border-amber-500/30 bg-gradient-to-br from-amber-500/10 to-transparent px-4 py-3" data-testid="dates-earnings-tile">
      <div className="text-[10px] uppercase tracking-wider text-amber-300/80">{t("er_month", lang)}</div>
      <div className="font-mono-num text-2xl leading-tight text-amber-200 mt-0.5" data-testid="dates-earnings-month">🪙 {e.earned.toLocaleString()}</div>
      <div className="text-[11px] text-slate-400 mt-1" data-testid="dates-earnings-held">🔒 {e.held.toLocaleString()} · {t("er_held", lang)}</div>
      {e.by_month?.length > 0 && <EarningsChart data={e.by_month} />}
    </div>
  );
}
