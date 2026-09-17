select hour_at, sum(trips) as trips, sum(total_usd) as total_usd,
       bool_and(complete) as complete
from {{ ref('fct_hourly') }} group by 1
