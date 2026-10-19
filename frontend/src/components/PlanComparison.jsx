import React from "react";
import { Check, X, Crown, Sparkles } from "lucide-react";
import { Button } from "./ui/button";
import { t } from "../lib/i18n";

const TIERS = [
  { key: "free", name: (lang) => t("plan_free", lang), color: "text-slate-200", ring: "border-white/10", head: "bg-white/5", icon: null },
  { key: "lite", name: (lang) => t("premium_lite", lang), color: "text-sky-200", ring: "border-sky-500/40", head: "bg-sky-500/10", icon: "text-sky-400 fill-sky-500" },
  { key: "premium", name: (lang) => t("premium", lang), color: "text-amber-200", ring: "border-amber-500/40", head: "bg-amber-500/10", icon: "text-amber-300" },
  { key: "vip", name: () => "VIP", color: "text-rose-200", ring: "border-rose-500/40", head: "bg-rose-500/10", icon: "text-rose-400 fill-rose-500" },
];

// value per tier: true (✓), false (✗) or a short text
const rows = (lang, meta) => [
  { group: t("plan_group_search", lang) },
  { label: t("plan_row_per_page", lang), v: ["2", "4", "8", "12"] },
  { label: t("plan_row_basic_filters", lang), v: [true, true, true, true] },
  { label: t("plan_row_lite_filters", lang), v: [false, true, true, true] },
  { label: t("plan_row_name_search", lang), v: [false, false, true, true] },
  { label: t("plan_row_adv_filters", lang), v: [false, false, true, true] },
  { label: t("saved_searches", lang), v: [false, false, true, true] },
  { label: t("vip_private_search", lang), v: [false, false, false, true] },
  { group: t("plan_group_dating", lang) },
  { label: t("plan_row_daily_likes", lang), v: [String(meta?.free_daily_likes ?? 15), t("plan_unlimited", lang), t("plan_unlimited", lang), t("plan_unlimited", lang)] },
  { label: t("perk_see_likes", lang), v: [false, true, true, true] },
  { label: t("plan_row_placement", lang), v: [false, t("plan_boosted", lang), t("plan_top", lang), t("plan_top", lang)] },
  { label: t("plan_row_free_msgs", lang), v: [false, false, "1", "3"] },
  { label: t("plan_row_automatch", lang), v: [false, false, "1", "3"] },
  { label: t("perk_private_content", lang), v: [false, false, false, true] },
  { label: t("perk_priority_support", lang), v: [false, false, false, true] },
];

function Cell({ v, tier }) {
  if (v === true) return <Check size={16} className={`mx-auto ${tier === "vip" ? "text-rose-300" : tier === "premium" ? "text-amber-300" : tier === "lite" ? "text-sky-300" : "text-emerald-300"}`} />;
  if (v === false) return <X size={14} className="mx-auto text-slate-600" />;
  return <span className="text-xs font-medium text-slate-200">{v}</span>;
}

/**
 * Side-by-side plan comparison. `current` = viewer's active tier ("free" | "lite" | "premium" | "vip").
 * `onChoose(tierKey)` opens checkout; omit it (e.g. inside the purchase pop-up) to hide the buttons.
 */
export default function PlanComparison({ lang, meta, current = "free", onChoose, compact = false }) {
  const price = {
    free: t("plan_free_price", lang),
    lite: `$${meta?.premium_lite?.amount || 14.99}`,
    premium: `$${meta?.premium?.amount || 29.99}`,
    vip: `$${meta?.vip?.amount || 49.99}`,
  };
  const rank = { free: 0, lite: 1, premium: 2, vip: 3 };
  return (
    <div data-testid="plan-comparison" className={compact ? "" : "glass rounded-2xl p-5"}>
      {!compact && (
        <div className="flex items-center gap-2 mb-4">
          <Sparkles size={18} className="text-amber-300" />
          <h3 className="font-serif-luxe text-xl">{t("plan_compare_title", lang)}</h3>
        </div>
      )}
      <div className="overflow-x-auto -mx-1 px-1">
        <table className="w-full min-w-[640px] border-separate border-spacing-0 text-sm">
          <thead>
            <tr>
              <th className="sticky left-0 z-10 bg-[#161320] text-left text-xs font-normal text-slate-500 p-2 w-[34%]" />
              {TIERS.map(tr => (
                <th key={tr.key} data-testid={`plan-col-${tr.key}`} className={`p-3 align-bottom rounded-t-xl border-t border-x ${tr.ring} ${tr.head} ${current === tr.key ? "shadow-[0_-8px_24px_-12px_rgba(244,63,94,0.6)]" : ""}`}>
                  {current === tr.key && <div data-testid="plan-current-badge" className="mb-1 inline-block px-2 py-0.5 rounded-full bg-emerald-500/20 border border-emerald-400/40 text-[10px] text-emerald-200">{t("plan_your_plan", lang)}</div>}
                  <div className={`flex items-center justify-center gap-1.5 font-serif-luxe text-lg ${tr.color}`}>
                    {tr.icon && <Crown size={15} className={tr.icon} />} {tr.name(lang)}
                  </div>
                  <div className="text-xs text-slate-400 font-mono-num mt-0.5">{price[tr.key]}{tr.key !== "free" && <span className="text-slate-500"> {t("per_month", lang)}</span>}</div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows(lang, meta).map((r, i) => r.group ? (
              <tr key={`g${i}`}>
                <td colSpan={5} className="sticky left-0 pt-4 pb-1.5 px-2 text-[11px] uppercase tracking-widest text-slate-500">{r.group}</td>
              </tr>
            ) : (
              <tr key={i} className="group">
                <td className="sticky left-0 z-10 bg-[#161320] p-2 text-slate-300 text-xs border-b border-white/5 group-hover:text-white">{r.label}</td>
                {TIERS.map((tr, j) => (
                  <td key={tr.key} data-testid={`plan-cell-${tr.key}-${i}`} className={`p-2 text-center border-b border-x border-white/5 ${tr.ring} ${current === tr.key ? "bg-white/[0.04]" : ""} group-hover:bg-white/[0.03]`}>
                    <Cell v={r.v[j]} tier={tr.key} />
                  </td>
                ))}
              </tr>
            ))}
            {onChoose && (
              <tr>
                <td className="sticky left-0 bg-[#161320]" />
                {TIERS.map(tr => (
                  <td key={tr.key} className={`p-3 text-center rounded-b-xl border-b border-x ${tr.ring}`}>
                    {tr.key === "free" ? null : current === tr.key ? (
                      <span className="text-[11px] text-emerald-300">{t("plan_active", lang)}</span>
                    ) : rank[current] > rank[tr.key] ? (
                      <span className="text-[11px] text-slate-500">{t("plan_included", lang)}</span>
                    ) : (
                      <Button data-testid={`plan-choose-${tr.key}`} size="sm" onClick={() => onChoose(tr.key)}
                        className={`h-8 text-xs border-0 text-white ${tr.key === "lite" ? "bg-sky-600 hover:bg-sky-500" : tr.key === "premium" ? "bg-amber-600 hover:bg-amber-500" : "bg-rose-600 hover:bg-rose-500"}`}>
                        {t("plan_choose", lang)}
                      </Button>
                    )}
                  </td>
                ))}
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
