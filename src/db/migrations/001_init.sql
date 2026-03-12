CREATE TABLE IF NOT EXISTS hangers (
  id SERIAL PRIMARY KEY,
  hanger_number INTEGER UNIQUE NOT NULL,
  brand VARCHAR(120) NOT NULL,
  warehouse_section VARCHAR(120) NOT NULL
);

CREATE TABLE IF NOT EXISTS cars (
  id SERIAL PRIMARY KEY,
  eva_code VARCHAR(40) UNIQUE NOT NULL,
  brand VARCHAR(120) NOT NULL,
  model VARCHAR(120) NOT NULL,
  generation VARCHAR(120),
  body_type VARCHAR(120),
  production_years VARCHAR(50),
  hanger_number INTEGER NOT NULL REFERENCES hangers(hanger_number) ON UPDATE CASCADE,
  template_type VARCHAR(10) NOT NULL CHECK (template_type IN ('2D', '5D')),
  status VARCHAR(30) NOT NULL DEFAULT 'active'
);

CREATE TABLE IF NOT EXISTS modifications (
  id SERIAL PRIMARY KEY,
  car_id INTEGER NOT NULL REFERENCES cars(id) ON DELETE CASCADE,
  article_code VARCHAR(80) UNIQUE NOT NULL,
  drive_type VARCHAR(30),
  gearbox VARCHAR(30),
  fuel_type VARCHAR(30),
  facelift_version VARCHAR(60)
);

CREATE TABLE IF NOT EXISTS logs (
  id SERIAL PRIMARY KEY,
  car_id INTEGER REFERENCES cars(id) ON DELETE SET NULL,
  event_type VARCHAR(60) NOT NULL,
  description TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cars_brand_model ON cars(brand, model);
CREATE INDEX IF NOT EXISTS idx_cars_hanger_number ON cars(hanger_number);
CREATE INDEX IF NOT EXISTS idx_modifications_car_id ON modifications(car_id);
CREATE INDEX IF NOT EXISTS idx_logs_car_id_created_at ON logs(car_id, created_at DESC);
