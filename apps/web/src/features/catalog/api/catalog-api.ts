import { ActivityLog, CarsResponse, CatalogFilters, Modification } from '@/features/catalog/types/catalog.types';

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:3000/api';

async function fetchJson<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init);
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }
  return (await response.json()) as T;
}

export async function fetchCars(filters: CatalogFilters): Promise<CarsResponse> {
  const params = new URLSearchParams({
    page: String(filters.page),
    limit: String(filters.limit),
  });

  if (filters.search) params.set('search', filters.search);
  if (filters.brand) params.set('brand', filters.brand);
  if (filters.template_type) params.set('template_type', filters.template_type);
  if (filters.status) params.set('status', filters.status);

  return fetchJson<CarsResponse>(`${API_BASE}/cars?${params.toString()}`);
}

export function fetchModifications(evaCode: string): Promise<Modification[]> {
  return fetchJson<Modification[]>(`${API_BASE}/cars/${evaCode}/modifications`);
}

export async function updateCarStatus(evaCode: string, status: string) {
  return fetchJson(`${API_BASE}/cars/${evaCode}/status`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ status }),
  });
}

export async function fetchLogs(carId: number): Promise<ActivityLog[]> {
  try {
    return await fetchJson<ActivityLog[]>(`${API_BASE}/activity?entityType=car_platform&entityId=${carId}`);
  } catch {
    return [];
  }
}
