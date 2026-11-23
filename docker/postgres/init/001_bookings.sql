CREATE TABLE IF NOT EXISTS bookings (
    booking_id  text PRIMARY KEY,
    customer_id text NOT NULL,
    session_id  text NOT NULL,
    campaign_id text NOT NULL,
    origin      text NOT NULL,
    destination text NOT NULL,
    travel_date date NOT NULL,
    status      text NOT NULL,
    currency    text NOT NULL,
    amount      numeric(10, 2) NOT NULL,
    created_at  timestamptz NOT NULL,
    updated_at  timestamptz NOT NULL
);

-- Volumenes existentes: CREATE TABLE IF NOT EXISTS no anade columnas. ADD COLUMN IF NOT EXISTS
-- las crea nullable (un NOT NULL sin DEFAULT falla en tablas con filas); el backfill hace
-- `seed_postgres --rebuild`, que vacia la tabla y recarga todas las filas con valores.
ALTER TABLE bookings ADD COLUMN IF NOT EXISTS origin      text;
ALTER TABLE bookings ADD COLUMN IF NOT EXISTS destination text;
ALTER TABLE bookings ADD COLUMN IF NOT EXISTS travel_date date;
