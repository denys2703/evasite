import { Search } from 'lucide-react';
import { Input } from '@/components/ui/input';
import { Select } from '@/components/ui/select';
import { CatalogFilters as CatalogFiltersType } from '@/features/catalog/types/catalog.types';

interface Props {
  filters: CatalogFiltersType;
  brands: string[];
  onChange: (patch: Partial<CatalogFiltersType>) => void;
}

export function CatalogFilters({ filters, brands, onChange }: Props) {
  return (
    <div className="grid grid-cols-1 gap-3 rounded-xl border border-slate-200 bg-white p-3 shadow-soft md:grid-cols-4">
      <div className="relative md:col-span-2">
        <Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
        <Input
          className="pl-9"
          placeholder="Search by brand, model, EVA, article"
          value={filters.search}
          onChange={(event) => onChange({ search: event.target.value, page: 1 })}
        />
      </div>

      <Select value={filters.brand} onChange={(event) => onChange({ brand: event.target.value, page: 1 })}>
        <option value="">All brands</option>
        {brands.map((brand) => (
          <option key={brand} value={brand}>
            {brand}
          </option>
        ))}
      </Select>

      <div className="grid grid-cols-2 gap-2">
        <Select value={filters.template_type} onChange={(event) => onChange({ template_type: event.target.value, page: 1 })}>
          <option value="">All types</option>
          <option value="2D">2D</option>
          <option value="5D">5D</option>
        </Select>

        <Select value={filters.status} onChange={(event) => onChange({ status: event.target.value, page: 1 })}>
          <option value="">All status</option>
          <option value="active">OK</option>
          <option value="draft">Needs Update</option>
          <option value="archived">Missing</option>
        </Select>
      </div>
    </div>
  );
}
