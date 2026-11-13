CREATE TABLE IF NOT EXISTS bookings (
    booking_id  text PRIMARY KEY,
    customer_id text NOT NULL,
    session_id  text NOT NULL,
    campaign_id text NOT NULL,
    status      text NOT NULL,
    currency    text NOT NULL,
    amount      numeric(10, 2) NOT NULL,
    created_at  timestamptz NOT NULL,
    updated_at  timestamptz NOT NULL
);
