export type ToastType = 'error' | 'success';

export interface ToastItem {
  id: number;
  type: ToastType;
  message: string;
}

export const toastListeners = new Set<(toast: ToastItem) => void>();
let nextToastId = 1;

export function showToast(message: string, type: ToastType = 'error') {
  const item = { id: nextToastId++, type, message };
  toastListeners.forEach((listener) => listener(item));
}
