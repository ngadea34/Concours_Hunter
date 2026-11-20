import { createContext, useCallback, useContext, useMemo, useRef, useState, type ReactNode } from 'react';
import { useI18n } from '../i18n';
import { errMsg } from '../util';

interface ToastItem { id: number; text: string; kind: 'ok' | 'err' }
interface ToastApi { ok: (text: string) => void; err: (e: unknown) => void }
const Ctx = createContext<ToastApi>({ ok: () => undefined, err: () => undefined });

export function ToastProvider({ children }: { children: ReactNode }) {
  const { t } = useI18n();
  const [items, setItems] = useState<ToastItem[]>([]);
  const nextId = useRef(1);
  const push = useCallback((text: string, kind: 'ok' | 'err') => {
    const id = nextId.current++;
    setItems((l) => [...l, { id, text, kind }]);
    window.setTimeout(() => setItems((l) => l.filter((x) => x.id !== id)), kind === 'err' ? 8000 : 4000);
  }, []);
  const api = useMemo<ToastApi>(() => ({
    ok: (text) => push(text, 'ok'),
    err: (e) => push(errMsg(e, t), 'err'),
  }), [push, t]);
  return (
    <Ctx.Provider value={api}>
      {children}
      <div className="toasts" aria-live="polite" aria-atomic="false" role="status">
        {items.map((i) => (
          <div key={i.id} className={`toast toast-${i.kind}`}>
            <span>{i.kind === 'err' ? `${t('common.error')} : ` : ''}{i.text}</span>
          </div>
        ))}
      </div>
    </Ctx.Provider>
  );
}

export function useToast(): ToastApi { return useContext(Ctx); }
