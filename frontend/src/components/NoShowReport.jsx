import React, { useState } from "react";
import { Loader2, Camera, X } from "lucide-react";
import { toast } from "sonner";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "./ui/dialog";
import { Button } from "./ui/button";
import { Textarea } from "./ui/textarea";
import { api } from "../lib/api";
import { useApp } from "../context/AppContext";
import { t } from "../lib/i18n";

const ERR = { EVIDENCE_REQUIRED: "ns_evidence_err", IMAGE_ONLY: "ns_image_err", FILE_TOO_LARGE: "ns_size_err", NO_SHOW_WINDOW: "ns_window_err" };

export default function NoShowReport({ b, onDone }) {
  const { lang, refreshUser } = useApp();
  const [open, setOpen] = useState(false);
  const [note, setNote] = useState("");
  const [file, setFile] = useState(null);
  const [busy, setBusy] = useState(false);
  const submit = async () => {
    if (!note.trim() && !file) { toast.error(t("ns_evidence_err", lang)); return; }
    const fd = new FormData();
    fd.append("note", note.trim());
    if (file) fd.append("photo", file);
    setBusy(true);
    try {
      await api.post(`/vip/schedule/bookings/${b.id}/no-show`, fd, { headers: { "Content-Type": "multipart/form-data" } });
      toast.success(t("ns_done", lang)); setOpen(false); await refreshUser(); onDone?.();
    } catch (e) { const d = e.response?.data?.detail || ""; toast.error(ERR[d] ? t(ERR[d], lang) : d || "Error"); }
    finally { setBusy(false); }
  };
  return (
    <>
      <Button data-testid={`vs-no-show-${b.id}`} size="sm" variant="outline" onClick={() => setOpen(true)} className="bg-white/5 border-rose-500/40 text-rose-300 hover:bg-rose-500/10 h-9">{t("ns_btn", lang)}</Button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="bg-[#161320] border-white/10 text-white max-w-md" data-testid={`vs-no-show-dialog-${b.id}`}>
          <DialogHeader>
            <DialogTitle className="font-serif-luxe text-2xl">{t("ns_btn", lang)}</DialogTitle>
            <DialogDescription className="text-xs text-slate-400">{t("ns_confirm", lang).replace("{c}", b.coins)}</DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            <div>
              <label className="text-xs text-slate-400">{t("ns_note_label", lang)}</label>
              <Textarea data-testid={`vs-no-show-note-${b.id}`} value={note} onChange={(e) => setNote(e.target.value)} maxLength={1000} rows={3}
                placeholder={t("ns_note_ph", lang)} className="bg-white/5 border-white/10 mt-1" />
            </div>
            <div>
              <label className="text-xs text-slate-400">{t("ns_photo_label", lang)}</label>
              {file ? (
                <div className="mt-1 flex items-center gap-3 rounded-lg border border-white/10 bg-white/5 p-2" data-testid={`vs-no-show-file-${b.id}`}>
                  <img src={URL.createObjectURL(file)} alt="" className="h-14 w-14 rounded-md object-cover" />
                  <span className="text-xs text-slate-300 truncate flex-1">{file.name}</span>
                  <button type="button" onClick={() => setFile(null)} className="text-slate-400 hover:text-white" data-testid={`vs-no-show-file-remove-${b.id}`}><X size={14} /></button>
                </div>
              ) : (
                <label className="mt-1 flex items-center justify-center gap-2 h-16 rounded-lg border border-dashed border-white/15 bg-white/[0.03] text-xs text-slate-400 hover:bg-white/[0.06] cursor-pointer transition-colors">
                  <Camera size={15} /> {t("ns_photo_add", lang)}
                  <input type="file" accept="image/*" className="hidden" data-testid={`vs-no-show-photo-${b.id}`} onChange={(e) => setFile(e.target.files?.[0] || null)} />
                </label>
              )}
            </div>
            <p className="text-[11px] text-slate-500">{t("ns_review_note", lang)}</p>
            <Button data-testid={`vs-no-show-submit-${b.id}`} disabled={busy} onClick={submit} className="w-full h-10 bg-rose-600 hover:bg-rose-500 text-white border-0">
              {busy ? <Loader2 size={15} className="animate-spin" /> : t("ns_submit", lang)}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}
