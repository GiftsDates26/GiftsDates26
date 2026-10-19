import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Sparkles } from "lucide-react";
import { api } from "../lib/api";
import { useApp } from "../context/AppContext";
import SpinWheel from "../components/SpinWheel";

export default function SpinPage() {
  const { user } = useApp();
  const nav = useNavigate();
  const [status, setStatus] = useState(null);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    api.get("/spin/status")
      .then((r) => { setStatus(r.data); setOpen(!!r.data.eligible); })
      .catch(() => setStatus({ eligible: false }));
  }, []);

  return (
    <div className="aurora-bg min-h-[calc(100vh-4rem)]">
      <div className="max-w-lg mx-auto px-4 py-12 text-center" data-testid="spin-page">
        <h1 className="font-serif-luxe text-4xl flex items-center justify-center gap-2">
          <Sparkles className="text-amber-300" /> Spin to Win
        </h1>
        {status && !status.eligible && (
          <div className="mt-8 rounded-2xl border border-white/10 bg-white/5 p-6 text-slate-300" data-testid="spin-not-eligible">
            Your one-time welcome spin has already been used. Explore profiles and enjoy GiftsDates!
          </div>
        )}
      </div>

      <SpinWheel
        open={open}
        userName={user?.name}
        onClose={() => { setOpen(false); nav("/browse"); }}
      />
    </div>
  );
}
