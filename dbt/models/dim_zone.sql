select zone_id, borough, zone_name, service_zone from {{ source('silver', 'zones') }}
