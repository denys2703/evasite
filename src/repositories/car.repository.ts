import { pool } from '../db/pool';
import { Car } from '../types/domain';

interface CarFilters {
  search?: string;
  brand?: string;
  template_type?: '2D' | '5D';
  status?: string;
}

export class CarRepository {
  async list(page: number, limit: number, filters: CarFilters): Promise<{ data: Car[]; total: number }> {
    const offset = (page - 1) * limit;
    const values: unknown[] = [];
    const where: string[] = [];

    if (filters.search) {
      values.push(`%${filters.search}%`);
      where.push(`(eva_code ILIKE $${values.length} OR brand ILIKE $${values.length} OR model ILIKE $${values.length})`);
    }
    if (filters.brand) {
      values.push(filters.brand);
      where.push(`brand = $${values.length}`);
    }
    if (filters.template_type) {
      values.push(filters.template_type);
      where.push(`template_type = $${values.length}`);
    }
    if (filters.status) {
      values.push(filters.status);
      where.push(`status = $${values.length}`);
    }

    const whereClause = where.length ? `WHERE ${where.join(' AND ')}` : '';

    const totalQuery = `SELECT COUNT(*)::int as total FROM cars ${whereClause}`;
    const totalResult = await pool.query<{ total: number }>(totalQuery, values);

    values.push(limit, offset);
    const dataQuery = `
      SELECT *
      FROM cars
      ${whereClause}
      ORDER BY brand, model, eva_code
      LIMIT $${values.length - 1} OFFSET $${values.length}
    `;

    const dataResult = await pool.query<Car>(dataQuery, values);

    return {
      data: dataResult.rows,
      total: totalResult.rows[0]?.total ?? 0,
    };
  }


  async findById(id: number): Promise<Car | null> {
    const result = await pool.query<Car>('SELECT * FROM cars WHERE id = $1', [id]);
    return result.rows[0] ?? null;
  }

  async findByEvaCode(evaCode: string): Promise<Car | null> {
    const result = await pool.query<Car>('SELECT * FROM cars WHERE eva_code = $1', [evaCode]);
    return result.rows[0] ?? null;
  }

  async updateStatusByEvaCode(evaCode: string, status: string): Promise<Car | null> {
    const result = await pool.query<Car>('UPDATE cars SET status = $1 WHERE eva_code = $2 RETURNING *', [status, evaCode]);
    return result.rows[0] ?? null;
  }

  async upsertCar(input: {
    eva_code: string;
    brand: string;
    model: string;
    generation: string | null;
    body_type: string;
    production_years: string | null;
    hanger_number: number;
    template_type: '2D' | '5D';
    status?: string;
  }): Promise<Car> {
    const result = await pool.query<Car>(
      `
      INSERT INTO cars (eva_code, brand, model, generation, body_type, production_years, hanger_number, template_type, status)
      VALUES ($1,$2,$3,$4,$5,$6,$7,$8, COALESCE($9, 'active'))
      ON CONFLICT (eva_code)
      DO UPDATE SET
        brand = EXCLUDED.brand,
        model = EXCLUDED.model,
        generation = EXCLUDED.generation,
        body_type = EXCLUDED.body_type,
        production_years = EXCLUDED.production_years,
        hanger_number = EXCLUDED.hanger_number,
        template_type = EXCLUDED.template_type
      RETURNING *
      `,
      [
        input.eva_code,
        input.brand,
        input.model,
        input.generation,
        input.body_type,
        input.production_years,
        input.hanger_number,
        input.template_type,
        input.status ?? null,
      ],
    );

    return result.rows[0];
  }
}
