import { useQuery } from '@tanstack/react-query';
import { fetchLogs, fetchModifications } from '@/features/catalog/api/catalog-api';

export function useCarDetails(evaCode: string, carId: number, enabled: boolean) {
  const modifications = useQuery({
    queryKey: ['modifications', evaCode],
    queryFn: () => fetchModifications(evaCode),
    enabled,
    staleTime: 5 * 60_000,
  });

  const logs = useQuery({
    queryKey: ['logs', carId],
    queryFn: () => fetchLogs(carId),
    enabled,
    staleTime: 30_000,
  });

  return { modifications, logs };
}
