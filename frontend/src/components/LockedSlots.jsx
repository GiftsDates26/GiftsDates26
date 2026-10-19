import React, { useEffect, useState } from "react";
import { Lock, LockOpen, Crown, ChevronDown } from "lucide-react";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import { Button } from "./ui/button";
import { api } from "../lib/api";
import { useApp } from "../context/AppContext";
import { t } from "../lib/i18n";
import { fromKey } from "../lib/availability";

export default function LockedSlots() {
  const { lang } = useApp();
  const [data, setData] = useState({ items: [], can_unlock: false });
  const [busy, setBusy] = useState(null);
  const [open, setOpen] = useState(false);
  const load = () => api.get("/me/locked-slots").then(r => setData(r.data)).catch(() => {});
  useEffect(() => { load(); }, []);

  const unlock = async (it) => {
    if (!window.confirm(t("ls_confirm", lang).replace("{w}", `${it.day} ${it.from}–${it.to}`))) return;
    setBusy(`${it.day}|${it.from}`);
    try { await api.post("/me/locked-slots/unlock", { day: it.day, time: it.from }); toast.success(t("ls_unlocked", lang)); await load(); }
    catch (e) { toast.error(e.response?.data?.detail === "PREMIUM_REQUIRED" ? t("ls_premium_only", lang) : t("failed", lang)); }
    finally { setBusy(null); }
  };

  const unlockAll = async () => {
    if (!window.confirm(t("ls_confirm_all", lang).replace("{n}", data.items.length))) return;
    setBusy("all");
    try { const r = await api.post("/me/locked-slots/unlock-all"); toast.success(t("ls_unlocked_all", lang).replace("{n}", r.data.count)); await load(); }
    catch (e) { toast.error(e.response?.data?.detail === "PREMIUM_REQUIRED" ? t("ls_premium_only", lang) : t("failed", lang)); }
    finally { setBusy(null); }
  };

  if (!data.items.length) return null;
  return (
    <div className="glass rounded-2xl" data-testid="locked-slots">
      <button type="button" onClick={() => setOpen(o => !o)} aria-expanded={open} data-testid="locked-slots-toggle"
        className="w-full flex items-center gap-2 p-5 text-left">
        <Lock size={18} className="text-slate-300" />
        <span className="font-serif-luxe text-xl">{t("ls_title", lang)}</span>
        <span className="text-[11px] font-mono-num px-2 py-0.5 rounded-full bg-white/10 text-slate-300" data-testid="locked-slots-count">{data.items.length}</span>
        <ChevronDown size={18} className={`ms-auto text-slate-400 transition-transform duration-200 ${open ? "rotate-180" : ""}`} />
      </button>
      {open && <div className="px-5 pb-5 -mt-2" data-testid="locked-slots-panel">
      <div className="flex flex-wrap items-start gap-3 mb-3">
        <p className="text-xs text-slate-400 flex-1 min-w-[200px]">{t("ls_sub", lang)}</p>
        {data.items.length > 1 && (
          <Button size="sm" disabled={!data.can_unlock || !!busy} onClick={unlockAll} data-testid="unlock-all-slots"
            className="h-8 bg-emerald-500 hover:bg-emerald-400 text-white border-0 disabled:opacity-40">
            <LockOpen size={13} className="me-1" />{t("ls_unlock_all", lang).replace("{n}", data.items.length)}
          </Button>
        )}
      </div>
      {!data.can_unlock && (
        <div className="flex flex-wrap items-center gap-2 text-xs rounded-lg border border-amber-500/30 bg-amber-500/5 p-2.5 mb-3 text-amber-100" data-testid="locked-slots-upsell">
          <Crown size={13} className="text-amber-300" />{t("ls_premium_only", lang)}
          <Link to="/wallet?premium=1" data-testid="locked-slots-upgrade" className="ms-auto text-amber-300 underline underline-offset-2">{t("buy_premium", lang)}</Link>
        </div>
      )}
      <div className="divide-y divide-white/5 rounded-xl border border-white/10">
        {data.items.map(it => {
          const key = `${it.day}|${it.from}`;
          return (
            <div key={key} className="flex items-center gap-2 sm:gap-3 px-2 sm:px-3 py-2 text-sm min-w-0" data-testid={`locked-slot-${it.day}-${it.from.replace(":", "")}`}>
              <span className="w-24 sm:w-28 shrink-0 text-slate-200">{fromKey(it.day).toLocaleDateString(lang, { weekday: "short", day: "numeric", month: "short" })}</span>
              <span className="font-mono-num text-slate-400 text-xs whitespace-nowrap"><Lock size={10} className="inline me-1 -mt-0.5" />{it.from}–{it.to}</span>
              <Button size="sm" variant="outline" disabled={!data.can_unlock || busy === key || busy === "all"} onClick={() => unlock(it)} data-testid={`unlock-slot-${it.day}-${it.from.replace(":", "")}`}
                className="ms-auto shrink-0 h-8 px-2 sm:px-3 bg-emerald-500/10 border-emerald-500/40 text-emerald-200 hover:bg-emerald-500/20 disabled:opacity-40">
                <LockOpen size={13} className="me-1" />{t("ls_unlock", lang)}
              </Button>
            </div>
          );
        })}
      </div>
      </div>}
    </div>
  );
}
