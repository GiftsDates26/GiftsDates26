import React, { useEffect, useState } from "react";
import { toast } from "sonner";
import { Flag } from "lucide-react";
import { Button } from "./ui/button";
import { api, fileUrl } from "../lib/api";

export const ReportPhotos = ({ photos, testid }) => photos?.length ? (
  <div className="flex flex-wrap gap-1.5 mt-1.5" data-testid={testid}>
    {photos.map(p => <a key={p} href={fileUrl(p)} target="_blank" rel="noreferrer"><img src={fileUrl(p)} alt="" className="w-14 h-14 rounded-md object-cover border border-white/10 hover:opacity-80 transition-opacity" /></a>)}
  </div>
) : null;

export const ReplyView = ({ reply, testid }) => (
  <div className="mt-2 text-xs rounded-md border border-white/10 bg-white/5 p-2" data-testid={testid}>
    {reply ? <><div className="text-sky-200">Reply from the reported person: "{reply.details}"</div><ReportPhotos photos={reply.photos} testid={`${testid}-photos`} /></>
      : <span className="text-slate-500">No reply from the reported person yet.</span>}
  </div>
);

export default function AdminBookingReports() {
  const [rows, setRows] = useState([]);
  const load = () => api.get("/admin/booking-reports").then(r => setRows(r.data.bookings || [])).catch(() => {});
  useEffect(() => { load(); }, []);
  const resolve = async (b, action) => {
    const msg = action === "refund_booker" ? `Refund all coins (🪙${b.coins}${b.taxi?.status === "sent" ? ` + taxi 🪙${b.taxi.coins}` : ""}) to ${b.inviter?.name}?` : "Dismiss this report? The date continues as normal.";
    if (!window.confirm(msg)) return;
    try { await api.post(`/admin/booking-reports/${b.id}/resolve?action=${action}`); toast.success("Done"); load(); }
    catch (e) { toast.error(e.response?.data?.detail || "Failed"); }
  };

  return (
    <div className="glass rounded-2xl p-5 mt-4" data-testid="admin-booking-reports">
      <h3 className="font-serif-luxe text-xl mb-3 flex items-center gap-2"><Flag size={16} className="text-rose-300" />Booked date reports ({rows.length})</h3>
      {rows.length === 0 ? <div className="text-sm text-slate-500 py-4 text-center">No reports</div> : rows.map(b => {
        const r = b.report || {}, open = (r.status || "open") === "open";
        const reporter = r.reporter_id === b.from_id ? b.inviter : b.recipient;
        return (
          <div key={b.id} className="py-3 border-t border-white/5 flex flex-wrap items-start gap-3" data-testid={`admin-booking-report-${b.id}`}>
            <div className="flex-1 min-w-[260px]">
              <div className="text-sm"><b>{b.inviter?.name}</b> → <b>{b.recipient?.name}</b> · {b.venue} · 🪙{b.coins} · <span className="uppercase text-rose-300">{open ? "open" : r.status}</span></div>
              <div className="text-xs text-slate-400">{new Date(b.scheduled_at).toLocaleString()} · reported by {reporter?.name}</div>
              <div className="text-xs text-rose-300 mt-1">{(r.reasons || []).join(", ")} — "{r.details}"{r.evidence ? ` · evidence: ${r.evidence}` : ""}</div>
              <ReportPhotos photos={r.photos} testid={`admin-booking-report-photos-${b.id}`} />
              <ReplyView reply={r.reply} testid={`admin-booking-reply-${b.id}`} />
            </div>
            {open && <>
              <Button size="sm" variant="outline" onClick={() => resolve(b, "refund_booker")} className="bg-white/5 border-white/15" data-testid={`admin-booking-refund-${b.id}`}>Refund booker</Button>
              <Button size="sm" variant="outline" onClick={() => resolve(b, "dismiss")} className="bg-white/5 border-white/15" data-testid={`admin-booking-dismiss-${b.id}`}>Dismiss</Button>
            </>}
          </div>
        );
      })}
    </div>
  );
}
