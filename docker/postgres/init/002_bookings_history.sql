-- CDC ligero: cada alta o cambio en `bookings` deja una fila en `bookings_history`.
-- `history_id` desempata las versiones con el mismo `changed_at`; para que sea
-- reproducible, el backfill hace TRUNCATE ... RESTART IDENTITY y aplica los
-- cambios en orden determinista (seed_postgres.py --rebuild).
CREATE TABLE IF NOT EXISTS bookings_history (
    history_id  bigserial PRIMARY KEY,
    booking_id  text NOT NULL,
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
    updated_at  timestamptz NOT NULL,
    changed_at  timestamptz NOT NULL
);

-- Volumenes existentes: ver 001_bookings.sql (columnas nullable; `seed_postgres --rebuild`
-- vacia la tabla y las rellena).
ALTER TABLE bookings_history ADD COLUMN IF NOT EXISTS origin      text;
ALTER TABLE bookings_history ADD COLUMN IF NOT EXISTS destination text;
ALTER TABLE bookings_history ADD COLUMN IF NOT EXISTS travel_date date;

CREATE INDEX IF NOT EXISTS bookings_history_changed_at_idx
    ON bookings_history (changed_at, history_id);

CREATE OR REPLACE FUNCTION bookings_history_write() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    INSERT INTO bookings_history (
        booking_id, customer_id, session_id, campaign_id,
        origin, destination, travel_date,
        status, currency, amount, created_at, updated_at, changed_at
    ) VALUES (
        NEW.booking_id, NEW.customer_id, NEW.session_id, NEW.campaign_id,
        NEW.origin, NEW.destination, NEW.travel_date,
        NEW.status, NEW.currency, NEW.amount, NEW.created_at, NEW.updated_at, NEW.updated_at
    );
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS bookings_history_trg ON bookings;
CREATE TRIGGER bookings_history_trg
    AFTER INSERT OR UPDATE ON bookings
    FOR EACH ROW EXECUTE FUNCTION bookings_history_write();
