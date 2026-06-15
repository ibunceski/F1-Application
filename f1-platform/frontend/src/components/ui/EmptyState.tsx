import type { LucideIcon } from 'lucide-react';

interface EmptyStateProps {
  title: string;
  description: string;
  icon?: LucideIcon;
}

export function EmptyState({ title, description, icon: Icon }: EmptyStateProps) {
  return (
    <div className="card flex min-h-40 flex-col items-center justify-center gap-3 p-8 text-center">
      {Icon ? <Icon className="h-8 w-8 text-f1-muted" /> : null}
      <div>
        <h2 className="text-base font-semibold text-f1-white">{title}</h2>
        <p className="mt-1 text-sm text-f1-muted">{description}</p>
      </div>
    </div>
  );
}
