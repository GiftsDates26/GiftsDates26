import React, { useState } from "react";
import { Crown, Gift } from "lucide-react";
import { toast } from "sonner";
import { useNavigate } from "react-router-dom";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "./ui/dialog";
import { Button } from "./ui/button";
import { api } from "../lib/api";
import { useApp } from "../context/AppContext";
import { t } from "../lib/i18n";

export const GiftPremiumModal = ({ open, onOpenChange, target }) => {
  const { user, refreshUser, lang } = useApp();
  const nav = useNavigate();
  const [busy, setBusy] = useState(false);
  const avail = (user?.coins || 0) + (user?.withdrawable || 0);

  const gift = async (tier) => {
    const cost = tier === "vip" ? 500 : tier === "premium_lite" ? 150 : 300;
    if (avail < cost) { toast.error(t("not_enough_coins", lang), { action: { label: t("topup", lang), onClick: () => nav("/wallet") } }); return; }
    setBusy(true);
    try {
      await api.post("/premium/gift", { target_id: target.id, tier });
      const tierName = tier === "vip" ? "VIP Premium" : tier === "premium_lite" ? t("premium_lite", lang) : "Premium";
      toast.success(t("gift_sent", lang).replace("{tier}", tierName).replace("{name}", target.name));
      await refreshUser();
      onOpenChange(false);
    } catch (e) { toast.error(e.response?.data?.detail || t("failed", lang)); } finally { setBusy(false); }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="bg-[#161018] border-white/10 text-white max-w-sm" data-testid="gift-premium-modal">
        <DialogHeader><DialogTitle className="font-serif-luxe text-2xl gold-text flex items-center gap-2"><Gift size={20} className="text-rose-400" /> {t("gift_premium", lang)} · {target?.name}</DialogTitle></DialogHeader>
        <p className="text-sm text-slate-400">{t("gift_premium_desc", lang)} (🪙 {avail}).</p>
        <Button data-testid="gift-premium-lite-30" onClick={() => gift("premium_lite")} disabled={busy} variant="outline" className="bg-sky-500/10 border-sky-500/40 text-sky-200 h-12 justify-between px-4">
          <span className="flex items-center gap-2"><Crown size={16} className="fill-sky-500 text-sky-400" /> {t("premium_lite", lang)} · {t("days_30", lang)}</span><span className="font-mono-num">🪙 150</span>
        </Button>
        <Button data-testid="gift-premium-30" onClick={() => gift("premium")} disabled={busy} className="rose-btn text-white border-0 h-12 justify-between px-4">
          <span className="flex items-center gap-2"><Crown size={16} /> Premium · {t("days_30", lang)}</span><span className="font-mono-num">🪙 300</span>
        </Button>
        <Button data-testid="gift-vip-30" onClick={() => gift("vip")} disabled={busy} variant="outline" className="bg-rose-500/10 border-rose-500/40 text-rose-200 h-12 justify-between px-4">
          <span className="flex items-center gap-2"><Crown size={16} className="fill-rose-500 text-rose-400" /> VIP Premium · {t("days_30", lang)}</span><span className="font-mono-num">🪙 500</span>
        </Button>
      </DialogContent>
    </Dialog>
  );
};

export default GiftPremiumModal;
