import React from "react";
import { useApp } from "../context/AppContext";
import { t } from "../lib/i18n";
import DateBookingList from "../components/DateBookingList";
import CancelledDates from "../components/CancelledDates";

export default function Dates() {
  const { lang } = useApp();
  return (
    <div className="aurora-bg min-h-[calc(100vh-4rem)]">
      <div className="max-w-5xl mx-auto px-4 py-10 space-y-8">
        <h1 className="font-serif-luxe text-4xl">{t("dates", lang)}</h1>
        <p className="text-xs text-slate-400 -mt-4">{t("photo_hint", lang)}</p>
        <DateBookingList mode="regular" />
        <CancelledDates />
      </div>
    </div>
  );
}
