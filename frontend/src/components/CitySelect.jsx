import React, { useState } from "react";
import { Check, ChevronsUpDown, MapPin } from "lucide-react";
import { Popover, PopoverContent, PopoverTrigger } from "./ui/popover";
import { Command, CommandGroup, CommandInput, CommandItem, CommandList } from "./ui/command";
import { Button } from "./ui/button";
import { citiesForCountry } from "../lib/cities";
import { t } from "../lib/i18n";

// Searchable city dropdown whose options depend on the chosen country.
// If the typed city isn't in the list, the user can still add it as a custom entry.
export default function CitySelect({ value, onChange, country, lang, testid = "city-select", required = false }) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const cities = citiesForCountry(country);
  const noCountry = !country;

  const q = query.trim().toLowerCase();
  const filtered = q ? cities.filter((c) => c.toLowerCase().includes(q)) : cities;
  const exactMatch = cities.some((c) => c.toLowerCase() === q);
  const showCustom = query.trim().length > 0 && !exactMatch;

  const pick = (city) => {
    onChange(city);
    setOpen(false);
    setQuery("");
  };

  return (
    <Popover open={open} onOpenChange={(o) => { if (!noCountry) setOpen(o); }}>
      <PopoverTrigger asChild>
        <Button
          data-testid={testid}
          type="button"
          variant="outline"
          role="combobox"
          aria-expanded={open}
          disabled={noCountry}
          className="w-full justify-between bg-white/5 border-white/10 mt-1 h-10 font-normal hover:bg-white/10 disabled:opacity-60"
        >
          <span className={`flex items-center gap-2 truncate ${value ? "text-white" : "text-slate-400"}`}>
            <MapPin size={15} className={value ? "text-rose-400" : "text-slate-400"} />
            {value ? value : (noCountry ? t("choose_country_first", lang) : t("choose_city", lang))}
          </span>
          <ChevronsUpDown size={15} className="ms-2 shrink-0 opacity-50" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="p-0 bg-[#161320] border-white/10 text-white w-[--radix-popover-trigger-width] min-w-[240px]" align="start">
        <Command className="bg-transparent" shouldFilter={false}>
          <CommandInput
            data-testid={`${testid}-search`}
            value={query}
            onValueChange={setQuery}
            placeholder={t("search_city", lang)}
            className="text-white"
          />
          <CommandList>
            <CommandGroup>
              {filtered.map((c) => (
                <CommandItem
                  key={c}
                  value={c}
                  data-testid={`${testid}-option-${c}`}
                  onSelect={() => pick(c)}
                  className="text-white aria-selected:bg-white/10 cursor-pointer"
                >
                  <MapPin size={14} className="me-2 text-slate-400" />
                  <span className="flex-1">{c}</span>
                  {value === c && <Check size={15} className="ms-auto text-rose-400" />}
                </CommandItem>
              ))}
              {showCustom && (
                <CommandItem
                  value={`__custom_${query}`}
                  data-testid={`${testid}-custom`}
                  onSelect={() => pick(query.trim())}
                  className="text-sky-200 aria-selected:bg-white/10 cursor-pointer"
                >
                  <MapPin size={14} className="me-2 text-sky-300" />
                  <span className="flex-1">{t("use_city", lang)} "{query.trim()}"</span>
                </CommandItem>
              )}
              {filtered.length === 0 && !showCustom && (
                <div className="px-3 py-4 text-sm text-slate-400 text-center">{t("no_results", lang)}</div>
              )}
            </CommandGroup>
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
}
