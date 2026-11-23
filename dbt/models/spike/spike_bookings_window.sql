{#- Spike 0c: incremental merge sobre Iceberg con ventana D-4..D de silver.bookings_eur (Design Decision 7).
    Se usa bookings_eur porque sessions no existe en dev. La fecha es date(changed_at) (DDL de bookings_eur).
    El pre_hook borra la ventana en el destino; el merge con incremental_predicates la reescribe.
    Fecha logica solo por var('run_date'), nunca now(). -#}
{{
    config(
        materialized='incremental',
        table_type='iceberg',
        incremental_strategy='merge',
        unique_key='booking_id',
        partitioned_by=['day(changed_date)'],
        incremental_predicates=[
            "target.changed_date between date_add('day', -4, date '" ~ var('run_date') ~ "') and date '" ~ var('run_date') ~ "'"
        ],
        pre_hook=[
            "{% if is_incremental() %}delete from {{ this }} where changed_date between date_add('day', -4, date '" ~ var('run_date') ~ "') and date '" ~ var('run_date') ~ "'{% endif %}"
        ],
    )
}}

select
    booking_id,
    history_id,
    changed_at,
    date(changed_at) as changed_date,
    currency,
    amount,
    fx_rate_applied,
    amount_eur
from {{ source('silver', 'bookings_eur') }}
where date(changed_at) between date_add('day', -4, date '{{ var("run_date") }}') and date '{{ var("run_date") }}'
