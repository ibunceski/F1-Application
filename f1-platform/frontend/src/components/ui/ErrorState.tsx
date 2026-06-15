import { AlertTriangle } from 'lucide-react';

interface ErrorStateProps {
  message: string;
  onRetry?: () => void;
}

export function ErrorState({ message, onRetry }: ErrorStateProps) {
  return (
    <div className="card flex items-center justify-between gap-4 p-5">
      <div className="flex items-center gap-3">
        <AlertTriangle className="h-5 w-5 text-f1-red" />
        <p className="text-sm text-f1-text">{message}</p>
      </div>
      {onRetry ? (
        <button
          type="button"
          onClick={onRetry}
          className="rounded-md border border-f1-border bg-f1-elevated px-3 py-2 text-sm font-semibold text-f1-white hover:border-f1-red"
        >
          Retry
        </button>
      ) : null}
    </div>
  );
}
