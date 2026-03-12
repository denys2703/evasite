import { pool } from '../db/pool';
import { Car, Hanger } from '../types/domain';

export class HangerRepository {
  async list(): Promise<Hanger[]> {
    const result = await pool.query<Hanger>('SELECT * FROM hangers ORDER BY hanger_number');
    return result.rows;
  }

  async carsByHangerNumber(hangerNumber: number): Promise<Car[]> {
    const result = await pool.query<Car>('SELECT * FROM cars WHERE hanger_number = $1 ORDER BY brand, model', [hangerNumber]);
    return result.rows;
  }

  async upsertHanger(input: { hanger_number: number; brand: string; warehouse_section: string }): Promise<Hanger> {
    const result = await pool.query<Hanger>(
      `
      INSERT INTO hangers (hanger_number, brand, warehouse_section)
      VALUES ($1,$2,$3)
      ON CONFLICT (hanger_number)
      DO UPDATE SET
        brand = EXCLUDED.brand,
        warehouse_section = EXCLUDED.warehouse_section
      RETURNING *
      `,
      [input.hanger_number, input.brand, input.warehouse_section],
    );

    return result.rows[0];
  }
}
