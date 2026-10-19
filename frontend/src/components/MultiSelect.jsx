import React, { useState } from "react";
import { Check, ChevronsUpDown, X } from "lucide-react";
import { Popover, PopoverContent, PopoverTrigger } from "./ui/popover";
import { Command, CommandGroup, CommandInput, CommandItem, CommandList, CommandSeparator } from "./ui/command";
import { Button } from "./ui/button";
import { Badge } from "./ui/badge";

// Reusable multi-select dropdown: choose as many options as you want.
// Accepts either `options` (flat) or `groups` ([{label, options:[{value,label}]}]).
// `accent` controls the highlight colour ("amber" | "rose").
export default function MultiSelect({
  value = [],
  onChange,
  options,
  groups,
  placeholder = "Select…",
  searchPlaceholder = "Search…",
  emptyText = "No results",
  accent = "amber",
  testid = "multi-select",
}) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");

  const allGroups = groups || [{ label: null, options: options || [] }];
  const flat = allGroups.flatMap((g) => g.options);
  const labelOf = (val) => flat.find((o) => o.value === val)?.label || val;

  const accentChip = accent === "rose"
    ? "bg-rose-500/20 border-rose-500/50 text-rose-200"
    : "bg-amber-500/20 border-amber-500/50 text-amber-200";
  const accentCheck = accent === "rose" ? "text-rose-300" : "text-amber-300";

  const toggle = (val) => {
    onChange(value.includes(val) ? value.filter((v) => v !== val) : [...value, val]);
  };
  const remove = (e, val) => { e.stopPropagation(); onChange(value.filter((v) => v !== val)); };

  const q = query.trim().toLowerCase();
  const filterOpts = (opts) => (q ? opts.filter((o) => o.label.toLowerCase().includes(q)) : opts);
  const hasResults = allGroups.some((g) => filterOpts(g.options).length > 0);

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          data-testid={testid}
          type="button"
          variant="outline"
          role="combobox"
          aria-expanded={open}
          className="w-full min-h-10 h-auto justify-between bg-white/5 border-white/10 font-normal hover:bg-white/10 py-2"
        >
          <span className="flex flex-wrap gap-1.5 items-center text-left">
            {value.length === 0 && <span className="text-slate-400">{placeholder}</span>}
            {value.map((val) => (
              <Badge
                key={val}
                data-testid={`${testid}-chip-${val}`}
                variant="outline"
                className={`gap-1 rounded-full px-2 py-0.5 text-xs font-normal ${accentChip}`}
              >
                {labelOf(val)}
                <span onClick={(e) => remove(e, val)} className="cursor-pointer hover:opacity-80" data-testid={`${testid}-remove-${val}`}>
                  <X size={11} />
                </span>
              </Badge>
            ))}
          </span>
          <ChevronsUpDown size={15} className="ms-2 shrink-0 opacity-50 self-start mt-1" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="p-0 bg-[#161320] border-white/10 text-white w-[--radix-popover-trigger-width] min-w-[260px]" align="start">
        <Command className="bg-transparent" shouldFilter={false}>
          <CommandInput value={query} onValueChange={setQuery} placeholder={searchPlaceholder} className="text-white" data-testid={`${testid}-search`} />
          <CommandList>
            {!hasResults && <div className="px-3 py-4 text-sm text-slate-400 text-center">{emptyText}</div>}
            {allGroups.map((g, gi) => {
              const opts = filterOpts(g.options);
              if (opts.length === 0) return null;
              return (
                <React.Fragment key={g.label || gi}>
                  {gi > 0 && <CommandSeparator className="bg-white/10" />}
                  <CommandGroup heading={g.label || undefined} className="text-slate-400 [&_[cmdk-group-heading]]:text-amber-200/70">
                    {opts.map((o) => {
                      const selected = value.includes(o.value);
                      return (
                        <CommandItem
                          key={o.value}
                          value={o.value}
                          data-testid={`${testid}-option-${o.value}`}
                          onSelect={() => toggle(o.value)}
                          className="text-white aria-selected:bg-white/10 cursor-pointer"
                        >
                          <span className={`me-2 flex h-4 w-4 items-center justify-center rounded border ${selected ? `${accentChip} border` : "border-white/25"}`}>
                            {selected && <Check size={12} className={accentCheck} />}
                          </span>
                          <span className="flex-1">{o.label}</span>
                        </CommandItem>
                      );
                    })}
                  </CommandGroup>
                </React.Fragment>
              );
            })}
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
}
