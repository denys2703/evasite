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
  status: string;
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

export interface Hanger {
  id: number;
  hanger_number: number;
  brand: string;
  warehouse_section: string;
}

export interface LogEntry {
  id: number;
  car_id: number | null;
  event_type: string;
  description: string;
  created_at: string;
}
