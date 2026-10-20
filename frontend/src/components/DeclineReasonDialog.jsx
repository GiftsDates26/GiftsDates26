import React, { useState } from "react";
import { Loader2, X } from "lucide-react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "./ui/dialog";
import { Button } from "./ui/button";
import { Textarea } from "./ui/textarea";
import { useApp } from "../context/AppContext";
import { t } from "../lib/i18n";

const QUICK = ["dr_busy", "dr_far", "dr_other_day", "dr_not_ready", "dr_personal"];

// Ask for a quick or typed reason before declining; the reason is sent to the inviter.
export default function DeclineReasonDialog({ open, onClose, onConfirm, warning, testid = "decline-dialog" }) {
  const { lang } = useApp();
  const [pick, setPick] = useState(null);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const reason = (text.trim() || (pick ? t(pick, lang) : "")).slice(0, 300);
  const close = () => { setPick(null); setText(""); onClose(); };
  const send = async () => { setBusy(true); try { await onConfirm(reason); close(); } finally { setBusy(false); } };
  return (
    <Dialog open={open} onOpenChange={(o) => !o && close()}>
      <DialogContent className="bg-[#14121a] border-white/10 text-white max-w-md" data-testid={testid}>
        <DialogHeader>
          <DialogTitle>{t("dr_title", lang)}</DialogTitle>
          <DialogDescription className="text-slate-400">{t("dr_sub", lang)}</DialogDescription>
        </DialogHeader>
        <div className="flex flex-wrap gap-2" data-testid={`${testid}-quick`}>
          {QUICK.map((k) => (
            <button key={k} type="button" onClick={() => { setPick(pick === k ? null : k); setText(""); }} data-testid={`${testid}-quick-${k}`}
              className={`rounded-full border px-3 py-1.5 text-xs transition-colors ${pick === k && !text ? "border-rose-400 bg-rose-500/20 text-rose-100" : "border-white/15 bg-white/5 text-slate-300 hover:bg-white/10"}`}>
              {t(k, lang)}
            </button>
          ))}
        </div>
        <Textarea value={text} onChange={(e) => setText(e.target.value)} maxLength={300} rows={3} placeholder={t("dr_type", lang)}
          className="bg-white/5 border-white/10" data-testid={`${testid}-text`} />
        {warning && <div className="text-[11px] text-amber-200/90 rounded-lg border border-amber-500/30 bg-amber-500/5 p-2" data-testid={`${testid}-warning`}>{warning}</div>}
        <div className="flex justify-end gap-2">
          <Button variant="outline" onClick={close} className="bg-white/5 border-white/15" data-testid={`${testid}-cancel`}>{t("dr_keep", lang)}</Button>
          <Button disabled={busy || !reason} onClick={send} className="bg-rose-600 hover:bg-rose-500 text-white border-0" data-testid={`${testid}-confirm`}>
            {busy ? <Loader2 size={14} className="animate-spin" /> : <><X size={14} className="me-1" />{t("dr_send", lang)}</>}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

export function DeclineNote({ reason, testid }) {
  const { lang } = useApp();
  if (!reason) return null;
  return (
    <div className="mt-1.5 inline-flex items-start gap-1.5 rounded-lg border border-rose-500/30 bg-rose-500/10 px-2.5 py-1.5 text-xs text-rose-100" data-testid={testid}>
      <X size={12} className="mt-0.5 shrink-0 text-rose-300" /><span><b className="text-rose-200">{t("dr_reason_label", lang)}:</b> “{reason}”</span>
    </div>
  );
}
