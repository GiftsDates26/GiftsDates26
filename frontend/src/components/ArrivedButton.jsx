import React, { useState } from "react";
import { MapPinned, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { api } from "../lib/api";
import { useApp } from "../context/AppContext";
import { t } from "../lib/i18n";

export default function ArrivedButton({ b, onDone }) {
  const { lang } = useApp();
  const [busy, setBusy] = useState(false);
  const go = async () => {
    setBusy(true);
    try { await api.post(`/vip/schedule/bookings/${b.id}/arrived`); toast.success(t("ar_done_toast", lang)); onDone?.(); }
    catch (e) { toast.error(e.response?.data?.detail === "NOT_DATE_TIME" ? t("ar_too_early", lang) : e.response?.data?.detail || "Error"); }
    finally { setBusy(false); }
  };
  return (
    <button type="button" data-testid={`vs-arrived-${b.id}`} disabled={busy} onClick={go}
      className="inline-flex items-center h-9 px-3 rounded-md text-sm font-semibold bg-emerald-500 hover:bg-emerald-400 text-black transition-colors disabled:opacity-60">
      {busy ? <Loader2 size={14} className="animate-spin" /> : <><MapPinned size={14} className="me-1.5" />{t("ar_btn", lang)}</>}
    </button>
  );
}
