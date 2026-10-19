import React from "react";
import { Globe, X } from "lucide-react";
import { useApp } from "../context/AppContext";
import { LANGUAGES } from "../lib/i18n";
import { Button } from "./ui/button";

// Shown once when the site was opened automatically in the visitor's browser language.
export default function DetectedLanguageBanner() {
  const { lang, langDetected, setLanguage, dismissLangBanner } = useApp();
  if (!langDetected || lang === "en") return null;
  const cur = LANGUAGES.find(l => l.code === lang);
  if (!cur) return null;
  const openPicker = () => { dismissLangBanner(); window.dispatchEvent(new Event("gd-open-language-picker")); };
  return (
    <div data-testid="detected-language-banner" className="fixed z-[60] bottom-5 start-5 max-w-[360px] glass-strong rounded-2xl border border-[#D4AF37]/30 shadow-2xl shadow-black/50 p-4 lang-banner-in">
      <button type="button" aria-label="Close" data-testid="detected-language-close" onClick={() => setLanguage(lang)} className="absolute top-2.5 end-2.5 text-slate-400 hover:text-white transition-colors"><X size={15} /></button>
      <div className="flex items-start gap-3 pe-5">
        <div className="w-9 h-9 shrink-0 rounded-xl bg-[#D4AF37]/10 border border-[#D4AF37]/30 flex items-center justify-center text-[#D4AF37]"><Globe size={17} /></div>
        <div className="text-sm text-slate-200 leading-snug">
          <div className="font-semibold text-white flex items-center gap-1.5"><span translate="no">{cur.flag}</span> <span translate="no">{cur.name}</span></div>
          <div className="text-xs text-slate-400 mt-0.5">We opened GiftsDates in your browser language.</div>
        </div>
      </div>
      <div className="flex flex-wrap gap-2 mt-3">
        <Button size="sm" data-testid="detected-language-keep" onClick={() => setLanguage(lang)} className="rose-btn text-white border-0 h-8">Keep</Button>
        <Button size="sm" variant="outline" data-testid="detected-language-english" onClick={() => setLanguage("en")} className="h-8 bg-white/5 border-white/15 text-slate-100 hover:bg-white/10"><span translate="no">🇺🇸 English</span></Button>
        <Button size="sm" variant="ghost" data-testid="detected-language-other" onClick={openPicker} className="h-8 text-[#D4AF37] hover:text-[#f3e5ab] hover:bg-[#D4AF37]/10">Other language</Button>
      </div>
    </div>
  );
}
