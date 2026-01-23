CREATE KEYSPACE IF NOT EXISTS air_quality WITH replication = {'class': 'SimpleStrategy', 'replication_factor': 2};
use air_quality;
CREATE TABLE measurements (
    station_id text,
    name text,
    value float,
    unit text,
    parameter text,
    measure_date timestamp,
    PRIMARY KEY ((station_id), measure_date)
) WITH CLUSTERING ORDER BY (measure_date DESC);

CREATE TABLE IF NOT EXISTS air_quality.daily_averages (
    station_id text,
    name text,
    day date,
    avg_value float,
    unit text,
    parameter text,
    PRIMARY KEY ((station_id), day)
) WITH CLUSTERING ORDER BY (day DESC);
