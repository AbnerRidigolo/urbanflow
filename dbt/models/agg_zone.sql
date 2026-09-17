select zone_id, borough, sum(trips) as trips, sum(total_usd) as total_usd,
       sum(duration_minutes)/nullif(sum(trips),0) as avg_duration_minutes
from {{ ref('fct_hourly') }} group by 1,2
