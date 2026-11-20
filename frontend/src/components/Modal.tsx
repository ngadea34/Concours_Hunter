import { useEffect, useRef, type ReactNode } from 'react';
import { useI18n } from '../i18n';

export function Modal({ open, title, onClose, children }: { open: boolean; title: string; onClose: () => void; children: ReactNode }) {
  const ref = useRef<HTMLDialogElement>(null);
  const { t } = useI18n();
  useEffect(() => {
    const d = ref.current;
    if (!d) return;
    if (open && !d.open) d.showModal();
    if (!open && d.open) d.close();
  }, [open]);
  return (
    <dialog ref={ref} className="modal" aria-labelledby="modal-title" onClose={onClose} onCancel={onClose}>
      {open && (
        <div className="modal-body">
          <div className="row between">
            <h2 id="modal-title">{title}</h2>
            <button className="btn btn-sm" onClick={onClose} aria-label={t('common.close')}>✕</button>
          </div>
          {children}
        </div>
      )}
    </dialog>
  );
}
