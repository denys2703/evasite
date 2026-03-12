import fs from 'fs';
import path from 'path';
import { pool } from './pool';

const migrationsDir = path.join(__dirname, 'migrations');

async function ensureMigrationsTable() {
  await pool.query(`
    CREATE TABLE IF NOT EXISTS schema_migrations (
      id SERIAL PRIMARY KEY,
      name VARCHAR(255) UNIQUE NOT NULL,
      executed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );
  `);
}

async function up() {
  await ensureMigrationsTable();
  const files = fs.readdirSync(migrationsDir).filter((f) => f.endsWith('.sql')).sort();

  for (const file of files) {
    const exists = await pool.query('SELECT 1 FROM schema_migrations WHERE name = $1', [file]);
    if (exists.rowCount) continue;

    const fullPath = path.join(migrationsDir, file);
    const sql = fs.readFileSync(fullPath, 'utf8');

    const client = await pool.connect();
    try {
      await client.query('BEGIN');
      await client.query(sql);
      await client.query('INSERT INTO schema_migrations(name) VALUES($1)', [file]);
      await client.query('COMMIT');
      console.log(`Applied migration: ${file}`);
    } catch (error) {
      await client.query('ROLLBACK');
      console.error(`Failed migration: ${file}`);
      throw error;
    } finally {
      client.release();
    }
  }
}

async function down() {
  await ensureMigrationsTable();
  await pool.query('DROP TABLE IF EXISTS logs, modifications, cars, hangers CASCADE');
  await pool.query('DELETE FROM schema_migrations');
  console.log('Rolled back all migrations (destructive)');
}

(async () => {
  try {
    const mode = process.argv[2];
    if (mode === 'down') await down();
    else await up();
  } finally {
    await pool.end();
  }
})().catch((error) => {
  console.error(error);
  process.exit(1);
});
