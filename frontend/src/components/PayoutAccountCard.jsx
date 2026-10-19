import React, { useState, useRef } from "react";
import { Landmark, ShieldCheck, Clock, XCircle, User, FileText, UploadCloud, Check } from "lucide-react";
import { toast } from "sonner";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { Label } from "./ui/label";
import { api } from "../lib/api";
import { useApp } from "../context/AppContext";
import { t } from "../lib/i18n";

const STATUS = {
  pending: { icon: Clock, cls: "bg-amber-500/15 border-amber-500/40 text-amber-300", key: "status_pending" },
  verified: { icon: ShieldCheck, cls: "bg-emerald-500/15 border-emerald-500/40 text-emerald-300", key: "status_verified" },
  rejected: { icon: XCircle, cls: "bg-rose-500/15 border-rose-500/40 text-rose-300", key: "status_rejected" },
};

const RECIPIENT = [["tax_id", "tax_id"], ["holder_name", "full_name"], ["recipient_street", "street"], ["recipient_city", "city"], ["recipient_province", "province"], ["recipient_postal_code", "postal_code"], ["country", "country"], ["recipient_email", "recipient_email"]];
const BANK = [["iban", "account_number"], ["swift", "swift_code"], ["routing_number", "routing_number"], ["bank_name", "bank_name"], ["bank_street", "bank_street"], ["bank_city", "bank_city"], ["bank_province", "bank_province"], ["bank_postal_code", "bank_postal_code"], ["bank_country", "bank_country"]];
const ALL = [...RECIPIENT, ...BANK].map(([k]) => k);
const OPTIONAL = new Set(["routing_number"]);
const DOCS = [["bank_statement_path", "bank_statement"], ["proof_of_address_path", "proof_of_address"]];

export default function PayoutAccountCard({ account, onSaved }) {
  const { lang, user } = useApp();
  const [edit, setEdit] = useState(!account);
  const [docsMode, setDocsMode] = useState(false);
  const [f, setF] = useState(Object.fromEntries([...ALL, ...DOCS.map(([k]) => k)].map(k => [k, account?.[k] || (k === "recipient_email" ? user?.email || "" : "")])));
  const [busy, setBusy] = useState(false);
  const [uploading, setUploading] = useState(null);
  const st = account && STATUS[account.status];
  const isVerified = user?.verified === true;

  const uploadDoc = async (kind, file) => {
    if (!file) return;
    setUploading(kind);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const { data } = await api.post(`/wallet/payout-document?kind=${kind === "bank_statement_path" ? "bank_statement" : "proof_of_address"}`, fd, { headers: { "Content-Type": "multipart/form-data" } });
      setF(prev => ({ ...prev, [kind]: data.path }));
      toast.success(t("uploaded", lang));
    } catch (e) { toast.error(e.response?.data?.detail || t("failed", lang)); }
    finally { setUploading(null); }
  };

  const submit = async () => {
    const missing = ALL.filter(k => !OPTIONAL.has(k) && !String(f[k] || "").trim());
    if (missing.length) { toast.error(t("fill_all", lang)); return; }
    if (!f.bank_statement_path || !f.proof_of_address_path) { toast.error(t("docs_required", lang)); return; }
    setBusy(true);
    try { await api.post("/wallet/payout-account", f); toast.success(t("status_pending", lang)); setEdit(false); setDocsMode(false); onSaved?.(); }
    catch (e) { toast.error(e.response?.data?.detail || t("failed", lang)); } finally { setBusy(false); }
  };

  const Field = ([k, label]) => (
    <div key={k}>
      <Label className="text-xs text-slate-400">{t(label, lang)}{OPTIONAL.has(k) ? "" : " *"}</Label>
      <Input data-testid={`payout-${k.replace(/_/g, "-")}-input`} type={k === "recipient_email" ? "email" : "text"} value={f[k]} onChange={e => setF({ ...f, [k]: e.target.value })} className={`bg-white/5 border-white/10 mt-1 h-9 ${["iban", "swift", "routing_number", "tax_id"].includes(k) ? "font-mono" : ""}`} />
    </div>
  );

  const renderDoc = ([k, label]) => (
    <DocUploadField
      key={k}
      fieldKey={k}
      label={label}
      done={!!f[k]}
      uploading={uploading === k}
      onPick={(file) => uploadDoc(k, file)}
      lang={lang}
    />
  );

  return (
    <div className="glass rounded-2xl p-5" data-testid="payout-account-card">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-emerald-500/15 border border-emerald-500/30 flex items-center justify-center"><Landmark className="text-emerald-300" /></div>
          <div>
            <div className="font-serif-luxe text-xl">{t("bank_account", lang)}</div>
            {account && !edit && <div className="text-xs text-slate-400">{account.holder_name} · {account.bank_name} · ····{account.iban.slice(-4)} · {account.swift}</div>}
          </div>
        </div>
        {st && !edit && !docsMode && (
          <div className="flex items-center gap-2">
            <span data-testid="payout-account-status" className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-full border text-xs ${st.cls}`}><st.icon size={12} /> {t(st.key, lang)}</span>
            {account.status !== "verified" && <Button data-testid="payout-account-edit-button" size="sm" variant="outline" onClick={() => setEdit(true)} className="bg-white/5 border-white/10">✎</Button>}
          </div>
        )}
      </div>
      {account?.status === "rejected" && account.reason && !edit && !docsMode && <div className="mt-2 text-xs text-rose-300" data-testid="payout-reject-reason">{account.reason}</div>}
      {account?.status === "rejected" && !edit && !docsMode && (
        <div className="mt-3 flex flex-wrap gap-2">
          <Button data-testid="payout-replace-docs-button" size="sm" onClick={() => { setF(prev => ({ ...prev, bank_statement_path: "", proof_of_address_path: "" })); setDocsMode(true); }} className="rose-btn text-white border-0 h-9"><FileText size={14} className="me-1" /> {t("replace_documents", lang)}</Button>
          <Button data-testid="payout-edit-all-button" size="sm" variant="outline" onClick={() => setEdit(true)} className="bg-white/5 border-white/10 h-9">{t("edit_all_details", lang)}</Button>
        </div>
      )}
      {docsMode && !edit && (
        <div className="mt-4 space-y-4" data-testid="payout-docs-only">
          <p className="text-xs text-slate-400">{t("replace_documents_hint", lang)}</p>
          <div className="text-xs text-slate-500">{account.holder_name} · {account.bank_name} · ····{account.iban.slice(-4)}</div>
          <div>
            <div className="text-xs uppercase tracking-widest text-slate-500 font-mono mb-2 flex items-center gap-1"><FileText size={12} /> {t("documents", lang)}</div>
            <div className="grid sm:grid-cols-2 gap-3">{DOCS.map(renderDoc)}</div>
          </div>
          <div className="flex gap-2">
            <Button data-testid="payout-docs-submit-button" disabled={busy} onClick={submit} className="rose-btn text-white border-0 h-10">{t("resubmit", lang)}</Button>
            <Button variant="ghost" onClick={() => setDocsMode(false)} className="text-slate-400">{t("cancel", lang)}</Button>
          </div>
        </div>
      )}
      {edit && (
        <div className="mt-4 space-y-5">
          <p className="text-xs text-slate-400" data-testid="payout-verification-intro">{t("verification_intro", lang)}</p>
          {!isVerified && (
            <div data-testid="payout-verify-badge-warning" className="flex items-start gap-2 text-xs text-amber-300 bg-amber-500/10 border border-amber-500/30 rounded-lg p-3">
              <ShieldCheck size={14} className="mt-0.5 shrink-0" /> {t("need_verified_badge", lang)}
            </div>
          )}
          <div>
            <div className="text-xs uppercase tracking-widest text-slate-500 font-mono mb-2 flex items-center gap-1"><User size={12} /> {t("recipient_details", lang)}</div>
            <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-3">{RECIPIENT.map(Field)}</div>
          </div>
          <div>
            <div className="text-xs uppercase tracking-widest text-slate-500 font-mono mb-2 flex items-center gap-1"><Landmark size={12} /> {t("bank_details", lang)}</div>
            <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-3">{BANK.map(Field)}</div>
          </div>
          <div>
            <div className="text-xs uppercase tracking-widest text-slate-500 font-mono mb-2 flex items-center gap-1"><FileText size={12} /> {t("documents", lang)}</div>
            <p className="text-xs text-slate-500 mb-2">{t("documents_hint", lang)}</p>
            <div className="grid sm:grid-cols-2 gap-3">{DOCS.map(renderDoc)}</div>
          </div>
          <div className="flex gap-2">
            <Button data-testid="payout-account-submit-button" disabled={busy} onClick={submit} className="rose-btn text-white border-0 h-10">{t("submit_verification", lang)}</Button>
            {account && <Button variant="ghost" onClick={() => setEdit(false)} className="text-slate-400">{t("cancel", lang)}</Button>}
          </div>
        </div>
      )}
    </div>
  );
}


// Standalone upload field so its useRef hook belongs to itself (not the parent),
// avoiding rules-of-hooks issues when the doc section mounts/unmounts.
function DocUploadField({ fieldKey, label, done, uploading, onPick, lang }) {
  const ref = useRef(null);
  const tid = fieldKey.replace(/_/g, "-");
  return (
    <div>
      <Label className="text-xs text-slate-400">{t(label, lang)} *</Label>
      <input ref={ref} data-testid={`payout-${tid}-input`} type="file" accept="image/*,application/pdf" className="hidden" onChange={e => onPick(e.target.files?.[0])} />
      <button
        type="button"
        data-testid={`payout-${tid}-upload`}
        onClick={() => ref.current?.click()}
        className={`mt-1 w-full inline-flex items-center justify-center gap-2 h-9 rounded-lg border text-sm transition-colors ${done ? "bg-emerald-500/10 border-emerald-500/40 text-emerald-300" : "bg-white/5 border-white/10 text-slate-300 hover:bg-white/10"}`}
      >
        {uploading ? <UploadCloud size={14} className="animate-pulse" /> : done ? <Check size={14} /> : <FileText size={14} />}
        {uploading ? t("uploading", lang) : done ? t("uploaded", lang) : t("upload_document", lang)}
      </button>
    </div>
  );
}