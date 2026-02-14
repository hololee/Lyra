import clsx from 'clsx';
import { CheckCircle, Info, X, XCircle } from 'lucide-react';
import { useEffect } from 'react';

export type ToastType = 'success' | 'error' | 'info';

interface ToastProps {
  id: string;
  message: string;
  type: ToastType;
  onClose: (id: string) => void;
}

export default function Toast({ id, message, type, onClose }: ToastProps) {
  useEffect(() => {
    const timer = setTimeout(() => {
      onClose(id);
    }, 3000);

    return () => clearTimeout(timer);
  }, [id, onClose]);

  const accent = type === 'success'
    ? 'var(--success)'
    : type === 'error'
      ? 'var(--danger)'
      : 'var(--primary)';

  return (
    <div
      className={clsx(
        "w-full max-w-md flex items-start gap-3 px-4 py-3 rounded-lg shadow-lg border border-l-4 backdrop-blur-md transition-all animate-in slide-in-from-right-full duration-300"
      )}
      style={{
        backgroundColor: 'color-mix(in oklab, var(--bg-elevated) 94%, transparent)',
        borderColor: `color-mix(in oklab, ${accent} 34%, var(--border))`,
        borderLeftColor: accent,
        color: `color-mix(in oklab, ${accent} 74%, var(--text))`,
      }}
      role="alert"
    >
      <div className="shrink-0">
        {type === 'success' && <CheckCircle size={18} style={{ color: accent }} />}
        {type === 'error' && <XCircle size={18} style={{ color: accent }} />}
        {type === 'info' && <Info size={18} style={{ color: accent }} />}
      </div>
      <p className="text-sm font-medium leading-5 break-words">{message}</p>
      <button
        onClick={() => onClose(id)}
        className="ml-2 rounded-md p-1 transition-colors hover:bg-[color-mix(in_oklab,var(--bg)_70%,transparent)]"
        style={{ color: accent }}
      >
        <X size={14} />
      </button>
    </div>
  );
}
