import React from "react";
import { Navigation } from "lucide-react";
import { useApp } from "../context/AppContext";
import { t } from "../lib/i18n";

export const directionsUrl = (loc = {}) => {
  const dest = loc.lat != null && loc.lng != null ? `${loc.lat},${loc.lng}` : [loc.venue, loc.address, loc.postal_code, loc.city, loc.country].filter(Boolean).join(", ");
  return dest ? `https://www.google.com/maps/dir/?api=1&destination=${encodeURIComponent(dest)}` : null;
};

export default function DirectionsButton({ loc, testid }) {
  const { lang } = useApp();
  const url = directionsUrl(loc);
  if (!url) return null;
  return (
    <a href={url} target="_blank" rel="noreferrer" data-testid={testid}
      className="inline-flex items-center h-9 px-3 rounded-md text-sm bg-sky-500/10 border border-sky-500/40 text-sky-200 hover:bg-sky-500/20 transition-colors">
      <Navigation size={14} className="me-1.5" />{t("dir_btn", lang)}
    </a>
  );
}
