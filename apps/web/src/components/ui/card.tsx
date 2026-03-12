import { PropsWithChildren } from 'react';
import { cn } from '@/lib/utils';

export function Card({ children, className }: PropsWithChildren<{ className?: string }>) {
  return <div className={cn('rounded-xl border border-slate-200 bg-white p-4 shadow-soft', className)}>{children}</div>;
}
