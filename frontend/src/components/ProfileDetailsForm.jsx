import React from "react";
import { Input } from "./ui/input";
import { Label } from "./ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "./ui/select";
import { DropdownMenu, DropdownMenuTrigger, DropdownMenuContent, DropdownMenuCheckboxItem } from "./ui/dropdown-menu";
import { ChevronDown } from "lucide-react";
import MultiSelect from "./MultiSelect";
import { SPOKEN_LANGUAGES, t } from "../lib/i18n";
import { HOBBY_SELECT_GROUPS, HOBBY_MAX } from "../lib/hobbies";
import { toast } from "sonner";

export const INTENTS = ["serious", "marriage", "casual", "just_sex", "friendship", "travel", "sponsor", "giftsdates"];
export const INCOMES = ["custom", "prefer_not"];
export const KIDS = ["none", "have", "want", "no_want"];
export const HABITS = ["never", "sometimes", "often"];
export const RELIGIONS = ["christian", "muslim", "jewish", "buddhist", "hindu", "spiritual", "atheist", "other", "prefer_not"];
export const BUST = ["AA", "A", "B", "C", "D", "DD", "E", "F", "G", "H+"];
export const BUST_TYPE = ["natural", "enhanced"];
export const DICK_GIRTHS = ["Slim", "Average", "Thick", "Very thick"];
export const SIZES = ["s", "m", "l", "xl"];

export const GENDERS = ["female", "male", "trans_woman", "trans_man", "non_binary", "transgender", "transfeminine", "transmasculine", "cis_woman", "cis_man", "agender", "genderqueer", "genderfluid", "genderless", "gender_nonconforming", "gender_questioning", "bigender", "pangender", "demigender", "demigirl", "demiboy", "two_spirit", "intersex", "androgyne", "androgynous", "neutrois", "gender_variant", "third_gender", "polygender", "omnigender", "transsexual", "questioning", "other_gender", "prefer_not_gender"];
export const ORIENTATIONS = ["straight", "gay", "lesbian", "bisexual", "pansexual", "omnisexual", "polysexual", "asexual", "demisexual", "sapiosexual", "aromantic", "transgender", "queer", "fluid", "questioning", "prefer_not"];
export const genderLabel = (g, lang) => t(g, lang);

export const optLabel = (field, v, lang) => {
  if (!v) return "";
  if (v === "prefer_not") return t("prefer_not", lang);
  if (field === "income" && v === "custom") return `${t("income_custom_value", lang)} ($/month)`;
  if (field === "gender") return t(v, lang);
  const prefix = { relationship_intent: "intent_", income: "income_", kids: "kids_", smoking: "habit_", drinking: "habit_", religion: "rel_", penis_size: "size_", orientation: "or_", bust_type: "bust_" }[field];
  return prefix ? t(prefix + v, lang) : v;
};

const NONE = "__none";
export function Field({ label, children }) {
  return <div><Label className="text-xs text-slate-400">{label}</Label>{children}</div>;
}
export function Sel({ testid, field, value, options, onChange, lang }) {
  return (
    <Select value={value || NONE} onValueChange={v => onChange(v === NONE ? "" : v)}>
      <SelectTrigger data-testid={testid} className="bg-white/5 border-white/10 mt-1"><SelectValue /></SelectTrigger>
      <SelectContent className="bg-[#161320] border-white/10 text-white max-h-72">
        <SelectItem value={NONE}>{t("not_specified", lang)}</SelectItem>
        {options.map(o => <SelectItem key={o} value={o}>{optLabel(field, o, lang)}</SelectItem>)}
      </SelectContent>
    </Select>
  );
}

export default function ProfileDetailsForm({ f, setF, lang, gender }) {
  const set = (k) => (v) => setF({ ...f, [k]: v });
  const intents = Array.isArray(f.relationship_intent) ? f.relationship_intent : (f.relationship_intent ? [f.relationship_intent] : []);
  const toggleIntent = (v) => {
    set("relationship_intent")(intents.includes(v) ? intents.filter(x => x !== v) : [...intents, v]);
  };
  return (
    <>
      <div className="glass rounded-2xl p-6 space-y-4 mb-6" data-testid="profile-details-section">
        <h2 className="font-serif-luxe text-2xl">{t("details", lang)}</h2>
        <Field label={`${t("relationship_intent", lang)} (${t("select_multiple", lang)})`}>
          <div className="mt-1">
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <button
                  type="button"
                  data-testid="profile-intent-select"
                  className="w-full min-h-10 flex items-center justify-between gap-2 rounded-md bg-white/5 border border-white/10 px-3 py-2 text-sm hover:bg-white/10 transition-colors focus:outline-none focus:ring-2 focus:ring-rose-500/40"
                >
                  <span className={`truncate text-left ${intents.length ? "text-white" : "text-slate-400"}`}>
                    {intents.length ? intents.map(o => optLabel("relationship_intent", o, lang)).join(", ") : t("relationship_intent", lang)}
                  </span>
                  <ChevronDown size={15} className="shrink-0 opacity-50" />
                </button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="start" className="bg-[#161320] border-white/10 text-white max-h-64 overflow-y-auto w-[--radix-dropdown-menu-trigger-width] min-w-[240px]">
                {INTENTS.map(o => (
                  <DropdownMenuCheckboxItem
                    key={o}
                    data-testid={`profile-intent-option-${o}`}
                    checked={intents.includes(o)}
                    onCheckedChange={() => toggleIntent(o)}
                    onSelect={(e) => e.preventDefault()}
                    className="text-white focus:bg-white/10 focus:text-white cursor-pointer"
                  >
                    {optLabel("relationship_intent", o, lang)}
                  </DropdownMenuCheckboxItem>
                ))}
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </Field>
        <Field label={`${t("orientation", lang)} (${t("select_multiple", lang)})`}>
          <div className="mt-1">
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <button
                  type="button"
                  data-testid="profile-orientation-select"
                  className="w-full min-h-10 flex items-center justify-between gap-2 rounded-md bg-white/5 border border-white/10 px-3 py-2 text-sm hover:bg-white/10 transition-colors focus:outline-none focus:ring-2 focus:ring-rose-500/40"
                >
                  {(() => {
                    const sel = Array.isArray(f.orientations) ? f.orientations : (f.orientation ? [f.orientation] : []);
                    return (
                      <span className={`truncate text-left ${sel.length ? "text-white" : "text-slate-400"}`}>
                        {sel.length ? sel.map(o => optLabel("orientation", o, lang)).join(", ") : t("orientation", lang)}
                      </span>
                    );
                  })()}
                  <ChevronDown size={15} className="shrink-0 opacity-50" />
                </button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="start" className="bg-[#161320] border-white/10 text-white max-h-64 overflow-y-auto w-[--radix-dropdown-menu-trigger-width] min-w-[240px]">
                {ORIENTATIONS.map(o => {
                  const sel = Array.isArray(f.orientations) ? f.orientations : (f.orientation ? [f.orientation] : []);
                  const checked = sel.includes(o);
                  return (
                    <DropdownMenuCheckboxItem
                      key={o}
                      data-testid={`profile-orientation-option-${o}`}
                      checked={checked}
                      onCheckedChange={(v) => {
                        const next = v ? [...sel, o] : sel.filter(x => x !== o);
                        setF({ ...f, orientations: next, orientation: next[0] || "" });
                      }}
                      onSelect={(e) => e.preventDefault()}
                      className="text-white focus:bg-white/10 focus:text-white cursor-pointer"
                    >
                      {optLabel("orientation", o, lang)}
                    </DropdownMenuCheckboxItem>
                  );
                })}
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </Field>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <Field label={t("job_title", lang)}><Input data-testid="profile-job-input" value={f.job_title || ""} onChange={e => set("job_title")(e.target.value)} className="bg-white/5 border-white/10 mt-1" /></Field>
          <Field label={t("height", lang)}><Input data-testid="profile-height-input" type="number" min="100" max="250" value={f.height || ""} onChange={e => set("height")(e.target.value ? parseInt(e.target.value) : null)} className="bg-white/5 border-white/10 mt-1" /></Field>
          <Field label={t("weight", lang)}><Input data-testid="profile-weight-input" type="number" min="30" max="300" value={f.weight || ""} onChange={e => set("weight")(e.target.value ? parseInt(e.target.value) : null)} className="bg-white/5 border-white/10 mt-1" /></Field>
          <Field label={`${t("income", lang)} $/month`}><Sel testid="profile-income-select" field="income" value={f.income} options={INCOMES} onChange={set("income")} lang={lang} /></Field>
          {f.income === "custom" && <Field label={`${t("income_custom_value", lang)} ($/month)`}><Input data-testid="profile-income-custom-input" inputMode="decimal" value={f.income_custom || ""} onChange={e => set("income_custom")(e.target.value.replace(/[^0-9.]/g, "").replace(/(\..*)\./g, "$1"))} placeholder="e.g. 7500" className="bg-white/5 border-white/10 mt-1 font-mono-num" /></Field>}
          <Field label={t("religion", lang)}><Sel testid="profile-religion-select" field="religion" value={f.religion} options={RELIGIONS} onChange={set("religion")} lang={lang} /></Field>
        </div>
        <Field label={`${t("hobbies", lang)} (max ${HOBBY_MAX})`}>
          <div className="mt-1">
            <MultiSelect
              testid="profile-hobbies-select"
              accent="rose"
              value={f.hobbies || []}
              onChange={(vals) => {
                if (vals.length > HOBBY_MAX) {
                  toast.error(`You can choose up to ${HOBBY_MAX} hobbies.`);
                  return;
                }
                set("hobbies")(vals);
              }}
              groups={HOBBY_SELECT_GROUPS}
              placeholder={t("hobbies", lang)}
              searchPlaceholder={t("search", lang)}
              emptyText={t("no_results", lang)}
            />
            <p className="text-[11px] text-slate-500 mt-1.5">{(f.hobbies || []).length}/{HOBBY_MAX} selected</p>
          </div>
        </Field>
        <Field label={t("languages_spoken", lang)}>
          <div className="mt-1">
            <MultiSelect
              testid="profile-languages-select"
              accent="rose"
              value={f.languages_spoken || []}
              onChange={(codes) => set("languages_spoken")(codes)}
              options={SPOKEN_LANGUAGES.map(l => ({ value: l.code, label: `${l.flag} ${l.name}` }))}
              placeholder={t("languages_spoken", lang)}
              searchPlaceholder={t("search", lang)}
              emptyText={t("no_results", lang)}
            />
          </div>
        </Field>
      </div>

      <div className="glass rounded-2xl p-6 space-y-4 mb-6" data-testid="profile-lifestyle-section">
        <h2 className="font-serif-luxe text-2xl">{t("lifestyle", lang)}</h2>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <Field label={t("kids", lang)}><Sel testid="profile-kids-select" field="kids" value={f.kids} options={KIDS} onChange={set("kids")} lang={lang} /></Field>
          <Field label={t("smoking", lang)}><Sel testid="profile-smoking-select" field="smoking" value={f.smoking} options={HABITS} onChange={set("smoking")} lang={lang} /></Field>
          <Field label={t("drinking", lang)}><Sel testid="profile-drinking-select" field="drinking" value={f.drinking} options={HABITS} onChange={set("drinking")} lang={lang} /></Field>
        </div>
      </div>

      <div className="glass rounded-2xl p-6 space-y-4 mb-6 border border-rose-500/20" data-testid="profile-intimate-section">
        <h2 className="font-serif-luxe text-2xl">{t("intimate", lang)}</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {gender !== "male" && <Field label={t("bust_size", lang)}><Sel testid="profile-bust-select" field="bust_size" value={f.bust_size} options={BUST} onChange={set("bust_size")} lang={lang} /></Field>}
          {gender !== "male" && <Field label={t("bust_type", lang)}><Sel testid="profile-bust-type-select" field="bust_type" value={f.bust_type} options={BUST_TYPE} onChange={set("bust_type")} lang={lang} /></Field>}
          {gender !== "female" && <Field label={t("penis_size", lang)}><Input data-testid="profile-penis-select" type="number" min="1" max="60" value={f.penis_size || ""} onChange={(e) => set("penis_size")(e.target.value)} placeholder={t("vip_dick_custom_ph", lang)} className="bg-white/5 border-white/10 mt-1" /></Field>}
          {gender !== "female" && <Field label={t("penis_girth", lang)}><Sel testid="profile-penis-girth-select" field="dick_girth" value={f.dick_girth} options={DICK_GIRTHS} onChange={set("dick_girth")} lang={lang} /></Field>}
        </div>
      </div>
    </>
  );
}
