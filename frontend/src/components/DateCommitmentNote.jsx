import React from "react";
import { Link } from "react-router-dom";
import { ShieldCheck } from "lucide-react";
import { useApp } from "../context/AppContext";
import { t } from "../lib/i18n";

export default function DateCommitmentNote({ testid = "date-commitment-note", checked, onCheckedChange }) {
  const { lang } = useApp();
  const link = (to, key) => (
    <Link key={key} to={to} target="_blank" className="text-rose-300 underline underline-offset-2 hover:text-rose-200" data-testid={`${testid}-${key}`}>{t(`commit_${key}`, lang)}</Link>
  );
  const parts = t("commit_body", lang).split(/(\{terms\}|\{privacy\})/);
  return (
    <div className="rounded-xl border border-white/10 bg-white/[0.03] p-3 text-[11px] leading-relaxed text-slate-400" data-testid={testid}>
      <div className="flex items-center gap-1.5 text-xs font-semibold text-slate-200 mb-1">
        <ShieldCheck size={13} className="text-emerald-300" /> {t("commit_title", lang)}
      </div>
      <p>{parts.map((p, i) => p === "{terms}" ? <React.Fragment key={i}>{link("/terms-of-use", "terms")}</React.Fragment> : p === "{privacy}" ? <React.Fragment key={i}>{link("/privacy", "privacy")}</React.Fragment> : p)}</p>
      {onCheckedChange && (
        <label className={`mt-2.5 flex items-start gap-2 cursor-pointer rounded-lg border px-2.5 py-2 transition-colors ${checked ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-100" : "border-amber-500/40 bg-amber-500/5 text-slate-200"}`}>
          <input type="checkbox" data-testid={`${testid}-checkbox`} checked={!!checked} onChange={(e) => onCheckedChange(e.target.checked)} className="mt-0.5 h-4 w-4 accent-rose-500 shrink-0" />
          <span className="text-xs">{t("commit_agree", lang)}</span>
        </label>
      )}
    </div>
  );
}
