import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { fetchCars } from '@/features/catalog/api/catalog-api';
import { CatalogFilters } from '@/features/catalog/types/catalog.types';
import { useDebouncedValue } from './use-debounced-value';

export function useCatalog() {
  const [filters, setFilters] = useState<CatalogFilters>({
    search: '',
    brand: '',
    template_type: '',
    status: '',
    page: 1,
    limit: 50,
  });

  const debouncedSearch = useDebouncedValue(filters.search);

  const query = useQuery({
    queryKey: ['cars', { ...filters, search: debouncedSearch }],
    queryFn: () => fetchCars({ ...filters, search: debouncedSearch }),
    placeholderData: (prev) => prev,
  });

  const brands = useMemo(() => {
    const records = query.data?.data ?? [];
    return [...new Set(records.map((item) => item.brand))].sort();
  }, [query.data]);

  return { query, filters, setFilters, brands };
}
