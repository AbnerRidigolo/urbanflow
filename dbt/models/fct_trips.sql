select * from {{ source('silver', 'trips') }}
-- No natural unique trip key exists in the public source. Preserve exact duplicates.
