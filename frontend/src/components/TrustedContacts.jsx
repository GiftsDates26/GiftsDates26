import React, { useEffect, useState } from "react";
import { ShieldCheck, Plus, Trash2, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { api } from "../lib/api";
import { useApp } from "../context/AppContext";
import { t } from "../lib/i18n";

const EMPTY = { name: "", email: "", phone: "" };

export default function TrustedContacts() {
  const { lang } = useApp();
  const [list, setList] = useState([]);
  const [max, setMax] = useState(3);
  const [busy, setBusy] = useState(false);
  useEffect(() => { api.get("/me/trusted-contacts").then(r => { setList(r.data.contacts); setMax(r.data.max); }).catch(() => {}); }, []);

  const set = (i, k, v) => setList(l => l.map((c, j) => (j === i ? { ...c, [k]: v } : c)));
  const save = async (next = list) => {
    setBusy(true);
    try {
      const r = await api.put("/me/trusted-contacts", { contacts: next.map(c => ({ name: c.name, email: c.email || null, phone: c.phone || null })) });
      setList(r.data.contacts); toast.success(t("tc_saved", lang));
    } catch (e) { const d = e.response?.data?.detail; toast.error(typeof d === "string" ? d : t("tc_invalid", lang)); }
    finally { setBusy(false); }
  };
  const remove = (i) => { const next = list.filter((_, j) => j !== i); setList(next); save(next); };

  return (
    <div className="glass rounded-2xl p-5 space-y-3" data-testid="trusted-contacts">
      <div className="flex items-center gap-2">
        <ShieldCheck size={18} className="text-emerald-300" />
        <h3 className="font-serif-luxe text-xl">{t("tc_title", lang)}</h3>
      </div>
      <p className="text-xs text-slate-400">{t("tc_desc", lang)}</p>
      {list.map((c, i) => (
        <div key={i} className="grid grid-cols-1 sm:grid-cols-[1fr_1fr_1fr_auto] gap-2 items-center" data-testid={`trusted-contact-${i}`}>
          <Input value={c.name || ""} onChange={e => set(i, "name", e.target.value)} placeholder={t("tc_name", lang)} className="bg-white/5 border-white/10 h-9" data-testid={`trusted-contact-name-${i}`} />
          <Input type="email" value={c.email || ""} onChange={e => set(i, "email", e.target.value)} placeholder={t("tc_email", lang)} className="bg-white/5 border-white/10 h-9" data-testid={`trusted-contact-email-${i}`} />
          <Input type="tel" value={c.phone || ""} onChange={e => set(i, "phone", e.target.value)} placeholder={t("tc_phone", lang)} className="bg-white/5 border-white/10 h-9" data-testid={`trusted-contact-phone-${i}`} />
          <Button size="sm" variant="ghost" onClick={() => remove(i)} disabled={busy} className="text-rose-300 hover:bg-rose-500/10 h-9" data-testid={`trusted-contact-remove-${i}`}><Trash2 size={14} /></Button>
        </div>
      ))}
      <div className="flex flex-wrap gap-2">
        {list.length < max && <Button size="sm" variant="outline" onClick={() => setList(l => [...l, { ...EMPTY }])} className="bg-white/5 border-white/15 h-9" data-testid="trusted-contact-add"><Plus size={14} className="me-1" />{t("tc_add", lang)}</Button>}
        {list.length > 0 && <Button size="sm" onClick={() => save()} disabled={busy} className="bg-emerald-600 hover:bg-emerald-500 text-white border-0 h-9" data-testid="trusted-contacts-save">{busy && <Loader2 size={14} className="me-1 animate-spin" />}{t("tc_save", lang)}</Button>}
      </div>
    </div>
  );
}
