import React from "react";
import { Languages, Play, Square, Mail, MessageSquare, RefreshCw, CheckCircle2, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { api } from "../lib/api";
import { LANGUAGES } from "../lib/i18n";
import { Button } from "./ui/button";
import { Progress } from "./ui/progress";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "./ui/select";

const flagOf = (c) => LANGUAGES.find(l => l.code === c)?.flag || "🌐";
const nativeOf = (c) => LANGUAGES.find(l => l.code === c)?.name || c;

export default function AdminTranslations() {
  const [st, setSt] = React.useState(null);
  const [busy, setBusy] = React.useState(false);
  const [pvLang, setPvLang] = React.useState("es");
  const [pv, setPv] = React.useState(null);
  const [pvBusy, setPvBusy] = React.useState(false);

  const load = React.useCallback(async () => {
    try { const { data } = await api.get("/admin/i18n/status"); setSt(data); } catch (e) { toast.error(e.response?.data?.detail || "Failed to load"); }
  }, []);
  React.useEffect(() => { load(); }, [load]);
  const running = !!st?.job?.running;
  React.useEffect(() => { if (!running) return; const id = setInterval(load, 3000); return () => clearInterval(id); }, [running, load]);

  const start = async () => {
    setBusy(true);
    try { await api.post("/admin/i18n/pretranslate", {}); toast.success("Pre-translation started"); await load(); }
    catch (e) { toast.error(e.response?.data?.detail || "Failed"); } finally { setBusy(false); }
  };
  const cancel = async () => { await api.post("/admin/i18n/cancel").catch(() => {}); toast("Stopping after the current batch…"); load(); };
  const preview = async () => {
    setPvBusy(true);
    try { const { data } = await api.post("/admin/i18n/preview-notification", { lang: pvLang }); setPv(data); }
    catch (e) { toast.error(e.response?.data?.detail || "Failed"); } finally { setPvBusy(false); }
  };

  const total = st?.total_sources || 0;
  const jobLangs = st?.job?.langs || {};
  const order = st?.job?.order || st?.default_langs || [];
  const overall = order.length && total ? Math.round(order.reduce((a, c) => a + Math.min(jobLangs[c]?.done || 0, total), 0) / (order.length * total) * 100) : 0;

  return (
    <div className="space-y-6" data-testid="admin-translations">
      <div className="glass rounded-2xl p-5">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h3 className="font-serif-luxe text-xl flex items-center gap-2"><Languages size={20} className="text-[#D4AF37]" /> Pre-translate the whole site</h3>
            <p className="text-sm text-slate-400 mt-1 max-w-2xl">Translates every page, menu, dropdown, notice and warning ahead of time for the 15 main markets, so visitors never wait on first load. Other languages still translate automatically on demand.</p>
            <p className="text-xs text-slate-500 mt-2" data-testid="admin-tr-total">{total} site strings · already-translated texts are reused at no cost</p>
          </div>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" onClick={load} className="bg-white/5 border-white/15" data-testid="admin-tr-refresh"><RefreshCw size={14} className="me-1" />Refresh</Button>
            {running
              ? <Button size="sm" onClick={cancel} variant="outline" className="bg-rose-500/10 border-rose-500/40 text-rose-300" data-testid="admin-tr-cancel"><Square size={14} className="me-1" />Stop</Button>
              : <Button size="sm" onClick={start} disabled={busy} className="rose-btn text-white border-0" data-testid="admin-tr-start"><Play size={14} className="me-1" />Pre-translate now</Button>}
          </div>
        </div>

        {(running || st?.job?.langs) && (
          <div className="mt-5" data-testid="admin-tr-progress">
            <div className="flex items-center justify-between text-xs text-slate-400 mb-1.5">
              <span className="flex items-center gap-1.5">{running ? <><Loader2 size={12} className="animate-spin text-[#D4AF37]" /> Working on <b className="text-slate-200" translate="no">{nativeOf(st.job.current || "")}</b></> : st?.job?.finished_at ? <><CheckCircle2 size={12} className="text-emerald-400" /> Finished {new Date(st.job.finished_at).toLocaleString()}</> : "Stopped"}</span>
              <span className="font-mono-num" data-testid="admin-tr-overall">{overall}%</span>
            </div>
            <Progress value={overall} className="h-2 bg-white/10" />
            {st?.job?.error && <div className="text-xs text-rose-300 mt-2">{st.job.error}</div>}
          </div>
        )}

        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3 mt-5">
          {(st?.coverage || []).map(c => {
            const j = jobLangs[c.code];
            const done = Math.min(j ? j.done : c.cached, total);
            const pct = total ? Math.round(done / total * 100) : 0;
            return (
              <div key={c.code} className="rounded-xl border border-white/10 bg-white/[0.03] p-3" data-testid={`admin-tr-lang-${c.code}`}>
                <div className="flex items-center justify-between text-sm">
                  <span className="flex items-center gap-2" translate="no"><span className="text-lg">{flagOf(c.code)}</span>{nativeOf(c.code)}</span>
                  <span className={`text-[10px] uppercase tracking-wider ${j?.status === "done" || pct >= 98 ? "text-emerald-400" : j?.status === "translating" || j?.status === "seeding" ? "text-[#D4AF37]" : "text-slate-500"}`}>{j?.status || (pct >= 98 ? "done" : "—")}</span>
                </div>
                <Progress value={pct} className="h-1.5 mt-2 bg-white/10" />
                <div className="text-[11px] text-slate-500 mt-1 font-mono-num">{done} / {total}{j?.seeded ? ` · ${j.seeded} reused` : ""}{j?.failed ? ` · ${j.failed} retry later` : ""}</div>
              </div>
            );
          })}
        </div>
      </div>

      <div className="glass rounded-2xl p-5" data-testid="admin-tr-preview">
        <h3 className="font-serif-luxe text-xl flex items-center gap-2"><Mail size={18} className="text-[#D4AF37]" /> Emails & SMS in each user's language</h3>
        <p className="text-sm text-slate-400 mt-1">Every account email and text message is sent in the recipient's chosen language. Preview a sample:</p>
        <div className="flex flex-wrap items-center gap-2 mt-3">
          <Select value={pvLang} onValueChange={setPvLang}>
            <SelectTrigger className="w-[220px] bg-white/5 border-white/10" data-testid="admin-tr-preview-lang"><SelectValue /></SelectTrigger>
            <SelectContent className="bg-[#161320] border-white/10 text-slate-100 max-h-[320px]">
              {LANGUAGES.filter(l => l.code !== "en").map(l => <SelectItem key={l.code} value={l.code}><span translate="no">{l.flag} {l.name}</span></SelectItem>)}
            </SelectContent>
          </Select>
          <Button size="sm" onClick={preview} disabled={pvBusy} className="rose-btn text-white border-0" data-testid="admin-tr-preview-btn">{pvBusy ? <Loader2 size={14} className="animate-spin me-1" /> : null}Preview</Button>
          {pv && <span className="text-xs text-slate-400">Email: <b className={pv.email_configured ? "text-emerald-400" : "text-amber-300"}>{pv.email_configured ? "live" : "not configured"}</b> · SMS: <b className={pv.sms_configured ? "text-emerald-400" : "text-amber-300"}>{pv.sms_configured ? "live" : "not configured"}</b></span>}
        </div>
        {pv && (
          <div className="grid lg:grid-cols-2 gap-4 mt-4" translate="no">
            <div>
              <div className="text-xs text-slate-500 mb-1">Subject: <span className="text-slate-200" data-testid="admin-tr-preview-subject">{pv.subject}</span></div>
              <iframe title="email-preview" sandbox="" srcDoc={pv.html} className="w-full h-[300px] rounded-xl border border-white/10 bg-[#0d0b12]" />
            </div>
            <div>
              <div className="text-xs text-slate-500 mb-1 flex items-center gap-1"><MessageSquare size={12} /> SMS</div>
              <div dir={pv.rtl ? "rtl" : "ltr"} className="rounded-2xl bg-white/10 px-4 py-3 text-sm text-slate-100 max-w-sm" data-testid="admin-tr-preview-sms">{pv.sms}</div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
