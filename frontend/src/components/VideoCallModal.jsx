import React, { useEffect, useRef, useState } from "react";
import { Dialog, DialogContent } from "./ui/dialog";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { Label } from "./ui/label";
import { Video as VideoIcon, PhoneOff, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { api } from "../lib/api";
import { useApp } from "../context/AppContext";
import { t } from "../lib/i18n";
import { presence } from "../lib/presence";
import { requestCamera, stopStream } from "../lib/media";
import CameraBlocked from "./CameraBlocked";
import CallStage from "./CallStage";

const RING_MS = 30000;

export default function VideoCallModal({ open, onOpenChange, target }) {
  const { user, meta, lang, refreshUser } = useApp();
  const rate = Math.max(target?.video_rate || 0, meta?.video_rate || 10);
  const online = presence(target, lang).online;
  const [minutes, setMinutes] = useState(5);
  // setup | camera | blocked | ringing | in_call | ended
  const [phase, setPhase] = useState("setup");
  const [camError, setCamError] = useState("");
  const [stream, setStream] = useState(null);
  const [call, setCall] = useState(null);
  const [endInfo, setEndInfo] = useState(null);
  const previewRef = useRef(null);
  const pollRef = useRef(null);
  const streamRef = useRef(null); streamRef.current = stream;
  const callRef = useRef(null); callRef.current = call;
  const phaseRef = useRef(phase); phaseRef.current = phase;

  const cleanup = () => {
    clearTimeout(pollRef.current);
    if (callRef.current && phaseRef.current === "ringing") api.post(`/videocalls/${callRef.current.id}/decline`).catch(() => {});
    if (phaseRef.current !== "in_call") stopStream(streamRef.current);
  };
  useEffect(() => {
    if (!open) { cleanup(); setPhase("setup"); setStream(null); setCall(null); setEndInfo(null); setCamError(""); }
  }, [open]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => () => cleanup(), []); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { if (previewRef.current && stream) previewRef.current.srcObject = stream; }, [stream, phase]);

  const cost = minutes * rate;

  // 1) Camera + microphone must be allowed before anything is sent or charged.
  const askCamera = async () => {
    setPhase("camera");
    const r = await requestCamera();
    if (!r.ok) { setCamError(r.message); setPhase("blocked"); return null; }
    setStream(r.stream);
    return r.stream;
  };

  const start = async () => {
    if (!online) { toast.error(t("video_calls_offline_toast", lang)); return; }
    if (((user.coins || 0) + (user.withdrawable || 0)) < cost) { toast.error(t("not_enough_coins", lang)); return; }
    const s = stream || await askCamera();
    if (!s) return;
    try {
      const { data } = await api.post("/videocalls/start", { target_id: target.id, minutes });
      setCall(data); setPhase("ringing");
      const startedAt = Date.now();
      const poll = async () => {
        try {
          const { data: c } = await api.get(`/videocalls/${data.id}`);
          if (c.status === "active") { setCall(c); setPhase("in_call"); refreshUser(); return; }
          if (["declined", "missed", "cancelled", "failed"].includes(c.status)) {
            stopStream(s); setStream(null);
            setEndInfo({ reason: c.status === "declined" ? "declined" : c.reason === "CALLER_INSUFFICIENT_COINS" ? "coins" : "missed" });
            setPhase("ended"); return;
          }
        } catch { /* retry */ }
        if (Date.now() - startedAt > RING_MS + 3000) {
          api.post(`/videocalls/${data.id}/decline`).catch(() => {});
          stopStream(s); setStream(null); setEndInfo({ reason: "missed" }); setPhase("ended"); return;
        }
        pollRef.current = setTimeout(poll, 1500);
      };
      pollRef.current = setTimeout(poll, 1500);
    } catch (e) {
      const detail = e.response?.data?.detail;
      const msg = detail === "VIDEO_CALLS_DISABLED" ? t("video_calls_disabled_toast", lang)
        : detail === "USER_OFFLINE" ? t("video_calls_offline_toast", lang)
        : (detail || t("failed", lang));
      toast.error(msg); stopStream(s); setStream(null); setPhase("setup");
    }
  };

  const cancelRinging = () => {
    clearTimeout(pollRef.current);
    if (call) api.post(`/videocalls/${call.id}/decline`).catch(() => {});
    stopStream(stream); setStream(null); setCall(null); setPhase("setup");
  };

  const endText = {
    declined: `${target?.name} declined the call. No coins were charged.`,
    missed: `${target?.name} didn't answer. No coins were charged.`,
    coins: "Not enough coins to start this call. No coins were charged.",
    partner_ended: `${target?.name} ended the call.`,
    failed: "The connection was lost.",
  };

  return (
    <Dialog open={open} onOpenChange={(v) => { if (!v && phase === "in_call") return; onOpenChange(v); }}>
      <DialogContent className="bg-[#0D0B12] border-white/10 text-white max-w-2xl p-0 overflow-hidden">
        {phase === "setup" && (
          <div className="p-6 space-y-4">
            <h3 className="font-serif-luxe text-2xl">{t("video_call", lang)} · <span translate="no">{target?.name}</span></h3>
            <Label className="text-xs text-slate-400">{t("duration_min", lang)}</Label>
            <Input data-testid="videocall-minutes-input" type="number" min={1} max={60} value={minutes} onChange={e => setMinutes(Math.max(1, Math.min(60, parseInt(e.target.value || 1))))} className="bg-white/5 border-white/10" />
            <div className="glass rounded-xl p-3 text-sm">
              <div className="flex justify-between"><span className="text-slate-400">{t("rate", lang)}</span><span className="font-mono-num text-amber-300">🪙 {rate}/{t("minutes", lang)}</span></div>
              <div className="flex justify-between mt-1"><span className="text-slate-400">{t("cost", lang)}</span><span className="font-mono-num text-amber-300">🪙 {cost}</span></div>
              <div className="flex justify-between mt-1"><span className="text-slate-400">{t("balance", lang)}</span><span className="font-mono-num">🪙 {(user?.coins || 0) + (user?.withdrawable || 0)}</span></div>
            </div>
            <div className="flex items-start gap-2 text-xs text-slate-400 rounded-xl border border-[#D4AF37]/20 bg-[#D4AF37]/5 p-3" data-testid="videocall-camera-note">
              <VideoIcon size={14} className="text-[#D4AF37] shrink-0 mt-0.5" />
              <span>Your camera and microphone must be allowed to call. Coins are charged only when the call is answered.</span>
            </div>
            <Button data-testid="videocall-start-button" onClick={start} disabled={!online} className="rose-btn text-white border-0 w-full h-11 disabled:opacity-50 disabled:cursor-not-allowed">{t("start_call", lang)}</Button>
            {!online && <p data-testid="videocall-offline-note" className="text-xs text-amber-300/90 text-center">{t("video_calls_offline_toast", lang)}</p>}
          </div>
        )}
        {phase === "camera" && (
          <div className="p-10 text-center space-y-3" data-testid="videocall-camera-request">
            <Loader2 className="animate-spin mx-auto text-[#D4AF37]" size={28} />
            <div className="font-serif-luxe text-xl">Allow camera & microphone</div>
            <p className="text-sm text-slate-400">Please choose "Allow" in your browser's pop-up.</p>
          </div>
        )}
        {phase === "blocked" && (
          <CameraBlocked message={camError} onRetry={start} onCancel={() => setPhase("setup")} cancelLabel="Back" />
        )}
        {phase === "ringing" && (
          <div className="relative aspect-video bg-black" data-testid="videocall-ringing">
            <video ref={previewRef} autoPlay playsInline muted className="absolute inset-0 w-full h-full object-cover scale-x-[-1] opacity-60" data-testid="videocall-preview" />
            <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 bg-black/40">
              <div className="w-24 h-24 rounded-full bg-gradient-to-br from-rose-500 to-violet-500 flex items-center justify-center text-4xl font-serif-luxe ring-pulse" translate="no">{target?.name?.[0]}</div>
              <div className="font-serif-luxe text-2xl mt-2">Calling <span translate="no">{target?.name}</span>…</div>
              <div className="text-xs text-slate-300">No coins are charged until they answer</div>
            </div>
            <div className="absolute bottom-5 left-1/2 -translate-x-1/2">
              <Button data-testid="videocall-cancel-ringing" onClick={cancelRinging} size="icon" className="rounded-full h-14 w-14 bg-red-600 hover:bg-red-700 border-0"><PhoneOff size={20} /></Button>
            </div>
          </div>
        )}
        {phase === "in_call" && call && stream && (
          <CallStage call={call} role="caller" localStream={stream} partnerName={target?.name}
            onEnded={(reason, secs) => { setStream(null); setEndInfo({ reason, secs }); setPhase("ended"); refreshUser(); }} />
        )}
        {phase === "ended" && (
          <div className="p-8 text-center space-y-3" data-testid="videocall-ended">
            <div className="w-14 h-14 mx-auto rounded-2xl bg-white/5 border border-white/10 flex items-center justify-center"><PhoneOff size={22} className="text-slate-300" /></div>
            <div className="font-serif-luxe text-2xl">{t("call_ended", lang)}</div>
            {endText[endInfo?.reason] && <div className="text-sm text-slate-400" data-testid="videocall-ended-reason">{endText[endInfo.reason]}</div>}
            <Button data-testid="videocall-close-button" onClick={() => onOpenChange(false)} className="rose-btn text-white border-0">{t("close", lang)}</Button>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
