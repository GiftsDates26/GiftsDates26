import React, { useEffect, useRef, useState } from "react";
import { Mic, MicOff, Video as VideoIcon, VideoOff, PhoneOff, Loader2 } from "lucide-react";
import { Button } from "./ui/button";
import { api } from "../lib/api";
import { stopStream } from "../lib/media";

const ICE = [{ urls: ["stun:stun.l.google.com:19302", "stun:stun1.l.google.com:19302", "stun:stun2.l.google.com:19302"] }];

/**
 * Live peer-to-peer video call between the two members of an accepted call.
 * role "caller" creates the offer; "callee" answers. Signaling is relayed by the backend.
 */
export default function CallStage({ call, role, localStream, partnerName, onEnded }) {
  const localRef = useRef(null);
  const remoteRef = useRef(null);
  const pcRef = useRef(null);
  const [connected, setConnected] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [muted, setMuted] = useState(false);
  const [camOff, setCamOff] = useState(false);
  const endedRef = useRef(false);
  const total = (call?.minutes || 1) * 60;

  const finish = async (reason, notify = true) => {
    if (endedRef.current) return;
    endedRef.current = true;
    try { pcRef.current?.close(); } catch { /* noop */ }
    stopStream(localStream);
    if (notify) await api.post(`/videocalls/${call.id}/end`).catch(() => {});
    onEnded?.(reason, elapsed);
  };
  const finishRef = useRef(finish); finishRef.current = finish;

  useEffect(() => {
    if (localRef.current) localRef.current.srcObject = localStream;
    const pc = new RTCPeerConnection({ iceServers: ICE });
    pcRef.current = pc;
    localStream.getTracks().forEach(t => pc.addTrack(t, localStream));
    const remote = new MediaStream();
    if (remoteRef.current) remoteRef.current.srcObject = remote;
    pc.ontrack = (e) => { e.streams[0]?.getTracks().forEach(tr => { if (!remote.getTracks().includes(tr)) remote.addTrack(tr); }); };
    pc.onconnectionstatechange = () => {
      if (pc.connectionState === "connected") setConnected(true);
      if (pc.connectionState === "failed") finishRef.current("failed");
    };
    const send = (type, data) => api.post(`/videocalls/${call.id}/signal`, { type, data }).catch(() => {});
    pc.onicecandidate = (e) => { if (e.candidate) send("ice", e.candidate.toJSON()); };
    const pendingIce = [];
    let last = 0, alive = true;

    (async () => {
      if (role === "caller") {
        const offer = await pc.createOffer();
        await pc.setLocalDescription(offer);
        send("offer", { type: offer.type, sdp: offer.sdp });
      }
    })();

    const poll = async () => {
      if (!alive) return;
      try {
        const { data } = await api.get(`/videocalls/${call.id}/signals`, { params: { after: last } });
        for (const s of data.signals || []) {
          last = Math.max(last, s.ts);
          if (s.type === "offer" && role === "callee") {
            await pc.setRemoteDescription(s.data);
            const ans = await pc.createAnswer();
            await pc.setLocalDescription(ans);
            send("answer", { type: ans.type, sdp: ans.sdp });
            while (pendingIce.length) await pc.addIceCandidate(pendingIce.shift()).catch(() => {});
          } else if (s.type === "answer" && role === "caller" && !pc.currentRemoteDescription) {
            await pc.setRemoteDescription(s.data);
            while (pendingIce.length) await pc.addIceCandidate(pendingIce.shift()).catch(() => {});
          } else if (s.type === "ice") {
            if (pc.remoteDescription) await pc.addIceCandidate(s.data).catch(() => {});
            else pendingIce.push(s.data);
          }
        }
        if (data.status && data.status !== "active") { finishRef.current("partner_ended", false); return; }
      } catch { /* retry */ }
      if (alive) setTimeout(poll, 1000);
    };
    poll();
    return () => { alive = false; try { pc.close(); } catch { /* noop */ } };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!connected) return;
    const id = setInterval(() => setElapsed(x => {
      if (x + 1 >= total) { clearInterval(id); finishRef.current("time_up"); return total; }
      return x + 1;
    }), 1000);
    return () => clearInterval(id);
  }, [connected, total]);

  const toggleMic = () => { localStream.getAudioTracks().forEach(t => { t.enabled = muted; }); setMuted(!muted); };
  const toggleCam = () => { localStream.getVideoTracks().forEach(t => { t.enabled = camOff; }); setCamOff(!camOff); };
  const left = Math.max(total - elapsed, 0);
  const mm = String(Math.floor(left / 60)).padStart(2, "0"), ss = String(left % 60).padStart(2, "0");

  return (
    <div className="relative aspect-video bg-black" data-testid="call-stage">
      <video ref={remoteRef} autoPlay playsInline data-testid="call-remote-video" className="absolute inset-0 w-full h-full object-cover" />
      {!connected && (
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 bg-gradient-to-br from-rose-950/60 via-[#0D0B12]/80 to-violet-950/60">
          <Loader2 className="animate-spin text-[#D4AF37]" size={28} />
          <div className="text-slate-200">Connecting to <span className="font-semibold" translate="no">{partnerName}</span>…</div>
        </div>
      )}
      <video ref={localRef} autoPlay playsInline muted data-testid="call-local-video" className={`absolute top-4 end-4 w-36 sm:w-48 aspect-video object-cover rounded-xl border border-white/20 shadow-2xl bg-black scale-x-[-1] ${camOff ? "opacity-30" : ""}`} />
      <div className="absolute top-4 start-4 px-3 py-1.5 rounded-full bg-black/50 backdrop-blur text-sm flex items-center gap-2">
        <span className={`w-2 h-2 rounded-full ${connected ? "bg-emerald-400 animate-pulse" : "bg-amber-400"}`} />
        <span translate="no">{partnerName}</span>
        <span className="font-mono-num text-amber-300" data-testid="call-timer">{mm}:{ss}</span>
      </div>
      <div className="absolute bottom-5 left-1/2 -translate-x-1/2 flex items-center gap-3">
        <Button data-testid="videocall-mute-button" onClick={toggleMic} size="icon" variant="outline" className={`rounded-full h-12 w-12 border-white/20 ${muted ? "bg-rose-500/30" : "bg-white/10"}`}>{muted ? <MicOff size={18} /> : <Mic size={18} />}</Button>
        <Button data-testid="videocall-camera-button" onClick={toggleCam} size="icon" variant="outline" className={`rounded-full h-12 w-12 border-white/20 ${camOff ? "bg-rose-500/30" : "bg-white/10"}`}>{camOff ? <VideoOff size={18} /> : <VideoIcon size={18} />}</Button>
        <Button data-testid="videocall-end-button" onClick={() => finish("hangup")} size="icon" className="rounded-full h-14 w-14 bg-red-600 hover:bg-red-700 border-0"><PhoneOff size={20} /></Button>
      </div>
    </div>
  );
}
