import { SelectHTMLAttributes } from 'react';

export function Select(props: SelectHTMLAttributes<HTMLSelectElement>) {
  return <select className="h-10 rounded-lg border border-slate-200 bg-white px-3 text-sm" {...props} />;
}
