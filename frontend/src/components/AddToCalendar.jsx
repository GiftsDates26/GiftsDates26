import React from "react";
import { CalendarPlus, Download } from "lucide-react";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel, DropdownMenuSeparator, DropdownMenuTrigger } from "./ui/dropdown-menu";
import { useApp } from "../context/AppContext";
import { t } from "../lib/i18n";

const REMINDERS = [1440, 120, 30]; // minutes before the date
const fmt = (dt) => dt.toISOString().replace(/[-:]/g, "").replace(/\.\d{3}/, "");
const esc = (x) => (x || "").replace(/([,;\\])/g, "\\$1").replace(/\n/g, "\\n");
const remLabel = (m) => (m >= 1440 ? `${m / 1440} day` : m >= 60 ? `${m / 60} hours` : `${m} min`);

const details = (link) => `Your GiftsDates date.\nReminders: ${REMINDERS.map(remLabel).join(", ")} before.\nOpen in the app: ${link}`;

const googleUrl = ({ title, place, start, end, link }) =>
  `https://calendar.google.com/calendar/render?${new URLSearchParams({ action: "TEMPLATE", text: title, dates: `${fmt(start)}/${fmt(end)}`, details: details(link), location: place || "" })}`;

const downloadIcs = ({ id, title, place, start, end, link }) => {
  const alarms = REMINDERS.flatMap(m => ["BEGIN:VALARM", "ACTION:DISPLAY", `DESCRIPTION:${esc(title)}`, `TRIGGER:-PT${m}M`, "END:VALARM"]);
  const ics = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//GiftsDates//EN", "CALSCALE:GREGORIAN", "METHOD:PUBLISH", "BEGIN:VEVENT",
    `UID:${id}@giftsdates`, `DTSTAMP:${fmt(new Date())}`, `DTSTART:${fmt(start)}`, `DTEND:${fmt(end)}`, `SUMMARY:${esc(title)}`,
    `LOCATION:${esc(place)}`, `DESCRIPTION:${esc(details(link))}`, `URL:${link}`, ...alarms, "END:VEVENT", "END:VCALENDAR"].join("\r\n");
  const url = URL.createObjectURL(new Blob([ics], { type: "text/calendar;charset=utf-8" }));
  const a = document.createElement("a"); a.href = url; a.download = `giftsdates-${id}.ics`; a.click(); URL.revokeObjectURL(url);
};

export default function AddToCalendar({ id, title, place, start, end, link = "/dates" }) {
  const { lang } = useApp();
  if (!start || isNaN(start)) return null;
  const ev = { id, title, place, start, end: end || new Date(start.getTime() + 150 * 60000), link: `${window.location.origin}${link}` };
  return (
    <DropdownMenu>
      <DropdownMenuTrigger data-testid={`add-to-calendar-${id}`}
        className="inline-flex items-center whitespace-nowrap h-9 px-3 rounded-md text-sm bg-emerald-500/10 border border-emerald-500/40 text-emerald-200 hover:bg-emerald-500/20 transition-colors">
        <CalendarPlus size={14} className="me-1.5" />{t("cal_add", lang)}
      </DropdownMenuTrigger>
      <DropdownMenuContent className="bg-[#161320] border-white/10 text-white w-64" data-testid={`add-to-calendar-menu-${id}`}>
        <DropdownMenuLabel className="text-[11px] text-slate-400 font-normal">{t("cal_reminders_note", lang)}</DropdownMenuLabel>
        <DropdownMenuSeparator className="bg-white/10" />
        <DropdownMenuItem asChild className="cursor-pointer focus:bg-white/10 focus:text-white">
          <a href={googleUrl(ev)} target="_blank" rel="noreferrer" data-testid={`cal-google-${id}`}><CalendarPlus size={14} className="me-2" />{t("id_cal_google", lang)}</a>
        </DropdownMenuItem>
        <DropdownMenuItem onSelect={() => downloadIcs(ev)} className="cursor-pointer focus:bg-white/10 focus:text-white" data-testid={`cal-ics-${id}`}>
          <Download size={14} className="me-2" />{t("cal_ics_reminders", lang)}
        </DropdownMenuItem>
        <DropdownMenuItem onSelect={() => downloadIcs(ev)} className="cursor-pointer focus:bg-white/10 focus:text-white" data-testid={`cal-apple-${id}`}>
          <CalendarPlus size={14} className="me-2" />{t("cal_apple", lang)}
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
