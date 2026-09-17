select zone_id, hour_at from {{ ref('fct_hourly') }}
group by 1,2 having count(*) != 1
union all
select zone_id, hour_at from {{ ref('fct_hourly') }} where trips < 0 or (complete and trips is null)
