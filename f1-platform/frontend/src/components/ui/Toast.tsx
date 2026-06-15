import { useEffect, useState } from 'react';
import { toastListeners, type ToastItem } from './toastStore';

export function ToastViewport() {
  const [items, setItems] = useState<ToastItem[]>([]);

  useEffect(() => {
    const listener = (toast: ToastItem) => {
      setItems((current) => [...current.slice(-2), toast]);
      window.setTimeout(() => {
        setItems((current) => current.filter((item) => item.id !== toast.id));
      }, 4000);
    };
    toastListeners.add(listener);
    return () => {
      toastListeners.delete(listener);
    };
  }, []);

  return (
    <div className="fixed bottom-5 right-5 z-50 flex w-[min(360px,calc(100vw-2rem))] flex-col gap-3">
      {items.map((item) => (
        <div
          key={item.id}
          className={`rounded-lg border bg-f1-surface px-4 py-3 text-sm shadow-2xl ${
            item.type === 'error' ? 'border-f1-red text-f1-text' : 'border-green-500 text-f1-text'
          }`}
        >
          <p className="font-semibold text-f1-white">{item.type === 'error' ? 'Request failed' : 'Success'}</p>
          <p className="mt-1 text-f1-muted">{item.message}</p>
        </div>
      ))}
    </div>
  );
}
