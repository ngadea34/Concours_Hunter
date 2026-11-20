import { createContext, createElement, useCallback, useContext, useMemo, useState, type ReactNode } from 'react';
import { fr } from './locales/fr';
import { en } from './locales/en';

export type Lang = 'fr' | 'en';
export type Key = keyof typeof fr;
const dicts: Record<Lang, Record<string, string>> = { fr, en };
const LANG_KEY = 'ch_lang';

function initialLang(): Lang {
  try {
    const v = localStorage.getItem(LANG_KEY);
    if (v === 'fr' || v === 'en') return v;
  } catch { /* ignoré */ }
  return 'fr';
}

export type TFn = (key: Key | (string & {}), vars?: Record<string, string | number>) => string;

interface Ctx { lang: Lang; setLang: (l: Lang) => void; t: TFn }
const I18nContext = createContext<Ctx>({ lang: 'fr', setLang: () => undefined, t: (k) => String(k) });

export function I18nProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>(initialLang);
  const setLang = useCallback((l: Lang) => {
    setLangState(l);
    try { localStorage.setItem(LANG_KEY, l); } catch { /* ignoré */ }
    document.documentElement.lang = l;
  }, []);
  const t = useCallback<TFn>((key, vars) => {
    let s = dicts[lang][key] ?? dicts.fr[key] ?? key;
    if (vars) for (const [k, v] of Object.entries(vars)) s = s.split(`{${k}}`).join(String(v));
    return s;
  }, [lang]);
  const value = useMemo(() => ({ lang, setLang, t }), [lang, setLang, t]);
  return createElement(I18nContext.Provider, { value }, children);
}

export function useI18n(): Ctx { return useContext(I18nContext); }
