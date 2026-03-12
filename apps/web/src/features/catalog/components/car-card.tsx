import { ChevronDown, ChevronUp } from 'lucide-react';
import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Checkbox } from '@/components/ui/checkbox';
import { Skeleton } from '@/components/ui/skeleton';
import { useCarDetails } from '@/features/catalog/hooks/use-car-details';
import { Car } from '@/features/catalog/types/catalog.types';
import { StatusBadge } from './status-badge';
import { ModificationsTable } from './modifications-table';
import { ActivityLogPanel } from './activity-log-panel';

interface Props {
  car: Car;
  expanded: boolean;
  onToggle: () => void;
}

export function CarCard({ car, expanded, onToggle }: Props) {
  const { modifications, logs } = useCarDetails(car.eva_code, car.id, expanded);

  return (
    <Card className="space-y-3 p-3">
      <div className="flex items-start justify-between gap-3">
        <div className="space-y-2">
          <div className="flex flex-wrap items-center gap-2">
            <Badge className="bg-slate-100 text-slate-700">{car.brand}</Badge>
            <Badge className="bg-slate-100 text-slate-700">{car.hanger_number}</Badge>
            <Badge className="bg-slate-100 text-slate-700">{car.template_type}</Badge>
            <StatusBadge status={car.status} />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-slate-900">
              {car.brand} {car.model} {car.generation ?? ''}
            </h3>
            <p className="text-xs text-slate-500">{car.production_years ?? 'Years unavailable'}</p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <label className="flex items-center gap-2 text-xs text-slate-500">
            <Checkbox checked={car.status === 'active' || car.status === 'ok'} readOnly />
            status
          </label>
          <button className="rounded-md border border-slate-200 p-1.5 hover:bg-slate-50" onClick={onToggle}>
            {expanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
          </button>
        </div>
      </div>

      {expanded && (
        <div className="space-y-3 border-t border-slate-100 pt-3">
          <div className="grid grid-cols-1 gap-2 text-sm text-slate-600 md:grid-cols-3">
            <div>
              <span className="text-xs uppercase text-slate-400">EVA code</span>
              <p>{car.eva_code}</p>
            </div>
            <div>
              <span className="text-xs uppercase text-slate-400">Body type</span>
              <p>{car.body_type ?? '—'}</p>
            </div>
            <div>
              <span className="text-xs uppercase text-slate-400">Generation</span>
              <p>{car.generation ?? '—'}</p>
            </div>
          </div>

          {modifications.isLoading ? <Skeleton className="h-24" /> : <ModificationsTable rows={modifications.data ?? []} />}

          {logs.isLoading ? <Skeleton className="h-16" /> : <ActivityLogPanel logs={logs.data ?? []} />}
        </div>
      )}
    </Card>
  );
}
