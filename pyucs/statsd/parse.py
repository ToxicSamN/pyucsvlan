
import queue
from datetime import datetime
from pyucs.logging import Logger


LOGGERS = Logger(log_file='/var/log/ucs_parser.log', error_log_file='/var/log/ucs_parser_err.log')


class Parser:

    def __init__(self, statsq, influxq):
        self.in_q = statsq
        self.out_q = influxq

        self._run()

    def _run(self):
        logger = LOGGERS.get_logger('Parser')
        logger.info('Parser process Started')
        while True:
            try:
                data = self.in_q.get_nowait()
                influx_series = self._parse_data(data)
                if influx_series:
                    for i in influx_series:
                        self.out_q.put_nowait(i)
            except queue.Empty:
                pass
        logger.info('Parser process Stopped')

    def _parse_data(self, data):

        json_series = []

        if data.rn == 'vnic-stats':
            pn_dn = "{}/{}/{}".format(data.dn.split('/')[0],
                                      data.dn.split('/')[1],
                                      data.dn.split('/')[2]
                                      )

            service_profile = [s for s in data._handle.LsServer if s.pn_dn == pn_dn][0]
            metrics = ['network.tx.rate', 'network.rx.rate', 'network.tx.drop',
                       'network.rx.drop', 'network.tx.error', 'network.rx.error']
            for metric in metrics:
                json_series.append(self._format_json(rawdata=data,
                                                     metric_name=metric,
                                                     metric_value=self._get_vnic_value(metric, data),
                                                     parent=service_profile.name,
                                                     equipment_dn=pn_dn,
                                                     ))
        return json_series

    @staticmethod
    def _format_json(rawdata, metric_name, metric_value, parent, equipment_dn):
        logger = LOGGERS.get_logger('Parser _format_json')
        collected_time = datetime.strptime(rawdata.time_collected, '%Y-%m-%dT%H:%M:%S.%f')
        collected_time = datetime.utcfromtimestamp(collected_time.timestamp())
        logger.info("Collection Date/Time UTC timestamp {}".format(collected_time.__str__()))
        # utc_now = datetime.utcnow()
        # logger.info("Curernt Date/Time UTC timestamp {}".format(utc_now.__str__()))
        # time_delata = utc_now - collected_time
        influx_time = collected_time.__str__()
        logger.info("Influx submitted Date/Time UTC timestamp {}".format(influx_time.__str__()))
        return {
            'time': influx_time,
            'measurement': metric_name,
            'fields': {'value': metric_value, },
            'tags': {
                'parent': parent,
                'parent_dn': equipment_dn,
                'ucs': rawdata._handle.ucs,
                'device': rawdata._ManagedObject__parent_dn.split('/')[
                    len(rawdata._ManagedObject__parent_dn.split('/')) - 1],
            },
        }

    @staticmethod
    def _get_vnic_value(metric, data):
        if metric == 'network.tx.rate':
            # convert to Gbps
            return float(((float(data.bytes_rx_delta)/60)*8)/1000000000)
        elif metric == 'network.rx.rate':
            # convert to Gbps
            return float(((float(data.bytes_tx_delta) / 60) * 8) / 1000000000)
        elif metric == 'network.tx.drop':
            return float(data.dropped_rx_delta)
        elif metric == 'network.rx.drop':
            return float(data.dropped_tx_delta)
        elif metric == 'network.tx.error':
            return float(data.errors_rx_delta)
        elif metric == 'network.rx.error':
            return float(data.errors_tx_delta)
        else:
            return None
