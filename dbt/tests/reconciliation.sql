select 1 as failed
where (select count(*) from {{ ref('fct_trips') }}) !=
      (select coalesce(sum(trips),0) from {{ ref('fct_hourly') }})
