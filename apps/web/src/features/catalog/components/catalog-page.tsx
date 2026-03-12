import { Skeleton } from '@/components/ui/skeleton';
import { CatalogFilters } from './catalog-filters';
import { CatalogList } from './catalog-list';
import { CatalogPagination } from './catalog-pagination';
import { useCatalog } from '@/features/catalog/hooks/use-catalog';

export function CatalogPage() {
  const { query, filters, setFilters, brands } = useCatalog();

  return (
    <div className="mx-auto max-w-6xl space-y-4 px-4 py-6">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight text-slate-900">Vehicle Template Catalog</h1>
        <p className="text-sm text-slate-500">Fast warehouse view for EVA platforms and ART modifications.</p>
      </header>

      <CatalogFilters filters={filters} brands={brands} onChange={(patch) => setFilters((prev) => ({ ...prev, ...patch }))} />

      {query.isLoading ? <Skeleton className="h-[60vh]" /> : <CatalogList cars={query.data?.data ?? []} />}

      <CatalogPagination
        page={filters.page}
        limit={filters.limit}
        total={query.data?.total ?? 0}
        onPageChange={(page) => setFilters((prev) => ({ ...prev, page }))}
      />
    </div>
  );
}
