-- Engine: DuckDB
-- stg_transportation — clean dirty data_transportation (4.2M truck trips, line-haul):
--   from/to_warehouse_id DOUBLE nullable → to_bigint; dt VARCHAR → DATE.
--   trip_code prefix 'T' (PK). Loại heavy_issue. transit_hours = arrival - departure.
with source as (
    select * from {{ source('raw', 'data_transportation') }}
    where {{ keep_non_quarantine('_data_quality') }}
)

select
    {{ clean_text('trip_code') }}            as trip_code,
    {{ to_bigint('from_warehouse_id') }}     as from_warehouse_id,
    {{ to_bigint('to_warehouse_id') }}       as to_warehouse_id,
    cast(departure_time as timestamp)        as departure_at,
    cast(arrival_time as timestamp)          as arrival_at,
    cast(driver_id as bigint)                as driver_shipper_id,
    upper(regexp_replace(trim(coalesce(truck_plate_number, '')), '\s+', '', 'g')) as truck_plate_number,
    cast(vehicle_weight_kg as double)        as vehicle_weight_kg,
    cast(n_packages as bigint)               as n_packages,
    {{ parse_dt('dt') }}                     as dt,
    _data_quality,
    case
        when arrival_time is not null and departure_time is not null
        then date_diff('second', cast(departure_time as timestamp), cast(arrival_time as timestamp)) / 3600.0
    end                                      as transit_hours
from source
