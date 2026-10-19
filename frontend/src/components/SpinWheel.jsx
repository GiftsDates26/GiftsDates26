import React, { useState, useRef } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "./ui/dialog";
import { Button } from "./ui/button";
import { api } from "../lib/api";
import { useApp } from "../context/AppContext";
import { Crown, Sparkles, Coins, Gift, PartyPopper } from "lucide-react";
import confetti from "canvas-confetti";

// 8 sectors — order & indices MUST match backend SPIN_PRIZES
const PRIZES = [
  { label: "Try Again", type: "none" },
  { label: "Premium-Lite", type: "premium_lite" },
  { label: "Try Again", type: "none" },
  { label: "Premium", type: "premium" },
  { label: "Try Again", type: "none" },
  { label: "VIP", type: "vip" },
  { label: "Try Again", type: "none" },
  { label: "10 Coins", type: "coins" },
];
const COLORS = ["#3f3f46", "#38bdf8", "#3f3f46", "#f59e0b", "#3f3f46", "#ef4444", "#3f3f46", "#f59e0b"];
const SEG = 45;
const GRAD = `conic-gradient(from -22.5deg, ${COLORS.map((c, i) => `${c} ${i * SEG}deg ${(i + 1) * SEG}deg`).join(", ")})`;

const TIER_NAME = { premium_lite: "Premium-Lite", premium: "Premium", vip: "VIP" };

const PRIZE_CONFETTI = {
  coins: ["#f59e0b", "#fbbf24", "#fde68a"],
  premium_lite: ["#38bdf8", "#7dd3fc", "#e0f2fe"],
  premium: ["#f59e0b", "#fcd34d", "#fff7ed"],
  vip: ["#ef4444", "#f43f5e", "#fecaca", "#fbbf24"],
};

// Celebratory confetti burst — bigger & longer for higher tiers.
function fireConfetti(type) {
  const colors = PRIZE_CONFETTI[type] || ["#f59e0b", "#f43f5e", "#38bdf8"];
  const big = type === "vip" || type === "premium";
  const end = Date.now() + (big ? 1400 : 800);
  // initial center burst
  confetti({ particleCount: big ? 160 : 90, spread: big ? 100 : 75, startVelocity: 45, origin: { y: 0.6 }, colors, zIndex: 100000 });
  // side cannons streaming for a moment
  (function frame() {
    confetti({ particleCount: 5, angle: 60, spread: 55, origin: { x: 0 }, colors, zIndex: 100000 });
    confetti({ particleCount: 5, angle: 120, spread: 55, origin: { x: 1 }, colors, zIndex: 100000 });
    if (Date.now() < end) requestAnimationFrame(frame);
  })();
}

// Short synthesized "win" chime using the Web Audio API (no external asset).
function playWinChime(ctx, type) {
  if (!ctx) return;
  try {
    if (ctx.state === "suspended") ctx.resume();
    const now = ctx.currentTime;
    // ascending arpeggio; a brighter/longer flourish for top tiers
    const big = type === "vip" || type === "premium";
    const notes = big ? [523.25, 659.25, 783.99, 1046.5, 1318.5] : [523.25, 659.25, 783.99, 1046.5];
    const master = ctx.createGain();
    master.gain.value = 0.0001;
    master.connect(ctx.destination);
    master.gain.setValueAtTime(0.18, now);
    notes.forEach((freq, i) => {
      const t = now + i * 0.11;
      const osc = ctx.createOscillator();
      const g = ctx.createGain();
      osc.type = "triangle";
      osc.frequency.value = freq;
      g.gain.setValueAtTime(0.0001, t);
      g.gain.exponentialRampToValueAtTime(0.22, t + 0.02);
      g.gain.exponentialRampToValueAtTime(0.0001, t + 0.28);
      osc.connect(g).connect(master);
      osc.start(t);
      osc.stop(t + 0.3);
    });
  } catch { /* ignore audio errors */ }
}

function SectorLabel({ p }) {
  return (
    <div className="absolute left-1/2 top-2 -translate-x-1/2 w-16 text-center leading-tight">
      <div className={`font-semibold ${p.label.length > 8 ? "text-[9px]" : "text-[11px]"} text-white drop-shadow`}>
        {p.type === "coins" ? "10 🪙" : p.type === "none" ? "—" : p.label}
      </div>
    </div>
  );
}

/**
 * Controlled one-time welcome wheel.
 * Props:
 *  - open: boolean
 *  - onClose(prizeOrNull): called when user finishes (spun) or dismisses (closed)
 *  - userName: string for the personalized welcome message
 */
export const SpinWheel = ({ open, onClose, userName }) => {
  const { refreshUser } = useApp();
  const [rot, setRot] = useState(0);
  const [spinning, setSpinning] = useState(false);
  const [result, setResult] = useState(null);
  const [done, setDone] = useState(false); // becomes true once a spin has been consumed
  const audioRef = useRef(null);
  const [spinCfg, setSpinCfg] = useState({ dur: 4.2, ease: "cubic-bezier(0.16,1,0.3,1)" });
  const [dramatic, setDramatic] = useState(false); // VIP suspense/glow while spinning

  const doSpin = async () => {
    if (spinning || result) return;
    setSpinning(true);
    // Create/resume the AudioContext inside the click gesture so the delayed
    // win chime is allowed to play by the browser.
    try {
      if (!audioRef.current) {
        const AC = window.AudioContext || window.webkitAudioContext;
        if (AC) audioRef.current = new AC();
      }
      if (audioRef.current?.state === "suspended") audioRef.current.resume();
    } catch { /* audio not available */ }
    try {
      const { data } = await api.post("/spin/claim");
      const p = data.prize;
      // VIP gets a slower, more dramatic finish (more turns + longer, suspenseful ease).
      const isVip = p.type === "vip";
      const turns = isVip ? 11 : 6;
      const dur = isVip ? 7.2 : 4.2;
      const ease = isVip ? "cubic-bezier(0.08,0.72,0.12,1)" : "cubic-bezier(0.16,1,0.3,1)";
      const target = 360 * turns + (360 - (p.index || 0) * SEG);
      setSpinCfg({ dur, ease });
      setDramatic(isVip);
      setRot(target);
      setTimeout(async () => {
        setResult(p);
        setDone(true);
        setSpinning(false);
        setDramatic(false);
        if (p.type === "none") {
          fireConfetti("coins");
          playWinChime(audioRef.current, "coins");
        } else if (p.type) {
          fireConfetti(p.type);
          playWinChime(audioRef.current, p.type);
          // VIP gets a second golden shower for extra drama.
          if (isVip) {
            setTimeout(() => fireConfetti("vip"), 700);
            setTimeout(() => fireConfetti("vip"), 1500);
          }
        }
        await refreshUser();
      }, dur * 1000 + 120);
    } catch (e) {
      setSpinning(false);
      setDramatic(false);
      setDone(true); // if backend says already used, don't allow retry
    }
  };

  const finish = () => { onClose && onClose(result); };

  // Dismissing (X or overlay) before spinning permanently disables the wheel.
  const handleOpenChange = async (o) => {
    if (o) return;
    if (!done && !spinning) {
      try { await api.post("/spin/dismiss"); } catch { /* ignore */ }
      await refreshUser();
    }
    onClose && onClose(result);
  };

  const welcome = () => {
    const first = (userName || "").trim().replace(/[,!.]+$/, "");
    if (!result) return "";
    if (result.type === "coins") {
      return `Congratulations${first ? ", " + first : ""}! You won 10 Coins — they've been added to your wallet.`;
    }
    if (TIER_NAME[result.type]) {
      return `Congratulations${first ? ", " + first : ""}! You won a 7-day ${TIER_NAME[result.type]} account!`;
    }
    return `Welcome to GiftsDates${first ? ", " + first : ""}! Here are 5 Coins to get you started — added to your wallet.`;
  };

  const ResultIcon = result?.type === "coins" ? Coins
    : result?.type === "vip" ? Crown
    : result?.type === "premium" ? Crown
    : result?.type === "premium_lite" ? Sparkles
    : result?.type === "none" ? Coins
    : PartyPopper;

  const isWin = result && (result.type !== "none" || result.coins);
  const bigWin = result && result.type === "vip";

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="bg-[#141019] border-white/10 text-white sm:max-w-md" data-testid="spin-dialog">
        <DialogHeader>
          <DialogTitle className="font-serif-luxe text-2xl flex items-center gap-2">
            <Sparkles size={20} className="text-amber-300" /> Spin to Win — Welcome Gift
          </DialogTitle>
        </DialogHeader>
        <p className="text-sm text-slate-400 -mt-1">One free spin, just for joining. Good luck!</p>

        <div className="relative mx-auto my-4" style={{ width: 300, height: 300 }} data-testid="spin-wheel">
          <div className="absolute left-1/2 -translate-x-1/2 -top-1 z-20"
            style={{ width: 0, height: 0, borderLeft: "14px solid transparent", borderRight: "14px solid transparent", borderTop: "22px solid #fbbf24" }} />
          <div className={`absolute inset-0 rounded-full border-4 border-amber-400/60 shadow-[0_0_40px_rgba(245,158,11,0.35)] pointer-events-none ${dramatic ? "vip-glow" : ""}`}
            style={{ background: GRAD, transform: `rotate(${rot}deg)`, transition: `transform ${spinCfg.dur}s ${spinCfg.ease}` }}>
            {PRIZES.map((p, i) => (
              <div key={i} className="absolute inset-0" style={{ transform: `rotate(${i * SEG}deg)` }}>
                <SectorLabel p={p} />
              </div>
            ))}
          </div>
          <div className={`absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-12 h-12 rounded-full bg-[#141019] border-4 border-amber-400/70 z-10 flex items-center justify-center ${dramatic ? "vip-crown-pop" : ""}`}>
            <Crown size={18} className="text-amber-300" />
          </div>
        </div>

        {!result ? (
          <Button data-testid="spin-go-btn" onClick={doSpin} disabled={spinning}
            className="w-full rose-btn text-white border-0 h-12 text-base">
            <Gift size={18} className="me-2" /> {spinning ? "Spinning…" : "Spin the Wheel"}
          </Button>
        ) : (
          <div data-testid="spin-result" className="text-center space-y-3">
            <div className={`rounded-2xl border p-4 ${bigWin ? "vip-shimmer-card border-amber-400/70 bg-gradient-to-b from-amber-500/20 to-rose-500/10 shadow-[0_0_50px_-8px_rgba(245,158,11,0.7)]" : isWin ? "border-amber-500/40 bg-amber-500/10" : "border-white/10 bg-white/5"}`}>
              {bigWin && (
                <div className="text-[10px] font-bold uppercase tracking-[0.25em] text-amber-300 mb-1" data-testid="spin-vip-tag">
                  ✦ VIP Jackpot ✦
                </div>
              )}
              <div className="flex justify-center mb-2"><ResultIcon size={bigWin ? 38 : 30} className={bigWin ? "text-amber-300 drop-shadow-[0_0_10px_rgba(245,158,11,0.9)]" : isWin ? "text-amber-300" : "text-slate-300"} /></div>
              <div className={`font-serif-luxe leading-snug ${bigWin ? "text-2xl gold-text" : "text-xl"}`}>{welcome()}</div>
              {result.expires_at && (
                <div className="text-xs text-emerald-300 mt-2" data-testid="spin-expiry">
                  Expires on {new Date(result.expires_at).toLocaleString()}
                </div>
              )}
            </div>
            <Button data-testid="spin-continue-btn" onClick={finish} className="w-full rose-btn text-white border-0 h-12 text-base">
              Continue
            </Button>
          </div>
        )}
        <p className="text-center text-[11px] text-slate-500">This welcome spin can only be used once.</p>
      </DialogContent>
    </Dialog>
  );
};

export default SpinWheel;
