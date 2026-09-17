with observed as (
    select pickup_zone_id as zone_id, date_trunc('hour', pickup_at) as hour_at,
           count(*)::bigint as trips, sum(total_usd) as total_usd,
           sum(duration_minutes) as duration_minutes
    from {{ ref('fct_trips') }} group by 1,2
)
select z.zone_id, h.hour_at, z.borough, h.complete,
       case when h.complete then coalesce(o.trips,0) else o.trips end as trips,
       coalesce(o.total_usd,0) as total_usd, coalesce(o.duration_minutes,0) as duration_minutes
from {{ ref('dim_zone') }} z cross join {{ ref('dim_hour') }} h
left join observed o on o.zone_id=z.zone_id and o.hour_at=h.hour_at
