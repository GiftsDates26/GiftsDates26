import React from "react";
import { VideoOff, RefreshCw } from "lucide-react";
import { Button } from "./ui/button";

// Shown when a member hasn't allowed their camera/microphone. Calls cannot start or be accepted without it.
export default function CameraBlocked({ message, onRetry, onCancel, retrying, cancelLabel = "Cancel" }) {
  return (
    <div data-testid="camera-blocked" className="p-6 text-center space-y-4">
      <div className="w-16 h-16 mx-auto rounded-2xl bg-rose-500/15 border border-rose-500/40 flex items-center justify-center text-rose-300"><VideoOff size={28} /></div>
      <div className="font-serif-luxe text-2xl">Allow your camera to continue</div>
      <p className="text-sm text-slate-300 max-w-sm mx-auto leading-relaxed" data-testid="camera-blocked-message">{message}</p>
      <p className="text-xs text-slate-500">Video calls on GiftsDates always need both members' camera and microphone. No coins are charged.</p>
      <div className="flex justify-center gap-2 pt-1">
        <Button data-testid="camera-retry-button" onClick={onRetry} disabled={retrying} className="rose-btn text-white border-0"><RefreshCw size={15} className={`me-1 ${retrying ? "animate-spin" : ""}`} />Try again</Button>
        <Button data-testid="camera-cancel-button" variant="outline" onClick={onCancel} className="bg-white/5 border-white/15">{cancelLabel}</Button>
      </div>
    </div>
  );
}
