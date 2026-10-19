import React, { useState } from "react";
import { Button } from "./ui/button";
import { RotateCcw, AlertTriangle, Loader2 } from "lucide-react";
import { api } from "../lib/api";
import { useApp } from "../context/AppContext";
import { t } from "../lib/i18n";
import { toast } from "sonner";

export default function RestoreAccountBanner() {
  const { user, refreshUser, lang } = useApp();
  const [busy, setBusy] = useState(false);

  if (!user || user.account_status !== "PENDING_DELETION") return null;

  const when = user.deletion_scheduled_at ? new Date(user.deletion_scheduled_at).toLocaleDateString() : "—";

  const restore = async () => {
    setBusy(true);
    try {
      await api.post("/account/restore");
      await refreshUser();
      toast.success(t("account_restored_toast", lang));
    } catch (e) {
      toast.error(e.response?.data?.detail || t("failed", lang));
    } finally { setBusy(false); }
  };

  return (
    <div data-testid="restore-account-banner"
      className="sticky top-16 z-40 bg-rose-950/70 backdrop-blur border-b border-rose-500/40">
      <div className="max-w-7xl mx-auto px-4 py-2.5 flex items-center justify-between gap-3 flex-wrap">
        <div className="flex items-center gap-2 text-sm text-rose-100">
          <AlertTriangle size={16} className="text-rose-300 shrink-0" />
          <span>{t("restore_banner_msg", lang).replace("{d}", when)}</span>
        </div>
        <Button data-testid="restore-account-btn" onClick={restore} disabled={busy}
          className="h-9 rose-btn text-white border-0 shrink-0">
          {busy ? <Loader2 size={15} className="animate-spin" /> : <><RotateCcw size={15} className="me-1.5" /> {t("restore_account", lang)}</>}
        </Button>
      </div>
    </div>
  );
}
