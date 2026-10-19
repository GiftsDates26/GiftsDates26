import React, { useEffect, useRef, useState } from "react";
import { Phone, PhoneOff, Video as VideoIcon, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { Dialog, DialogContent } from "./ui/dialog";
import { Button } from "./ui/button";
import { api, fileUrl } from "../lib/api";
import { useApp } from "../context/AppContext";
import { requestCamera, stopStream } from "../lib/media";
import CameraBlocked from "./CameraBlocked";
import CallStage from "./CallStage";

// Global watcher: rings when another member video-calls you. Accepting requires your camera & microphone.
export default function IncomingCallWatcher() {
  const { user, refreshUser } = useApp();
  const [call, setCall] = useState(null);
  const [phase, setPhase] = useState("ringing"); // ringing | camera | blocked | accepting | in_call | ended
  const [camError, setCamError] = useState("");
  const [stream, setStream] = useState(null);
  const [endReason, setEndReason] = useState("");
  const busyRef = useRef(false); busyRef.current = !!call;
  const dismissed = useRef(new Set());

  useEffect(() => {
    if (!user) return;
    let alive = true, timer;
    const poll = async () => {
      if (!alive) return;
      if (!busyRef.current && document.visibilityState !== "hidden") {
        try {
          const { data } = await api.get("/videocalls/incoming");
          const c = (data || []).find(x => !dismissed.current.has(x.id));
          if (c && alive) { setCall(c); setPhase("ringing"); setEndReason(""); }
        } catch { /* ignore */ }
      }
      timer = setTimeout(poll, 3000);
    };
    poll();
    return () => { alive = false; clearTimeout(timer); };
  }, [user]);

  // While ringing, watch for the caller hanging up / timeout.
  useEffect(() => {
    if (!call || !["ringing", "camera", "blocked"].includes(phase)) return;
    let alive = true;
    const id = setInterval(async () => {
      try {
        const { data } = await api.get(`/videocalls/${call.id}`);
        if (alive && data.status !== "ringing") { stopStream(stream); setStream(null); setEndReason("missed"); setPhase("ended"); }
      } catch { /* ignore */ }
    }, 2000);
    return () => { alive = false; clearInterval(id); };
  }, [call, phase]); // eslint-disable-line react-hooks/exhaustive-deps

  const close = () => { if (call) dismissed.current.add(call.id); stopStream(stream); setStream(null); setCall(null); setPhase("ringing"); };
  const decline = () => { if (call) api.post(`/videocalls/${call.id}/decline`).catch(() => {}); close(); };

  const accept = async () => {
    setPhase("camera");
    const r = await requestCamera();
    if (!r.ok) { setCamError(r.message); setPhase("blocked"); return; }
    setStream(r.stream); setPhase("accepting");
    try {
      const { data } = await api.post(`/videocalls/${call.id}/accept`);
      setCall(data); setPhase("in_call");
    } catch (e) {
      stopStream(r.stream); setStream(null);
      const d = e.response?.data?.detail || "";
      setEndReason(d === "CALLER_INSUFFICIENT_COINS" ? "coins" : "missed"); setPhase("ended");
      if (d && d !== "CALLER_INSUFFICIENT_COINS" && !d.startsWith("CALL_")) toast.error(d);
    }
  };

  if (!user || !call) return null;
  const caller = call.caller || {};
  const photo = caller.photo ? fileUrl(caller.photo) : null;
  const ended = { missed: "The call was cancelled or timed out.", coins: "The caller doesn't have enough coins for this call.", partner_ended: `${caller.name} ended the call.`, time_up: "Call time is over.", hangup: "You ended the call.", failed: "The connection was lost." };

  return (
    <Dialog open onOpenChange={(v) => { if (!v && phase !== "in_call") (phase === "ended" ? close() : decline()); }}>
      <DialogContent className="bg-[#0D0B12] border-white/10 text-white max-w-2xl p-0 overflow-hidden" data-testid="incoming-call-dialog">
        {phase === "ringing" && (
          <div className="p-8 text-center space-y-4" data-testid="incoming-call-ringing">
            <div className="text-xs uppercase tracking-[0.25em] text-[#D4AF37]">Incoming video call</div>
            <div className="w-28 h-28 mx-auto rounded-full overflow-hidden bg-gradient-to-br from-rose-500 to-violet-500 flex items-center justify-center text-5xl font-serif-luxe ring-pulse" translate="no">
              {photo ? <img src={photo} alt="" className="w-full h-full object-cover" /> : caller.name?.[0]}
            </div>
            <div className="font-serif-luxe text-3xl" translate="no">{caller.name}</div>
            <div className="text-sm text-slate-400 font-mono-num">{call.minutes} min · 🪙 {call.rate}/min · you earn 🪙 {call.cost}</div>
            <div className="flex items-center justify-center gap-2 text-xs text-slate-400"><VideoIcon size={13} className="text-[#D4AF37]" /> Accepting will ask to use your camera and microphone</div>
            <div className="flex justify-center gap-6 pt-2">
              <div className="text-center">
                <Button data-testid="incoming-call-decline" onClick={decline} size="icon" className="rounded-full h-16 w-16 bg-red-600 hover:bg-red-700 border-0"><PhoneOff size={24} /></Button>
                <div className="text-xs text-slate-400 mt-1.5">Decline</div>
              </div>
              <div className="text-center">
                <Button data-testid="incoming-call-accept" onClick={accept} size="icon" className="rounded-full h-16 w-16 bg-emerald-600 hover:bg-emerald-500 border-0 accept-pulse"><Phone size={24} /></Button>
                <div className="text-xs text-slate-400 mt-1.5">Accept</div>
              </div>
            </div>
          </div>
        )}
        {(phase === "camera" || phase === "accepting") && (
          <div className="p-10 text-center space-y-3">
            <Loader2 className="animate-spin mx-auto text-[#D4AF37]" size={28} />
            <div className="font-serif-luxe text-xl">{phase === "camera" ? "Allow camera & microphone" : "Connecting…"}</div>
            {phase === "camera" && <p className="text-sm text-slate-400">Please choose "Allow" in your browser's pop-up.</p>}
          </div>
        )}
        {phase === "blocked" && <CameraBlocked message={camError} onRetry={accept} onCancel={decline} cancelLabel="Decline call" />}
        {phase === "in_call" && stream && (
          <CallStage call={call} role="callee" localStream={stream} partnerName={caller.name}
            onEnded={(reason) => { setStream(null); setEndReason(reason); setPhase("ended"); refreshUser(); }} />
        )}
        {phase === "ended" && (
          <div className="p-8 text-center space-y-3" data-testid="incoming-call-ended">
            <div className="font-serif-luxe text-2xl">Call ended</div>
            <div className="text-sm text-slate-400">{ended[endReason] || ""}</div>
            <Button data-testid="incoming-call-close" onClick={close} className="rose-btn text-white border-0">Close</Button>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
