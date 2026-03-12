import { useRef, useState } from 'react';
import { useVirtualizer } from '@tanstack/react-virtual';
import { Car } from '@/features/catalog/types/catalog.types';
import { CarCard } from './car-card';

export function CatalogList({ cars }: { cars: Car[] }) {
  const parentRef = useRef<HTMLDivElement>(null);
  const [expandedId, setExpandedId] = useState<number | null>(null);

  const rowVirtualizer = useVirtualizer({
    count: cars.length,
    getScrollElement: () => parentRef.current,
    estimateSize: (index) => (expandedId === cars[index]?.id ? 340 : 120),
    overscan: 8,
  });

  return (
    <div ref={parentRef} className="h-[calc(100vh-220px)] overflow-auto rounded-xl border border-slate-200 bg-slate-50 p-3">
      <div className="relative" style={{ height: `${rowVirtualizer.getTotalSize()}px`, width: '100%' }}>
        {rowVirtualizer.getVirtualItems().map((virtualRow) => {
          const car = cars[virtualRow.index];
          const expanded = expandedId === car.id;
          return (
            <div
              key={car.id}
              className="absolute left-0 top-0 w-full pb-2"
              style={{ transform: `translateY(${virtualRow.start}px)` }}
            >
              <CarCard car={car} expanded={expanded} onToggle={() => setExpandedId(expanded ? null : car.id)} />
            </div>
          );
        })}
      </div>
    </div>
  );
}
