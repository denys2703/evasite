import { PropsWithChildren } from 'react';

export function Table({ children }: PropsWithChildren) {
  return <table className="w-full text-left text-sm">{children}</table>;
}

export function Th({ children }: PropsWithChildren) {
  return <th className="px-2 py-2 text-xs font-semibold uppercase tracking-wide text-slate-500">{children}</th>;
}

export function Td({ children }: PropsWithChildren) {
  return <td className="px-2 py-2 text-slate-700">{children}</td>;
}
