export type Status = 'ok' | 'needs_scan' | 'missing' | 'needs_update' | 'active' | 'draft' | 'archived';

export interface Car {
  id: number;
  eva_code: string;
  brand: string;
  model: string;
  generation: string | null;
  body_type: string | null;
  production_years: string | null;
  hanger_number: number;
  template_type: '2D' | '5D';
  status: Status;
}

export interface Modification {
  id: number;
  car_id: number;
  article_code: string;
  drive_type: string | null;
  gearbox: string | null;
  fuel_type: string | null;
  facelift_version: string | null;
}

export interface ActivityLog {
  id: number;
  event_type: string;
  description: string;
  created_at: string;
}

export interface CarsResponse {
  page: number;
  limit: number;
  total: number;
  data: Car[];
}

export interface CatalogFilters {
  search: string;
  brand: string;
  template_type: string;
  status: string;
  page: number;
  limit: number;
}
