interface StatCardProps {
  label: string;
  value: string | number;
  unit?: string;
  trend?: string;
  color?: string;
}

export function StatCard({ label, value, unit, trend, color }: StatCardProps) {
  return (
    <div className="card p-4">
      <p className="section-label">{label}</p>
      <div className="mt-3 flex items-end gap-2">
        <span className={`data-value text-2xl font-semibold ${color || ''}`}>{value}</span>
        {unit ? <span className="pb-1 text-xs text-f1-muted">{unit}</span> : null}
      </div>
      {trend ? <p className="mt-2 text-xs text-f1-muted">{trend}</p> : null}
    </div>
  );
}
