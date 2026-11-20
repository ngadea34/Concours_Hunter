import { useState } from 'react';
import { useI18n } from '../i18n';
import { useToast } from './Toast';

export function CopyButton({ text, label }: { text: string; label?: string }) {
  const { t } = useI18n();
  const toast = useToast();
  const [done, setDone] = useState(false);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setDone(true);
      window.setTimeout(() => setDone(false), 1500);
    } catch {
      toast.err(t('common.copyFailed'));
    }
  };
  return (
    <button type="button" className="btn btn-sm" onClick={copy} aria-label={label}>
      {done ? t('common.copied') : t('common.copy')}
    </button>
  );
}
