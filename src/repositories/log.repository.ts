import { pool } from '../db/pool';
import { LogEntry } from '../types/domain';

export class LogRepository {
  async create(input: { car_id?: number | null; event_type: string; description: string }): Promise<LogEntry> {
    const result = await pool.query<LogEntry>(
      'INSERT INTO logs (car_id, event_type, description) VALUES ($1,$2,$3) RETURNING *',
      [input.car_id ?? null, input.event_type, input.description],
    );
    return result.rows[0];
  }
}
