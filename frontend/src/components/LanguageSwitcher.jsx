import React from "react";
import { Check, ChevronDown, Globe, Loader2 } from "lucide-react";
import { LANGUAGES } from "../lib/i18n";
import { useApp } from "../context/AppContext";
import { onTranslatingChange } from "../lib/autoTranslate";
import { Popover, PopoverContent, PopoverTrigger } from "./ui/popover";
import { Command, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList } from "./ui/command";

const POPULAR = ["en", "es", "fr", "de", "pt", "ru", "zh", "ar", "hi", "ja", "ko", "it", "tr", "uk", "pl"];

function LangRow({ l, active }) {
  return (
    <span className="flex items-center gap-2.5 w-full" translate="no">
      <span className="text-lg leading-none w-6 text-center">{l.flag}</span>
      <span className="flex-1 min-w-0">
        <span className="block text-sm text-slate-100 truncate">{l.name}</span>
        {l.englishName && l.englishName !== l.name && <span className="block text-[11px] text-slate-400 truncate">{l.englishName}</span>}
      </span>
      {active && <Check size={14} className="text-rose-400 shrink-0" />}
    </span>
  );
}

export default function LanguageSwitcher({ className = "" }) {
  const { lang, setLanguage } = useApp();
  const [open, setOpen] = React.useState(false);
  const [busy, setBusy] = React.useState(false);
  React.useEffect(() => onTranslatingChange(setBusy), []);
  React.useEffect(() => {
    const openIt = () => setOpen(true);
    window.addEventListener("gd-open-language-picker", openIt);
    return () => window.removeEventListener("gd-open-language-picker", openIt);
  }, []);
  const current = LANGUAGES.find(l => l.code === lang) || LANGUAGES[0];
  const popular = POPULAR.map(c => LANGUAGES.find(l => l.code === c)).filter(Boolean);
  const all = [...LANGUAGES].sort((a, b) => (a.englishName || a.name).localeCompare(b.englishName || b.name));

  const pick = (code) => { setLanguage(code); setOpen(false); };

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <button
          type="button"
          data-testid="nav-language-switcher-select"
          aria-label="Language"
          className={`flex items-center gap-2 h-10 px-3 rounded-md bg-white/5 border border-white/10 hover:bg-white/10 hover:border-[#D4AF37]/40 text-slate-100 transition-colors ${className}`}
        >
          <span className="text-lg leading-none" translate="no">{current.flag}</span>
          <span className="hidden sm:inline text-sm max-w-[110px] truncate" translate="no">{current.name}</span>
          {busy ? <Loader2 size={14} className="animate-spin text-[#D4AF37]" data-testid="lang-translating-indicator" /> : <ChevronDown size={14} className="text-slate-400" />}
        </button>
      </PopoverTrigger>
      <PopoverContent align="end" className="w-[300px] p-0 bg-[#161320] border-white/10 text-slate-100" data-testid="lang-popover">
        <Command
          className="bg-transparent text-slate-100"
          filter={(value, search) => (value.toLowerCase().includes(search.toLowerCase()) ? 1 : 0)}
        >
          <div className="px-3 pt-3 pb-1 flex items-center gap-2 text-xs text-[#D4AF37]">
            <Globe size={13} /> <span>{LANGUAGES.length} languages · auto-translated</span>
          </div>
          <CommandInput data-testid="lang-search-input" placeholder="Search language…" className="text-slate-100 placeholder:text-slate-500" />
          <CommandList className="max-h-[360px]">
            <CommandEmpty className="py-6 text-center text-sm text-slate-400">No language found.</CommandEmpty>
            <CommandGroup heading="Popular" className="[&_[cmdk-group-heading]]:text-slate-500">
              {popular.map(l => (
                <CommandItem key={`p-${l.code}`} value={`popular ${l.code} ${l.name} ${l.englishName}`} onSelect={() => pick(l.code)}
                  data-testid={`lang-option-${l.code}`} className="cursor-pointer data-[selected=true]:bg-rose-500/20 data-[selected=true]:text-white">
                  <LangRow l={l} active={l.code === lang} />
                </CommandItem>
              ))}
            </CommandGroup>
            <CommandGroup heading="All languages" className="[&_[cmdk-group-heading]]:text-slate-500">
              {all.map(l => (
                <CommandItem key={l.code} value={`${l.code} ${l.name} ${l.englishName}`} onSelect={() => pick(l.code)}
                  data-testid={`lang-all-option-${l.code}`} className="cursor-pointer data-[selected=true]:bg-rose-500/20 data-[selected=true]:text-white">
                  <LangRow l={l} active={l.code === lang} />
                </CommandItem>
              ))}
            </CommandGroup>
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
}
