
import sys
import threading
import logging
import logging.handlers
from pyucs.logging import Logger
from influxdb import InfluxDBClient


LOGGERS = Logger(log_file='/var/log/ucs_influx.log', error_log_file='/var/log/ucs_influx_err.log')


class InfluxDB(object):
    """ Creating an Object to hold other objects """

    def __init__(self, data, influxdb_client):
        self.data = data
        self.influxdb_client = influxdb_client
        self.time_precision = 'n'
        self.protocol = 'json'


class InfluxDBThread(threading.Thread):
    """
     Inheritence from threading.thread and override the run method
     This is used ro start a new thread for sending influx data
    """

    def __init__(self, influx_obj, thread_id, entity_name=''):
        threading.Thread.__init__(self)
        self.influx_data = influx_obj.data
        self.influxdb_client = influx_obj.client
        self.time_precision = influx_obj.time_precision
        self.protocol = influx_obj.protocol
        self.thread_id = thread_id
        self.entity_name = entity_name

    def run(self):
        logger = LOGGERS.get_logger(str('InfluxDBThread'))
        try:
            logger.info("{}: Total Metrics Being Sent to InfluxDB for {}: {}".format(str(self.thread_id),
                                                                                     self.entity_name,
                                                                                     len(self.influx_data)))

            InfluxDBThread.send_influx((self.influx_data,
                                        self.influxdb_client,
                                        self.thread_id,
                                        self.entity_name))

        except BaseException as e:
            logger.error("{}: Total Metrics Being Sent to InfluxDB for {}: {}".format(str(self.thread_id),
                                                                                      self.entity_name,
                                                                                      len(self.influx_data)))
            logger.exception('{}: Exception: {}'.format(str(self.thread_id), e))
            try:
                logger.info("TRY AGAIN for {}: {}".format(self.entity_name, str(self.thread_id)))
                influx_client = InfluxDBClient(host=self.influxdb_client._host,  # args.TelegrafIP
                                               port=self.influxdb_client._port,  # 8186
                                               username=self.influxdb_client._username,
                                               password=self.influxdb_client._password,
                                               database=self.influxdb_client._database,
                                               timeout=self.influxdb_client._timeout,
                                               retries=self.influxdb_client._retries)
                c_count = 1
                for chunk in InfluxDBThread.chunk_it(self.influx_data, chunk_size=1000):
                    try:
                        influx_client.write_points(chunk,
                                                   time_precision=self.time_precision,
                                                   protocol=self.protocol)
                        c_count += 1
                    except:
                        logger.exception('RETRY FAILED!!! {} Chunk {}: {}'.format(self.entity_name,
                                                                                  str(c_count),
                                                                                  str(self.thread_id)))
                        c_count += 1
                        pass

            except BaseException as e:
                logger.exception('RETRY FAILED!!! {}: {}'.format(self.entity_name,
                                                                 str(self.thread_id)))

    @staticmethod
    def send_influx(args):

        influx_series, influx_client, thread_id, entity_name = args

        logger = LOGGERS.get_logger('send_influx')

        keep_running = True
        while keep_running:
            try:
                influx_client.write_points(influx_series,
                                           time_precision='n',
                                           protocol='json')
                keep_running = False
            except BaseException as e:
                if not InfluxDBThread.influx_chunk_n_send(influx_series, influx_client, thread_id):
                    logger.exception('RETRY FAILED {}\t{}'.format(entity_name, e))
                break

    @staticmethod
    def influx_chunk_n_send(influx_series, influx_client, id=''):

        if len(influx_series) > 1:
            count = 0
            for chunk in InfluxDBThread.chunk_it(influx_series, chunk_size=(len(influx_series) / 2)):
                count += 1
                try:
                    # logger.info('sending chunk {}:{}'.format(id, count))
                    influx_client.write_points(chunk, time_precision='n', protocol='json')
                except:
                    # logger.error('Try Again Chunk-n-Send {}:{}'.format(id, count))
                    InfluxDBThread.influx_chunk_n_send(chunk, influx_client, str(str(id) + ':' + str(count)))
            return True
        else:
            try:
                # logger.info('Last try chunk {}:{}'.format(id, 1))
                influx_client.write_points(influx_series, time_precision='n', protocol='json')
                return True
            except:
                # logger.exception('Unable to send influx data {}'.format(influx_series))
                return False

    @staticmethod
    def chunk_it(input_list, chunk_size=1.0):
        avg = len(input_list) / float(chunk_size)
        out = []
        last = 0.0
        while last < len(input_list):
            check_not_null = input_list[int(last):int(last + avg)]
            if check_not_null:
                out.append(check_not_null)
            last += avg
        return out
