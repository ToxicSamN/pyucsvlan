
import json
import threading
import sys
import logging
import logging.handlers
from multiprocessing import Process, Pool
from multiprocessing import cpu_count
from pyucs.ucs import Ucs
from pyucs.logging import Logger
from pyucs.influx import InfluxDBThread


LOGGERS = Logger(log_file='/var/log/ucs_stats.log', error_log_file='/var/log/ucs_stats_err.log')


class StatsCollector:

    def __init__(self, ucs):
        self.ucs = ucs
        self.querySpec = []
        self.query_results = []
        self.thread_results = None

    def query_stats(self):
        parallelism_thread_count = cpu_count()

        vnics = self.ucs.get_vnic()
        vhbas = self.ucs.get_vhba()

        # create thread pool args and launch _query_thread_pool
        #  define the threading group sizes. This will pair down the number of entities
        #  that will be collected per thread and allowing ucs to multi-thread the queries
        thread_pool_args = []
        thread = 1

        # for chunk in self.chunk_it(vnics, parallelism_thread_count/2):
        for chunk in vnics:
            # for chunk in chunk_it(specArray, parallelism_thread_count):
            thread_pool_args.append(
                [self.ucs, chunk, 'vnic', thread])
            thread += 1

        for chunk in vhbas:
        # for chunk in self.chunk_it(vhbas, parallelism_thread_count/2):
            # for chunk in chunk_it(specArray, parallelism_thread_count):
            thread_pool_args.append(
                [self.ucs, chunk, 'vhba', thread])
            thread += 1

        # this is a custom thread throttling function. Could probably utilize ThreadPools but wanted to have a little
        #  more control.
        self.query_results = self._query_thread_pool(thread_pool_args,
                                                     pool_size=parallelism_thread_count)

        # self.query_results = self.ucs.get_vnic_stats(vnic=vnics)
        # self.query_results.append(self.ucs.get_vhba_stats(vhba=vhbas))

    def parse_results(self, influxdb_client, parallelism_thread_count=2):
        # create thread pool args and launch _run_thread_pool
        #  define the threading group sizes. This will pair down the number of entities
        #  that will be collected per thread and allowing ucs to multi-thread the queries
        thread_pool_args = []
        thread = 1

        for chunk in self.chunk_it(self.query_results, parallelism_thread_count):
            # for chunk in chunk_it(specArray, parallelism_thread_count):
            thread_pool_args.append(
                [chunk, self.ucs, thread, influxdb_client])
            thread += 1

        # this is a custom thread throttling function. Could probably utilize ThreadPools but wanted to have a little
        #  more control.
        self.thread_results = self._query_thread_pool(thread_pool_args,
                                                      pool_size=parallelism_thread_count)

    @staticmethod
    def _run_thread_pool(func_args_array, pool_size=2):
        """
        This is the multithreading function that maps get_stats with func_args_array
        :param func_args_array:
        :param pool_size:
        :return:
        """

        t_pool = Pool(pool_size)
        results = t_pool.map(StatsCollector._parse_stats, func_args_array)
        t_pool.close()
        t_pool.join()
        return results

    @staticmethod
    def _query_thread_pool(func_args_array, pool_size=2):
        """
        This is the multithreading function that maps get_stats with func_args_array
        :param func_args_array:
        :param pool_size:
        :return:
        """

        t_pool = Pool(pool_size)
        results = t_pool.map(StatsCollector._query_stats, func_args_array)

        return results

    @staticmethod
    def _query_stats(thread_args):
        ucs, adapter_chunk, adaptor_type, thread_id = thread_args

        if adaptor_type == 'vnic':
            return ucs.get_vnic_stats(vnic=adapter_chunk, ignore_error=True)
        elif adaptor_type == 'vhba':
            return ucs.get_vhba_stats(vhba=adapter_chunk, ignore_error=True)

    @staticmethod
    def _parse_stats(thread_args):
        stats, ucs, thread_id, influxdb_client = thread_args

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


