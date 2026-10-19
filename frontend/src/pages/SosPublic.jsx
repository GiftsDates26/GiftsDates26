import React, { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { Siren, Navigation } from "lucide-react";
import axios from "axios";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const ago = (iso) => Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 60000));

export default function SosPublic() {
  const { token } = useParams();
  const [d, setD] = useState(null);
  const [err, setErr] = useState(false);
  useEffect(() => {
    const load = () => axios.get(`${API}/sos/public/${token}`).then(r => setD(r.data)).catch(() => setErr(true));
    load(); const iv = setInterval(load, 20000); return () => clearInterval(iv);
  }, [token]);

  return (
    <div className="aurora-bg min-h-screen flex items-start justify-center p-4 sm:p-10">
      <div className="w-full max-w-2xl rounded-2xl border-2 border-red-500/50 bg-[#161320] p-5 sm:p-7 space-y-4" data-testid="sos-public">
        <div className="flex items-center gap-2">
          <Siren className="text-red-400 animate-pulse" />
          <h1 className="font-serif-luxe text-3xl sm:text-4xl text-white">SOS</h1>
        </div>
        {err ? <p className="text-sm text-slate-400" data-testid="sos-public-expired">This SOS link has expired or is not valid.</p>
          : !d ? <p className="text-sm text-slate-400">Loading…</p> : <>
            <p className="text-sm text-slate-200" data-testid="sos-public-text"><b>{d.name}</b> pressed SOS during a date on GiftsDates {ago(d.created_at)} min ago. Our support team has been alerted.
              {d.status === "resolved" && <span className="text-emerald-300"> Support has marked this alert as resolved.</span>}</p>
            {d.lat != null ? <>
              <div className="text-xs text-slate-400">Last location update: {ago(d.updated_at)} min ago (refreshes automatically)</div>
              <iframe title="sos-map" className="w-full h-72 rounded-xl border border-white/10" src={`https://maps.google.com/maps?q=${d.lat},${d.lng}&z=15&output=embed`} data-testid="sos-public-map" />
              <a href={`https://www.google.com/maps/dir/?api=1&destination=${d.lat},${d.lng}`} target="_blank" rel="noreferrer" data-testid="sos-public-directions"
                className="inline-flex items-center gap-1.5 rounded-full bg-sky-500 hover:bg-sky-400 transition-colors text-white text-sm px-4 py-2"><Navigation size={14} />Directions</a>
            </> : <p className="text-sm text-amber-300">Their location is not available yet.</p>}
            <p className="text-xs text-red-200">If you think they are in danger, call your local emergency services.</p>
          </>}
      </div>
    </div>
  );
}
