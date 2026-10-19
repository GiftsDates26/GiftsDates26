import React, { useEffect, useState } from "react";
import { toast } from "sonner";
import { UserX } from "lucide-react";
import { Button } from "./ui/button";
import { api } from "../lib/api";
import { ReportPhotos } from "./AdminBookingReports";

export default function AdminNoShowReports() {
  const [rows, setRows] = useState([]);
  const load = () => api.get("/admin/no-show-reports").then((r) => setRows(r.data.reports || [])).catch(() => {});
  useEffect(() => { load(); }, []);
  const resolve = async (b, action) => {
    const msg = action === "reversed"
      ? `Reverse this report? Up to 🪙${b.refund || b.coins} will be taken back from ${b.client?.name} and paid to ${b.vip?.name}.`
      : `Uphold this report? ${b.client?.name} keeps the full refund.`;
    if (!window.confirm(msg)) return;
    try { await api.post(`/admin/no-show-reports/${b.id}/resolve?action=${action}`); toast.success("Done"); load(); }
    catch (e) { toast.error(e.response?.data?.detail || "Failed"); }
  };
  return (
    <div className="glass rounded-2xl p-5 mt-4" data-testid="admin-no-show-reports">
      <h3 className="font-serif-luxe text-xl mb-3 flex items-center gap-2"><UserX size={16} className="text-rose-300" />VIP no-show reports ({rows.length})</h3>
      {rows.length === 0 ? <div className="text-sm text-slate-500 py-4 text-center">No reports</div> : rows.map((b) => {
        const r = b.no_show_report || {}, open = r.status === "open";
        return (
          <div key={b.id} className="py-3 border-t border-white/5 flex flex-wrap items-start gap-3" data-testid={`admin-no-show-${b.id}`}>
            <div className="flex-1 min-w-[260px]">
              <div className="text-sm"><b>{b.client?.name}</b> reported <b>{b.vip?.name}</b> · {b.date} {b.start}–{b.end} · refunded 🪙{b.refund ?? b.coins}{b.taxi_coins ? ` (incl. taxi 🪙${b.taxi_coins})` : ""} · <span className={`uppercase ${open ? "text-rose-300" : "text-slate-400"}`} data-testid={`admin-no-show-status-${b.id}`}>{r.status}</span></div>
              <div className="text-[11px] text-slate-500 mt-0.5">Reported {new Date(r.created_at).toLocaleString()}{b.arrived_at ? ` · client checked in at ${new Date(b.arrived_at).toLocaleTimeString()}` : ""}{b.late ? ` · VIP said running ${b.late.minutes} min late` : ""}</div>
              {r.note && <div className="text-xs text-slate-300 mt-1.5 rounded-md border border-white/10 bg-white/5 p-2" data-testid={`admin-no-show-note-${b.id}`}>"{r.note}"</div>}
              <ReportPhotos photos={r.photo ? [r.photo] : []} testid={`admin-no-show-photo-${b.id}`} />
              {r.status === "reversed" && <div className="text-[11px] text-amber-300 mt-1">🪙{b.no_show_reversed_coins || 0} paid to the VIP</div>}
            </div>
            {open && (
              <div className="flex gap-2">
                <Button size="sm" data-testid={`admin-no-show-valid-${b.id}`} onClick={() => resolve(b, "valid")} className="bg-emerald-600 hover:bg-emerald-500 text-white border-0">Uphold</Button>
                <Button size="sm" variant="outline" data-testid={`admin-no-show-reverse-${b.id}`} onClick={() => resolve(b, "reversed")} className="bg-white/5 border-amber-500/40 text-amber-300 hover:bg-amber-500/10">VIP showed up</Button>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
