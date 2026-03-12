import { pool } from '../db/pool';
import { Modification } from '../types/domain';

export class ModificationRepository {
  async findByEvaCode(evaCode: string): Promise<Modification[]> {
    const result = await pool.query<Modification>(
      `
      SELECT m.*
      FROM modifications m
      JOIN cars c ON c.id = m.car_id
      WHERE c.eva_code = $1
      ORDER BY m.article_code
      `,
      [evaCode],
    );

    return result.rows;
  }

  async upsertModification(input: {
    car_id: number;
    article_code: string;
    drive_type: string | null;
    gearbox: string | null;
    fuel_type: string | null;
    facelift_version: string | null;
  }): Promise<Modification> {
    const result = await pool.query<Modification>(
      `
      INSERT INTO modifications (car_id, article_code, drive_type, gearbox, fuel_type, facelift_version)
      VALUES ($1,$2,$3,$4,$5,$6)
      ON CONFLICT (article_code)
      DO UPDATE SET
        car_id = EXCLUDED.car_id,
        drive_type = EXCLUDED.drive_type,
        gearbox = EXCLUDED.gearbox,
        fuel_type = EXCLUDED.fuel_type,
        facelift_version = EXCLUDED.facelift_version
      RETURNING *
      `,
      [input.car_id, input.article_code, input.drive_type, input.gearbox, input.fuel_type, input.facelift_version],
    );

    return result.rows[0];
  }
}
