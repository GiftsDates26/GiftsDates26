import React from "react";
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from "./ui/alert-dialog";
import { useApp } from "../context/AppContext";
import { t } from "../lib/i18n";

// byRequester: the person who sent/paid cancels -> 50% back, 25% other side, 25% fee; otherwise full refund.
export const cancelSplit = (total, byRequester, taxi = 0) => {
  if (!byRequester) return { refund: total, comp: 0, fee: 0 };
  const base = total - taxi, refund = Math.round(base * 0.5), comp = Math.round(base * 0.25);
  return { refund: refund + taxi, comp, fee: base - refund - comp };
};

const Row = ({ label, value, strong, testid }) => (
  <div className="flex justify-between text-sm" data-testid={testid}>
    <span className={strong ? "text-white font-semibold" : "text-slate-400"}>{label}</span>
    <span className={`font-mono-num ${strong ? "text-emerald-300 font-semibold" : "text-slate-200"}`}>🪙 {value}</span>
  </div>
);

export default function CancelPreviewDialog({ open, onOpenChange, total = 0, taxi = 0, byRequester, onConfirm, split }) {
  const { lang } = useApp();
  const { refund, comp, fee } = split || cancelSplit(total, byRequester, taxi);
  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent className="bg-[#161320] border-white/10 text-white max-w-sm" data-testid="cancel-preview-dialog">
        <AlertDialogHeader>
          <AlertDialogTitle className="font-serif-luxe text-2xl">{t("cp_title", lang)}</AlertDialogTitle>
          <AlertDialogDescription className="text-xs text-slate-400">{t(byRequester ? "cp_partial_note" : "cp_full_note", lang)}</AlertDialogDescription>
        </AlertDialogHeader>
        <div className="rounded-xl border border-white/10 bg-white/[0.03] p-3 space-y-1.5">
          <Row label={t("cp_paid", lang)} value={total} testid="cancel-preview-paid" />
          {taxi > 0 && <Row label={`🚕 ${t("cp_taxi_full", lang)}`} value={taxi} testid="cancel-preview-taxi" />}
          {taxi > 0 && byRequester && <Row label={t("cp_date_back", lang)} value={refund - taxi} testid="cancel-preview-date-back" />}
          <Row label={t(byRequester ? "cp_you_get" : "cp_client_gets", lang)} value={refund} strong testid="cancel-preview-refund" />
          {byRequester && <Row label={t("cp_other_gets", lang)} value={comp} testid="cancel-preview-comp" />}
          {byRequester && <Row label={t("cp_fee", lang)} value={fee} testid="cancel-preview-fee" />}
        </div>
        <AlertDialogFooter>
          <AlertDialogCancel data-testid="cancel-preview-keep" className="bg-white/5 border-white/10 text-slate-200 hover:bg-white/10 hover:text-white">{t("cp_keep", lang)}</AlertDialogCancel>
          <AlertDialogAction data-testid="cancel-preview-confirm" onClick={onConfirm} className="bg-rose-600 hover:bg-rose-500 text-white">{t("cp_confirm", lang)}</AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
