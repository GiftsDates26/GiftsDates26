import React, { useState } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "./ui/dialog";
import { Button } from "./ui/button";
import { Coffee, Trash2, Loader2 } from "lucide-react";
import { api } from "../lib/api";
import { useApp } from "../context/AppContext";
import { t } from "../lib/i18n";
import { toast } from "sonner";
import { useNavigate } from "react-router-dom";

export default function DeleteAccountModal({ open, onOpenChange }) {
  const { lang, logout, refreshUser } = useApp();
  const nav = useNavigate();
  const [busy, setBusy] = useState("");

  const takeBreak = async () => {
    setBusy("break");
    try {
      await api.post("/account/pause");
      toast.success(t("break_taken_toast", lang));
      onOpenChange(false);
      logout();
      nav("/");
    } catch (e) {
      toast.error(e.response?.data?.detail || t("failed", lang));
    } finally { setBusy(""); }
  };

  const proceedDeletion = async () => {
    setBusy("delete");
    try {
      await api.post("/account/delete-request");
      toast.success(t("deletion_scheduled_toast", lang));
      onOpenChange(false);
      logout();
      nav("/");
    } catch (e) {
      toast.error(e.response?.data?.detail || t("failed", lang));
    } finally { setBusy(""); }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="bg-[#161320] border-white/10 text-white max-w-md" data-testid="delete-account-dialog">
        <DialogHeader>
          <DialogTitle className="font-serif-luxe text-2xl text-rose-300 flex items-center gap-2">
            <Trash2 size={20} /> {t("delete_modal_title", lang)}
          </DialogTitle>
        </DialogHeader>
        <p className="text-sm text-slate-300 leading-relaxed" data-testid="delete-modal-message">
          {t("delete_modal_msg", lang)}
        </p>
        <div className="mt-4 space-y-2.5">
          <Button data-testid="modal-take-break" onClick={takeBreak} disabled={!!busy}
            className="w-full h-11 rose-btn text-white border-0">
            {busy === "break" ? <Loader2 size={16} className="animate-spin" /> : <><Coffee size={16} className="me-1.5" /> {t("take_break", lang)}</>}
          </Button>
          <Button data-testid="modal-proceed-deletion" onClick={proceedDeletion} disabled={!!busy}
            variant="outline" className="w-full h-11 bg-rose-500/10 border-rose-500/40 text-rose-300 hover:bg-rose-500/20">
            {busy === "delete" ? <Loader2 size={16} className="animate-spin" /> : <><Trash2 size={16} className="me-1.5" /> {t("proceed_deletion", lang)}</>}
          </Button>
          <Button data-testid="modal-cancel" onClick={() => onOpenChange(false)} disabled={!!busy}
            variant="ghost" className="w-full h-10 text-slate-400 hover:text-white hover:bg-white/5">
            {t("cancel", lang)}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
