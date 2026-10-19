import React, { useState } from "react";
import { Hourglass, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { Popover, PopoverContent, PopoverTrigger } from "./ui/popover";
import { Button } from "./ui/button";
import ExtraHoursStepper from "./ExtraHoursStepper";
import { api } from "../lib/api";
import { useApp } from "../context/AppContext";
import { t } from "../lib/i18n";

export default function ExtendDateButton({ url, price, id, onDone }) {
  const { lang, refreshUser } = useApp();
  const [hours, setHours] = useState(1);
  const [busy, setBusy] = useState(false);
  const [open, setOpen] = useState(false);
  const submit = async () => {
    setBusy(true);
    try {
      await api.post(url, { hours });
      toast.success(t("ext_done", lang));
      setOpen(false); setHours(1);
      await refreshUser(); onDone?.();
    } catch (e) {
      const d = e.response?.data?.detail || "";
      toast.error(d === "SLOT_TAKEN" ? t("bk_slot_taken", lang) : d === "Insufficient coins" ? t("not_enough_coins", lang) : d || "Error");
    } finally { setBusy(false); }
  };
  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger data-testid={`extend-date-${id}`}
        className="inline-flex items-center h-9 px-3 rounded-md text-sm bg-amber-500/10 border border-amber-500/40 text-amber-200 hover:bg-amber-500/20 transition-colors">
        <Hourglass size={14} className="me-1.5" />{t("ext_add", lang)}
      </PopoverTrigger>
      <PopoverContent className="bg-[#161320] border-white/10 text-white w-72 space-y-3" data-testid={`extend-date-panel-${id}`}>
        <p className="text-xs text-slate-400">{t("ext_note", lang)}</p>
        <ExtraHoursStepper label={t("bk_extra_hours", lang)} each={t("bk_each", lang)} value={hours} onChange={(n) => setHours(Math.max(1, n))} price={price} testid={`extend-hours-${id}`} />
        <Button data-testid={`extend-confirm-${id}`} disabled={busy} onClick={submit} className="rose-btn text-white border-0 w-full h-9">
          {busy ? <Loader2 size={14} className="animate-spin" /> : t("ext_confirm", lang).replace("{h}", hours).replace("{c}", hours * price)}
        </Button>
      </PopoverContent>
    </Popover>
  );
}
