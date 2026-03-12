import { Button } from '@/components/ui/button';

interface Props {
  page: number;
  limit: number;
  total: number;
  onPageChange: (page: number) => void;
}

export function CatalogPagination({ page, limit, total, onPageChange }: Props) {
  const pageCount = Math.max(1, Math.ceil(total / limit));

  return (
    <div className="flex items-center justify-between rounded-xl border border-slate-200 bg-white p-3">
      <p className="text-sm text-slate-500">
        Page {page} of {pageCount} • {total} cars
      </p>
      <div className="flex gap-2">
        <Button className="bg-white text-slate-800 border border-slate-200 hover:bg-slate-50" disabled={page <= 1} onClick={() => onPageChange(page - 1)}>
          Previous
        </Button>
        <Button disabled={page >= pageCount} onClick={() => onPageChange(page + 1)}>
          Next
        </Button>
      </div>
    </div>
  );
}
