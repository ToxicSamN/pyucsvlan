

from influxdb import InfluxDBClient

class InfluxDB(InfluxDBClient):

    def chunk_and_send(self, stats):
