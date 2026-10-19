import React, { useEffect, useState } from "react";
import { XCircle, Coins, Loader2 } from "lucide-react";
import { api } from "../lib/api";
import { useApp } from "../context/AppContext";
import { t } from "../lib/i18n";

export default function CancelledDates() {
  const { lang } = useApp();
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    api.get("/invites/cancelled")
      .then((r) => { if (alive) setItems(r.data.items || []); })
      .catch(() => { if (alive) setItems([]); })
      .finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, []);

  const statusLabel = (s) => {
    const l = t(`ds_${s}`, lang);
    return l === `ds_${s}` ? s : l;
  };

  if (!loading && items.length === 0) return null;
  return (
    <div className="glass rounded-2xl p-6 mt-6 space-y-4" data-testid="profile-cancelled-dates">
      <h3 className="font-serif-luxe text-xl gold-text flex items-center gap-2">
        <XCircle size={18} className="text-rose-300" /> {t("cancelled_dates_title", lang)}
      </h3>

      {loading ? (
        <div className="flex items-center gap-2 text-slate-400 text-sm py-4"><Loader2 size={16} className="animate-spin" /> …</div>
      ) : items.length === 0 ? (
        <p className="text-sm text-slate-400" data-testid="cancelled-dates-empty">{t("cancelled_dates_empty", lang)}</p>
      ) : (
        <div className="space-y-2">
          {items.map((d) => (
            <div key={d.id} data-testid={`cancelled-date-${d.id}`}
              className="flex items-center justify-between gap-3 rounded-xl border border-white/10 bg-white/5 p-3">
              <div className="min-w-0">
                <div className="text-sm text-slate-100 truncate">
                  {t(d.role === "inviter" ? "cd_role_inviter" : "cd_role_recipient", lang)}{" "}
                  <span className="text-rose-200">{d.other?.name || "…"}</span>
                </div>
                <div className="mt-0.5 flex flex-wrap items-center gap-x-2 gap-y-0.5 text-[11px] text-slate-400">
                  <span className="inline-flex items-center gap-1 rounded-full border border-rose-500/40 bg-rose-500/10 px-2 py-0.5 text-rose-300">
                    {statusLabel(d.status)}
                  </span>
                  {d.proposed_start && <span>{new Date(d.proposed_start).toLocaleDateString()}</span>}
                  {typeof d.total_hold === "number" && (
                    <span className="inline-flex items-center gap-0.5"><Coins size={11} className="text-amber-300" />{d.total_hold}</span>
                  )}
                </div>
              </div>
              {d.refund_amount > 0 && (
                <div className="text-right shrink-0" data-testid={`cancelled-date-refund-${d.id}`}>
                  <div className="text-[10px] uppercase tracking-wide text-emerald-400/80">{t("cd_refunded_to_you", lang)}</div>
                  <div className="inline-flex items-center gap-1 text-sm font-semibold text-emerald-300"><Coins size={12} />+{d.refund_amount}</div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
