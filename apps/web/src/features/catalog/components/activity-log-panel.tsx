import { ActivityLog } from '@/features/catalog/types/catalog.types';

function formatDate(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat('en-GB').format(date);
}

export function ActivityLogPanel({ logs }: { logs: ActivityLog[] }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-slate-50 p-3">
      <h4 className="mb-2 text-xs font-semibold uppercase text-slate-500">Recent activity</h4>
      {logs.length ? (
        <ul className="space-y-1 text-sm text-slate-700">
          {logs.slice(0, 5).map((log) => (
            <li key={log.id}>
              {formatDate(log.created_at)} — {log.description || log.event_type}
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-sm text-slate-500">No recent logs.</p>
      )}
    </div>
  );
}
