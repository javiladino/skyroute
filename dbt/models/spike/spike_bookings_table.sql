{#- Spike 0c: materializacion `table` para confirmar que el drop o rename funciona con los permisos
    de local-dbt (GlueGoldWrite: CreateTable, UpdateTable, DeleteTable en gold). Lee bookings_eur. -#}
{{ config(materialized='table', table_type='iceberg') }}

select
    booking_id,
    date(changed_at) as changed_date,
    amount_eur
from {{ source('silver', 'bookings_eur') }}
where date(changed_at) between date_add('day', -4, date '{{ var("run_date") }}') and date '{{ var("run_date") }}'
