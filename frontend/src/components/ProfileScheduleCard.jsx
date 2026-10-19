import React, { useEffect, useState } from "react";
import { CalendarClock } from "lucide-react";
import { Button } from "./ui/button";
import { api } from "../lib/api";
import { useApp } from "../context/AppContext";
import VipDateBookModal from "./VipDateBookModal";

// Standalone booking entry for a VIP's availability calendar.
// Rendered independently of the private VIP section lock so ANY member can
// request an exact time slot from a VIP who has published availability.
export default function ProfileScheduleCard({ profile }) {
  const { user } = useApp();
  const [days, setDays] = useState(null); // null=loading, []=none
  const [open, setOpen] = useState(false);

  const isOwn = user?.id === profile?.id;

  useEffect(() => {
    if (!profile?.id || isOwn) { setDays([]); return; }
    api.get(`/vip/schedule/${profile.id}/slots`)
      .then((r) => setDays(r.data.days || []))
      .catch(() => setDays([]));
  }, [profile, isOwn]);

  if (isOwn || !days || days.length === 0) return null;

  const freeCount = days.reduce((n, d) => n + (d.slots || []).filter((s) => s.state === "available").length, 0);

  return (
    <div className="mt-6 glass rounded-2xl p-6 border border-amber-500/25" data-testid="profile-schedule-card">
      <div className="flex flex-col sm:flex-row sm:items-center gap-4 justify-between">
        <div className="flex items-start gap-3">
          <div className="w-11 h-11 rounded-xl bg-amber-500/15 border border-amber-500/30 flex items-center justify-center shrink-0">
            <CalendarClock size={20} className="text-amber-300" />
          </div>
          <div>
            <h3 className="font-serif-luxe text-xl gold-text">Availability calendar</h3>
            <p className="text-sm text-slate-400 mt-0.5">
              Pick an exact time slot from {profile.name}'s calendar. A 15-minute buffer is protected around every date.
            </p>
            <p className="text-xs text-emerald-300 mt-1">{freeCount} open slot{freeCount === 1 ? "" : "s"} across {days.length} day{days.length === 1 ? "" : "s"}</p>
          </div>
        </div>
        <Button data-testid="profile-open-schedule" onClick={() => setOpen(true)} className="rose-btn text-white border-0 shrink-0">
          <CalendarClock size={16} className="me-1.5" /> Book from calendar
        </Button>
      </div>

      <VipDateBookModal
        open={open}
        onOpenChange={setOpen}
        target={{ id: profile.id, name: profile.name, city: profile.city }}
      />
    </div>
  );
}
