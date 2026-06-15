import { Activity, BarChart3, Database, Gauge, Server, Settings2, Trophy } from 'lucide-react';

const stages = [
  { name: 'FastF1 API', description: 'Historical race data', Icon: Gauge },
  { name: 'Data Ingestion', description: 'Seasons, results, lap times', Icon: Activity },
  { name: 'PostgreSQL', description: 'Structured storage', Icon: Database },
  { name: 'Feature Engineering', description: 'Driver form, pace, circuit history', Icon: Settings2 },
  { name: 'ML Models', description: '4 prediction models', Icon: BarChart3 },
  { name: 'FastAPI Backend', description: 'REST API', Icon: Server },
  { name: 'React Dashboard', description: 'Interactive visualization', Icon: Trophy },
];

export function ModelPipelineDiagram() {
  return (
    <section className="card-elevated overflow-hidden p-5">
      <div className="mb-5 flex items-center justify-between gap-4">
        <div>
          <p className="section-label">Pipeline</p>
          <h2 className="mt-2 text-xl font-bold text-f1-white">From timing data to race predictions</h2>
        </div>
        <div className="hidden rounded-full border border-f1-red/50 px-3 py-1 font-mono text-xs text-f1-red md:block">LIVE PATH</div>
      </div>

      <div className="relative overflow-x-auto pb-2">
        <div className="absolute left-20 right-20 top-1/2 hidden -translate-y-1/2 border-t border-dashed border-f1-red/50 md:block motion-safe:animate-pulse" />
        <div className="grid min-w-[980px] grid-cols-7 gap-3">
          {stages.map(({ name, description, Icon }, index) => (
            <div key={name} className="relative">
              <div className="relative z-10 h-full rounded-lg border border-f1-border bg-f1-elevated p-4">
                <Icon className="h-5 w-5 text-f1-red" />
                <h3 className="mt-3 text-sm font-bold text-f1-white">{name}</h3>
                <p className="mt-1 min-h-8 text-xs leading-relaxed text-f1-muted">{description}</p>
              </div>
              {index < stages.length - 1 ? (
                <div className="absolute -right-3 top-1/2 z-20 hidden h-6 w-6 -translate-y-1/2 items-center justify-center rounded-full border border-f1-border bg-f1-dark text-f1-red md:flex">
                  <span className="font-mono text-xs">-&gt;</span>
                </div>
              ) : null}
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
