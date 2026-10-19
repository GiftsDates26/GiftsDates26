import React, { useState } from "react";
import { Timer, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { Popover, PopoverContent, PopoverTrigger } from "./ui/popover";
import { api } from "../lib/api";
import { useApp } from "../context/AppContext";
import { t } from "../lib/i18n";

const MINUTES = [5, 10, 15, 20, 30, 45, 60];

export default function RunningLateButton({ b, onDone }) {
  const { lang, user } = useApp();
  const isVip = user?.id === b.vip_id;
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(null);
  const send = async (m) => {
    setBusy(m);
    try { await api.post(`/vip/schedule/bookings/${b.id}/late`, { minutes: m }); toast.success(t(isVip ? "lt_sent_toast" : "lt_sent_toast_vip", lang)); setOpen(false); onDone?.(); }
    catch (e) { toast.error(e.response?.data?.detail === "NOT_DATE_TIME" ? t("lt_window_err", lang) : e.response?.data?.detail || "Error"); }
    finally { setBusy(null); }
  };
  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger data-testid={`vs-late-${b.id}`}
        className="inline-flex items-center h-9 px-3 rounded-md text-sm bg-amber-500/10 border border-amber-500/40 text-amber-200 hover:bg-amber-500/20 transition-colors">
        <Timer size={14} className="me-1.5" />{t("lt_btn", lang)}
      </PopoverTrigger>
      <PopoverContent className="bg-[#161320] border-white/10 text-white w-64" data-testid={`vs-late-panel-${b.id}`}>
        <p className="text-xs text-slate-400 mb-2.5">{t(isVip ? "lt_title" : "lt_title_client", lang)}</p>
        <div className="grid grid-cols-4 gap-1.5">
          {MINUTES.map((m) => (
            <button key={m} type="button" disabled={!!busy} onClick={() => send(m)} data-testid={`vs-late-${b.id}-${m}`}
              className="h-9 rounded-lg border border-white/10 bg-white/5 hover:bg-amber-500/20 hover:border-amber-500/40 text-sm font-mono-num transition-colors disabled:opacity-50">
              {busy === m ? <Loader2 size={13} className="animate-spin mx-auto" /> : `${m}′`}
            </button>
          ))}
        </div>
      </PopoverContent>
    </Popover>
  );
}
