select h as hour_at, extract(hour from h)::int as hour_of_day,
       extract(isodow from h)::int as weekday,
       to_char(h, 'YYYY-MM') as source_month, c.complete
from {{ source('silver', 'coverage') }} c
cross join lateral generate_series((c.source_month || '-01')::timestamp,
    (c.source_month || '-01')::timestamp + interval '1 month' - interval '1 hour', interval '1 hour') h
