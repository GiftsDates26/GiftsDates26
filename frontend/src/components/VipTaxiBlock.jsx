import React, { useState } from "react";
import { Car, AlertTriangle, Loader2, Send } from "lucide-react";
import { toast } from "sonner";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { api } from "../lib/api";
import { useApp } from "../context/AppContext";
import { t } from "../lib/i18n";

const ERR = { TAXI_PENDING: "vt_err_pending", "Insufficient coins": "not_enough_coins" };

function TaxiRequestForm({ b, onDone, lang }) {
  const [coins, setCoins] = useState("");
  const [busy, setBusy] = useState(false);
  const send = async () => {
    const n = parseInt(coins, 10);
    if (!n || n < 1) { toast.error(t("vt_amount_err", lang)); return; }
    setBusy(true);
    try { await api.post(`/vip/schedule/bookings/${b.id}/taxi/request`, { coins: n }); toast.success(t("vt_requested_toast", lang)); setCoins(""); onDone?.(); }
    catch (e) { const d = e.response?.data?.detail || ""; toast.error(ERR[d] ? t(ERR[d], lang) : d || "Error"); }
    finally { setBusy(false); }
  };
  return (
    <div className="flex gap-2 mt-2" data-testid={`vs-taxi-form-${b.id}`}>
      <Input data-testid={`vs-taxi-coins-${b.id}`} type="number" min={1} value={coins} onChange={(e) => setCoins(e.target.value)} placeholder={t("vt_amount_ph", lang)} className="bg-white/5 border-white/10 h-9 font-mono-num" />
      <Button data-testid={`vs-taxi-request-${b.id}`} size="sm" disabled={busy} onClick={send} className="bg-amber-500 hover:bg-amber-400 text-black border-0 h-9 shrink-0">
        {busy ? <Loader2 size={14} className="animate-spin" /> : <><Car size={14} className="me-1" />{t("vt_request", lang)}</>}
      </Button>
    </div>
  );
}

function InviterTaxiActions({ b, onDone, lang }) {
  const { refreshUser } = useApp();
  const [busy, setBusy] = useState(false);
  const act = async (path, msg) => {
    setBusy(true);
    try { await api.post(`/vip/schedule/bookings/${b.id}/taxi/${path}`); toast.success(t(msg, lang)); await refreshUser(); onDone?.(); }
    catch (e) { const d = e.response?.data?.detail || ""; toast.error(ERR[d] ? t(ERR[d], lang) : d || "Error"); }
    finally { setBusy(false); }
  };
  return (
    <div className="flex gap-2 mt-2">
      <Button data-testid={`vs-taxi-send-${b.id}`} size="sm" disabled={busy} onClick={() => act("send", "vt_sent_toast")} className="bg-emerald-600 hover:bg-emerald-500 text-white border-0 h-9">
        {busy ? <Loader2 size={14} className="animate-spin" /> : <><Send size={14} className="me-1" />{t("vt_send", lang).replace("{c}", b.taxi.coins)}</>}
      </Button>
      <Button data-testid={`vs-taxi-decline-${b.id}`} size="sm" variant="outline" disabled={busy} onClick={() => act("decline", "vt_declined_toast")} className="bg-white/5 border-white/15 text-slate-300 hover:bg-white/10 h-9">{t("vb_decline", lang)}</Button>
    </div>
  );
}

export default function VipTaxiBlock({ b, who, onDone }) {
  const { lang } = useApp();
  const tx = b.taxi;
  const active = ["pending", "confirmed"].includes(b.status);
  if (!active && !tx) return null;
  const status = tx && (
    <div className="text-xs text-amber-200 flex items-center gap-1.5" data-testid={`vs-taxi-status-${b.id}`}>
      <Car size={13} /> {t(`vt_st_${tx.status}`, lang).replace("{c}", tx.coins)}
    </div>
  );
  return (
    <div className="w-full mt-3 rounded-xl border border-white/10 bg-white/[0.03] p-3 space-y-2" data-testid={`vs-taxi-${b.id}`}>
      {who === "incoming" && b.status === "pending" && (
        <div className="flex items-start gap-2 text-xs text-rose-200 bg-rose-500/10 border border-rose-500/30 rounded-lg p-2.5" data-testid={`vs-reject-warning-${b.id}`}>
          <AlertTriangle size={14} className="mt-0.5 shrink-0" />
          <span>{t("vt_reject_warning", lang).replace("{total}", b.coins)}</span>
        </div>
      )}
      {status}
      {who === "incoming" && active && (!tx || tx.status === "declined") && (
        <>
          <p className="text-xs text-slate-400" data-testid={`vs-taxi-note-${b.id}`}>{t("vt_note", lang)}</p>
          <TaxiRequestForm b={b} onDone={onDone} lang={lang} />
        </>
      )}
      {who === "outgoing" && active && tx?.status === "pending" && !["offered", "address_set"].includes(b.pickup?.status) && (
        <>
          <p className="text-xs text-slate-400">{t("vt_inviter_note", lang)}</p>
          <InviterTaxiActions b={b} onDone={onDone} lang={lang} />
        </>
      )}
    </div>
  );
}
