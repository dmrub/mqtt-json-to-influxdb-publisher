# MQTT JSON to InfluxDB Publisher
This tool converts MQTT messages in JSON format and pushes them to InfluxDB database.

## Usage
```
main.py [options]

Run MQTT to JSON InfluxDB Publisher.

optional arguments:
  -h, --help            show this help message and exit
  -d, --debug           enable debug mode (default: False)
  -c, --log-to-console  output log to console (default: False)
  -l [FILE], --log-file [FILE]
                        output log to file (default: None)
  --log-max-bytes MAX_BYTES
                        Rollover whenever the current log file is nearly
                        MAX_BYTES in length (default: 1048576)
  --log-backup-count BACKUP_COUNT
                        If BACKUP_COUNT is non-zero, the system will save old
                        log files by appending the extensions '.1', '.2' etc.,
                        to the filename. (default: 3)
  --mqtt-host MQTT_HOST
                        MQTT server host (default: localhost)
  --mqtt-port MQTT_PORT
                        MQTT server port (default: 1883)
  --influxdb-uri INFLUXDB_URI
                        InfluxDB API URI (default: http://localhost:8086)
  --influxdb-dbname INFLUXDB_DBNAME
                        InfluxDB database name (default: mqtt)
  --mqtt-topics MQTT_TOPIC [MQTT_TOPIC ...]
                        MQTT topics to subscribe (default: ['#'])
  --mqtt-qos QOS        MQTT QoS value for messages (default: 0)
  --version             show program's version number and exit
```
