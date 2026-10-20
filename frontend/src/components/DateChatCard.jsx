import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { CalendarHeart, Check, Clock, Coins, Loader2, MapPin, X } from "lucide-react";
import { toast } from "sonner";
import { api } from "../lib/api";
import { useApp } from "../context/AppContext";
import { t } from "../lib/i18n";
import { MapsLink } from "./AddressPicker";
import DeclineReasonDialog, { DeclineNote } from "./DeclineReasonDialog";

const PAGE = { invite: "/dates", booking: "/dates", vip: "/vip-bookings" };

// endpoints for instant approval / decline straight from the chat
const ACTIONS = {
  invite: {
    invite: { choose: (id, opt) => api.post(`/invites/${id}/choose`, { idea_id: opt }), decline: (id, r) => api.post(`/invites/${id}/cancel`, null, { params: { reason: r } }) },
    location: { accept: (id) => api.post(`/invites/${id}/location/confirm`), decline: (id) => api.post(`/invites/${id}/location/reject`) },
  },
  booking: { invite: { choose: (id, opt) => api.post(`/dates/respond/${id}`, null, { params: { accept: true, selected_activity: opt } }), accept: (id) => api.post(`/dates/respond/${id}`, null, { params: { accept: true } }), decline: (id, r) => api.post(`/dates/respond/${id}`, null, { params: { accept: false, reason: r } }) } },
  vip: { invite: { accept: (id) => api.post(`/vip/schedule/bookings/${id}/confirm`), decline: (id, r) => api.post(`/vip/schedule/bookings/${id}/decline`, null, { params: { reason: r } }) } },
};

const fmt = (iso, lang) => { try { return new Date(iso).toLocaleString(lang, { weekday: "short", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" }); } catch { return iso; } };

function Details({ m, lang }) {
  const d = m.data || {}, loc = d.location || {};
  const addr = [loc.venue, loc.address, loc.city, loc.postal_code, loc.country].filter(Boolean).join(", ");
  return (
    <div className="space-y-1 text-xs text-slate-300">
      {d.when && <div className="flex items-center gap-1.5"><Clock size={11} className="text-amber-300" />{fmt(d.when, lang)}{d.end ? ` – ${d.end}` : ""}</div>}
      {addr && <div className="flex items-start gap-1.5"><MapPin size={11} className="mt-0.5 text-rose-300 shrink-0" /><span>{addr} <MapsLink loc={loc} testid={`chat-date-maps-${m.id}`} /></span></div>}
      {d.place === "own" && <div className="flex items-center gap-1.5"><MapPin size={11} className="text-rose-300" />{t("dc_vip_place", lang)}</div>}
      {d.coins > 0 && <div className="flex items-center gap-1.5 text-amber-200 font-mono-num"><Coins size={11} />{d.coins}</div>}
      {d.option && <div className="text-rose-200">♥ {d.option}</div>}
      {d.refunded > 0 && <div className="text-emerald-300">🪙 {d.refunded} {t("dc_refunded", lang)}</div>}
      <DeclineNote reason={d.reason} testid={`chat-date-reason-${m.id}`} />
    </div>
  );
}

export default function DateChatCard({ m, onDone }) {
  const { user, lang } = useApp();
  const nav = useNavigate();
  const [busy, setBusy] = useState(null);
  const [pick, setPick] = useState(null);
  const [declineOpen, setDeclineOpen] = useState(false);
  const acts = ACTIONS[m.kind]?.[m.event];
  const mine = m.action_for === user.id && acts;
  const opts = m.data?.options || [];
  const run = async (key, fn) => {
    setBusy(key);
    try { await fn(); toast.success(t("dc_done", lang)); onDone?.(); }
    catch (e) { toast.error(e.response?.data?.detail || t("failed", lang)); }
    finally { setBusy(null); }
  };
  const declineNeedsReason = m.event === "invite";
  return (
    <div className="w-[300px] max-w-full rounded-2xl border border-rose-400/30 bg-gradient-to-br from-rose-500/10 to-amber-500/5 p-3 text-slate-100" data-testid={`chat-date-card-${m.id}`}>
      <div className="flex items-center gap-1.5 text-sm font-semibold mb-1.5"><CalendarHeart size={14} className="text-rose-300" />{m.text}</div>
      <Details m={m} lang={lang} />
      {opts.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1.5" data-testid={`chat-date-options-${m.id}`}>
          {opts.map((o, i) => {
            const id = o.id || o, name = o.name || o;
            return mine && acts.choose
              ? <button key={i} type="button" onClick={() => setPick(id)} data-testid={`chat-date-option-${m.id}-${i}`}
                  className={`rounded-full border px-2.5 py-1 text-[11px] transition-colors ${pick === id ? "border-emerald-400 bg-emerald-500/20 text-emerald-100" : "border-white/15 bg-white/5 hover:bg-white/10"}`}>{name}</button>
              : <span key={i} className="rounded-full border border-white/10 bg-white/5 px-2.5 py-1 text-[11px] text-slate-300">{name}</span>;
          })}
        </div>
      )}
      {mine && (
        <div className="mt-2.5 flex flex-wrap gap-2">
          <button type="button" disabled={!!busy || (acts.choose && opts.length > 0 && !pick)} data-testid={`chat-date-accept-${m.id}`}
            onClick={() => run("ok", () => acts.choose && opts.length ? acts.choose(m.ref_id, pick) : acts.accept(m.ref_id))}
            className="inline-flex items-center gap-1 rounded-full bg-emerald-600 hover:bg-emerald-500 disabled:opacity-40 px-3 py-1.5 text-xs font-medium text-white transition-colors">
            {busy === "ok" ? <Loader2 size={12} className="animate-spin" /> : <Check size={12} />}{t(acts.choose && opts.length && !pick ? "dc_pick_first" : "dc_accept", lang)}
          </button>
          <button type="button" disabled={!!busy} data-testid={`chat-date-decline-${m.id}`}
            onClick={() => declineNeedsReason ? setDeclineOpen(true) : run("no", () => acts.decline(m.ref_id))}
            className="inline-flex items-center gap-1 rounded-full border border-rose-500/40 bg-white/5 hover:bg-rose-500/15 px-3 py-1.5 text-xs text-rose-200 transition-colors">
            {busy === "no" ? <Loader2 size={12} className="animate-spin" /> : <X size={12} />}{t("dc_decline", lang)}
          </button>
        </div>
      )}
      <button type="button" onClick={() => nav(PAGE[m.kind] || "/dates")} data-testid={`chat-date-open-${m.id}`} className="mt-2 text-[11px] text-sky-300 hover:text-sky-200">{t("dc_open", lang)} →</button>
      <DeclineReasonDialog open={declineOpen} onClose={() => setDeclineOpen(false)} testid={`chat-decline-dialog-${m.id}`}
        onConfirm={(r) => run("no", () => acts.decline(m.ref_id, r))} />
    </div>
  );
}
