import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import pg from 'pg';
import { DEFAULT_DATABASE_URL, saveChanges } from './db';
import { initialDispatchState } from '../src/logic/dispatch';
import { loadFakeData } from '../src/data/fakeData';

// Creates (or recreates) the local development database from db/schema.sql
// and loads the fake data, shifted so its newest timestamp is a few minutes ago.
//   npm run db:reset   — DROPS every table in the target database first.

const url = new URL(process.env.DATABASE_URL ?? DEFAULT_DATABASE_URL);
const dbName = url.pathname.slice(1);

if (!process.argv.includes('--reset')) {
  console.error('Refusing to run without --reset: this drops every table in', dbName);
  process.exit(1);
}
if (!/^[a-z_][a-z0-9_]*$/.test(dbName)) {
  console.error(`Unexpected database name "${dbName}".`);
  process.exit(1);
}

const schemaPath = fileURLToPath(new URL('../../db/schema.sql', import.meta.url));

async function main() {
  // 1. Make sure the database exists (connect to the default "postgres" database to create it).
  const admin = new pg.Client({ connectionString: Object.assign(new URL(url), { pathname: '/postgres' }).toString() });
  await admin.connect();
  const exists = await admin.query('SELECT 1 FROM pg_database WHERE datname = $1', [dbName]);
  if (exists.rowCount === 0) {
    await admin.query(`CREATE DATABASE ${dbName}`);
    console.log(`Created database ${dbName}.`);
  }
  await admin.end();

  // 2. Recreate the schema and load the fake data in one transaction.
  const db = new pg.Client({ connectionString: url.toString() });
  await db.connect();
  try {
    await db.query('BEGIN');
    await db.query('DROP SCHEMA IF EXISTS public CASCADE; CREATE SCHEMA public;');
    await db.query(readFileSync(schemaPath, 'utf8'));
    const empty = initialDispatchState({ incidents: [], health: [], teams: [], travelTimes: [] });
    const data = initialDispatchState(loadFakeData({ shiftTo: new Date() }));
    await saveChanges(db, empty, data);
    await db.query('COMMIT');
    console.log(
      `Loaded ${data.incidents.length} incidents, ${data.health.length} health records, ${data.teams.length} teams, ` +
        `${data.travelTimes.length} travel times into ${dbName}.`,
    );
  } catch (err) {
    await db.query('ROLLBACK').catch(() => {});
    const e = err as { code?: string; message?: string };
    console.error(`Seeding failed: ${e.code ?? ''} ${e.message ?? err}`);
    process.exitCode = 1;
  } finally {
    await db.end();
  }
}

main();
