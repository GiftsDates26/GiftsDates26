import React, { useRef, useState } from "react";
import { ShieldAlert, ImagePlus, X, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { api, fileUrl } from "../lib/api";
import { useApp } from "../context/AppContext";
import { t } from "../lib/i18n";

const REASONS = [
  ["reason_no_show", "No-show"], ["reason_cancelled_last", "Cancelled last minute"], ["reason_misleading", "Misleading profile"],
  ["reason_rude", "Rude or disrespectful"], ["reason_uncomfortable", "Made me uncomfortable"], ["reason_harassment", "Harassment"],
  ["reason_money", "Asked for money"], ["reason_scam", "Suspicious / scam"], ["reason_unsafe", "Unsafe situation"], ["reason_other", "Other"],
];
const MAX_PHOTOS = 6;

export const DateStartedNote = ({ id }) => {
  const { lang } = useApp();
  return (
    <div className="w-full flex items-start gap-1.5 text-[11px] text-amber-200/90 rounded-lg border border-amber-500/30 bg-amber-500/5 p-2" data-testid={`date-started-note-${id}`}>
      <ShieldAlert size={13} className="mt-0.5 shrink-0 text-amber-300" />
      <span>{t("rp_started_note", lang)}</span>
    </div>
  );
};

export default function DateReportForm({ id, onSubmit, reply = false }) {
  const { lang } = useApp();
  const tr = (k) => t(k, lang);
  const [reasons, setReasons] = useState([]);
  const [details, setDetails] = useState("");
  const [evidence, setEvidence] = useState("");
  const [photos, setPhotos] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [busy, setBusy] = useState(false);
  const fileRef = useRef();

  const addPhotos = async (e) => {
    const files = [...(e.target.files || [])].slice(0, MAX_PHOTOS - photos.length);
    e.target.value = "";
    if (!files.length) return;
    setUploading(true);
    try {
      for (const f of files) {
        const fd = new FormData(); fd.append("file", f);
        const r = await api.post("/upload", fd, { headers: { "Content-Type": "multipart/form-data" } });
        setPhotos(p => [...p, r.data.path]);
      }
    } catch { toast.error(tr("upload_failed")); } finally { setUploading(false); }
  };

  const submit = async () => {
    if (details.trim().length < 10) { toast.error(tr("id_report_min")); return; }
    setBusy(true);
    try { await onSubmit(reply ? { details, photos } : { reasons, details, evidence, photos }); toast.success(tr(reply ? "rr_sent" : "id_report_submitted")); }
    catch (e) { const d = e.response?.data?.detail; toast.error(d === "ALREADY_REPORTED" ? tr("rp_already") : d === "ALREADY_REPLIED" ? tr("rr_already") : d || tr("failed")); }
    finally { setBusy(false); }
  };

  return (
    <div className="mt-3 rounded-lg border border-rose-500/30 bg-rose-500/5 p-3 space-y-2" data-testid={`${reply ? "reply" : "report"}-form-${id}`}>
      <div className="text-xs font-semibold text-rose-200 flex items-center gap-1"><ShieldAlert size={13} />{tr(reply ? "rr_title" : "id_report_title")}</div>
      {!reply && <div className="flex flex-wrap gap-1.5">{REASONS.map(([k, v]) => (
        <button key={k} type="button" onClick={() => setReasons(s => s.includes(v) ? s.filter(x => x !== v) : [...s, v])} data-testid={`report-reason-${k}-${id}`}
          className={`text-[11px] px-2 py-1 rounded-full border transition-colors ${reasons.includes(v) ? "bg-rose-500/20 border-rose-500/50 text-rose-200" : "bg-white/5 border-white/10 text-slate-400"}`}>{tr(k)}</button>))}</div>}
      <textarea data-testid={`report-details-${id}`} value={details} onChange={e => setDetails(e.target.value)} placeholder={tr(reply ? "rr_details_ph" : "id_report_details_ph")} className="w-full bg-white/5 border border-white/10 rounded-md p-2 text-sm text-slate-200 min-h-[70px]" />
      <div className="space-y-1.5" data-testid={`report-evidence-block-${id}`}>
        <div className="text-[11px] text-slate-300">{tr("rp_evidence")}</div>
        <div className="flex flex-wrap gap-2">
          {photos.map(p => (
            <div key={p} className="relative w-16 h-16" data-testid={`report-photo-${id}`}>
              <img src={fileUrl(p)} alt="" className="w-16 h-16 rounded-md object-cover border border-white/10" />
              <button type="button" onClick={() => setPhotos(s => s.filter(x => x !== p))} data-testid={`report-photo-remove-${id}`}
                className="absolute -top-1.5 -end-1.5 rounded-full bg-black/80 border border-white/20 p-0.5 text-slate-200"><X size={11} /></button>
            </div>
          ))}
          {photos.length < MAX_PHOTOS && (
            <button type="button" onClick={() => fileRef.current?.click()} disabled={uploading} data-testid={`report-photo-add-${id}`}
              className="w-16 h-16 rounded-md border border-dashed border-rose-400/40 bg-white/5 text-rose-200 flex flex-col items-center justify-center text-[10px] gap-0.5 hover:bg-white/10 transition-colors">
              {uploading ? <Loader2 size={16} className="animate-spin" /> : <ImagePlus size={16} />}{tr("rp_add_photo")}
            </button>
          )}
        </div>
        <input ref={fileRef} type="file" accept="image/*" multiple className="hidden" onChange={addPhotos} data-testid={`report-photo-input-${id}`} />
        {!reply && <Input data-testid={`report-evidence-${id}`} value={evidence} onChange={e => setEvidence(e.target.value)} placeholder={tr("id_report_evidence_ph")} className="bg-white/5 border-white/10 h-9" />}
      </div>
      <div className="text-[11px] text-slate-400" data-testid={`report-note-${id}`}>{tr(reply ? "rr_note" : "rp_note")}</div>
      <Button data-testid={`${reply ? "reply" : "report"}-submit-${id}`} disabled={busy || uploading} onClick={submit} className="rose-btn text-white border-0 h-9">{tr(reply ? "rr_submit" : "id_submit_report")}</Button>
    </div>
  );
}

export const ReportReplyBlock = ({ id, info, onSubmit }) => {
  const { lang } = useApp();
  const [open, setOpen] = useState(false);
  if (!info || info.by_me) return null;
  return (
    <div className="w-full rounded-lg border border-rose-500/30 bg-rose-500/5 p-3 space-y-2" data-testid={`reported-block-${id}`}>
      <div className="text-xs font-semibold text-rose-200 flex items-center gap-1"><ShieldAlert size={13} />{t("rr_you_were_reported", lang)}</div>
      <div className="text-[11px] text-slate-300">{(info.reasons || []).join(", ")}{info.details ? ` — "${info.details}"` : ""}</div>
      {info.replied ? <div className="text-[11px] text-emerald-300" data-testid={`reply-sent-${id}`}>{t("rr_sent", lang)}</div>
        : info.status === "open" && (open ? <DateReportForm id={id} reply onSubmit={async (p) => { await onSubmit(p); setOpen(false); }} />
          : <Button size="sm" onClick={() => setOpen(true)} data-testid={`reply-open-${id}`} className="rose-btn text-white border-0 h-8">{t("rr_open", lang)}</Button>)}
    </div>
  );
};
