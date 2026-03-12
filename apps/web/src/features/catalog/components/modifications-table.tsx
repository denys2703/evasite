import { Table, Td, Th } from '@/components/ui/table';
import { Modification } from '@/features/catalog/types/catalog.types';

export function ModificationsTable({ rows }: { rows: Modification[] }) {
  if (!rows.length) return <p className="text-sm text-slate-500">No modifications found.</p>;

  return (
    <div className="overflow-x-auto rounded-lg border border-slate-200">
      <Table>
        <thead className="bg-slate-50">
          <tr>
            <Th>Article</Th>
            <Th>Drive</Th>
            <Th>Gearbox</Th>
            <Th>Fuel</Th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.id} className="border-t border-slate-100">
              <Td>{row.article_code}</Td>
              <Td>{row.drive_type ?? '—'}</Td>
              <Td>{row.gearbox ?? '—'}</Td>
              <Td>{row.fuel_type ?? 'Petrol/Diesel'}</Td>
            </tr>
          ))}
        </tbody>
      </Table>
    </div>
  );
}
