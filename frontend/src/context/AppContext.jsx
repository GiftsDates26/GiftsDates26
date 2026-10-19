import React, { createContext, useContext, useEffect, useState, useCallback } from "react";
import { api } from "../lib/api";
import { LANGUAGES, missingStrings, detectLanguage } from "../lib/i18n";
import { setAutoLanguage, prefetch } from "../lib/autoTranslate";

const AppCtx = createContext(null);
export const useApp = () => useContext(AppCtx);

export function AppProvider({ children }) {
  const [user, setUser] = useState(null);
  // Explicit choice wins; otherwise open the site in the visitor's browser language (closest match, else English).
  const [lang, setLang] = useState(() => localStorage.getItem("gd_lang") || detectLanguage());
  const [langDetected, setLangDetected] = useState(() => !localStorage.getItem("gd_lang") && detectLanguage() !== "en" && !localStorage.getItem("gd_lang_banner_done"));
  const [meta, setMeta] = useState(null);
  const [loading, setLoading] = useState(true);
  const [spinEligible, setSpinEligible] = useState(false);

  const refreshSpin = useCallback(async () => {
    if (!localStorage.getItem("gd_token")) { setSpinEligible(false); return; }
    try { const { data } = await api.get("/spin/status"); setSpinEligible(!!data.eligible); } catch { setSpinEligible(false); }
  }, []);

  const dismissLangBanner = useCallback(() => { setLangDetected(false); localStorage.setItem("gd_lang_banner_done", "1"); }, []);
  const setLanguage = useCallback((code) => {
    setLang(code);
    setLangDetected(false); localStorage.setItem("gd_lang_banner_done", "1");
    localStorage.setItem("gd_lang", code);
    const cfg = LANGUAGES.find(l => l.code === code);
    document.documentElement.setAttribute("dir", cfg?.dir || "ltr");
    document.documentElement.setAttribute("lang", code);
    if (user) api.patch("/auth/me", { language: code }).catch(() => {});
  }, [user]);

  useEffect(() => {
    const cfg = LANGUAGES.find(l => l.code === lang);
    document.documentElement.setAttribute("dir", cfg?.dir || "ltr");
    document.documentElement.setAttribute("lang", lang);
    // Auto-translate every page, dropdown, toast, dialog & warning into the chosen language
    setAutoLanguage(lang);
    if (lang !== "en") {
      const id = setTimeout(() => prefetch(missingStrings(lang)), 1500);
      return () => clearTimeout(id);
    }
  }, [lang]);

  const refreshUser = useCallback(async () => {
    const t = localStorage.getItem("gd_token");
    if (!t) { setUser(null); return; }
    try {
      const { data } = await api.get("/auth/me");
      setUser(data);
      // The language chosen on this device (e.g. on the main page) wins; sync it to the account.
      const chosen = localStorage.getItem("gd_lang");
      if (chosen && data.language !== chosen) api.patch("/auth/me", { language: chosen }).catch(() => {});
      else if (!chosen && data.language && data.language !== lang) { setLang(data.language); localStorage.setItem("gd_lang", data.language); }
      refreshSpin();
    } catch { localStorage.removeItem("gd_token"); setUser(null); setSpinEligible(false); }
  }, [lang, refreshSpin]);

  useEffect(() => {
    (async () => {
      try { const { data } = await api.get("/meta"); setMeta(data); } catch {}
      await refreshUser();
      setLoading(false);
    })();
  }, [refreshUser]);

  const login = async (email, password) => {
    const { data } = await api.post("/auth/login", { email, password });
    localStorage.setItem("gd_token", data.token);
    setUser(data.user);
    return data.user;
  };
  const register = async (payload) => {
    const { data } = await api.post("/auth/register", payload);
    localStorage.setItem("gd_token", data.token);
    setUser(data.user);
    return data.user;
  };
  const logout = () => { localStorage.removeItem("gd_token"); setUser(null); setSpinEligible(false); };

  return (
    <AppCtx.Provider value={{ user, setUser, lang, setLanguage, langDetected, dismissLangBanner, meta, loading, login, register, logout, refreshUser, spinEligible, refreshSpin }}>
      {children}
    </AppCtx.Provider>
  );
}
