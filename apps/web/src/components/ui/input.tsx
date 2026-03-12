import { InputHTMLAttributes } from 'react';
import { cn } from '@/lib/utils';

export function Input(props: InputHTMLAttributes<HTMLInputElement>) {
  return <input className={cn('h-10 w-full rounded-lg border border-slate-200 bg-white px-3 text-sm outline-none ring-0 focus:border-slate-400')} {...props} />;
}
