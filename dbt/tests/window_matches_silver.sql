{#- Validation 6b: la ventana D-4..D de Gold coincide con Silver. Anti-join en los dos sentidos
    por booking_id; devuelve las filas que sobran o faltan (esperado: 0 filas). -#}
with silver_window as (
    select booking_id
    from {{ source('silver', 'bookings_eur') }}
    where date(changed_at) between date_add('day', -4, date '{{ var("run_date") }}') and date '{{ var("run_date") }}'
),

gold_window as (
    select booking_id
    from {{ ref('spike_bookings_window') }}
    where changed_date between date_add('day', -4, date '{{ var("run_date") }}') and date '{{ var("run_date") }}'
)

select 'missing_in_gold' as side, s.booking_id
from silver_window as s
left join gold_window as g on s.booking_id = g.booking_id
where g.booking_id is null

union all

select 'orphan_in_gold' as side, g.booking_id
from gold_window as g
left join silver_window as s on g.booking_id = s.booking_id
where s.booking_id is null
