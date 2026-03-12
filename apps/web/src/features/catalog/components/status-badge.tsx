import { Badge } from '@/components/ui/badge';
import { Status } from '@/features/catalog/types/catalog.types';

const map: Record<string, { label: string; className: string }> = {
  ok: { label: 'OK', className: 'bg-emerald-100 text-emerald-700' },
  needs_scan: { label: 'Needs Scan', className: 'bg-amber-100 text-amber-700' },
  missing: { label: 'Missing', className: 'bg-red-100 text-red-700' },
  needs_update: { label: 'Needs Update', className: 'bg-sky-100 text-sky-700' },
  active: { label: 'OK', className: 'bg-emerald-100 text-emerald-700' },
  draft: { label: 'Needs Update', className: 'bg-sky-100 text-sky-700' },
  archived: { label: 'Missing', className: 'bg-red-100 text-red-700' },
};

export function StatusBadge({ status }: { status: Status | string }) {
  const style = map[status] ?? { label: status, className: 'bg-slate-100 text-slate-700' };
  return <Badge className={style.className}>{style.label}</Badge>;
}
