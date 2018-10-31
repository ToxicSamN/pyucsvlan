
from multiprocessing import Pool
from multiprocessing import cpu_count
from pyucs.logging import Logger


LOGGERS = Logger(log_file='/var/log/ucs_stats.log', error_log_file='/var/log/ucs_stats_err.log')


class StatsCollector:

    def __init__(self, ucs):
        self.ucs = ucs
        self.query_results = []
        self.thread_results = None

    def query_stats(self, statsq):
        logger = LOGGERS.get_logger('StatsCollector')
        logger.info('StatsCollector started')
        parallelism_thread_count = cpu_count()

        vnics = self.ucs.get_vnic()
        vhbas = self.ucs.get_vhba()

        # create thread pool args and launch _query_thread_pool
        #  define the threading group sizes. This will pair down the number of entities
        #  that will be collected per thread and allowing ucs to multi-thread the queries
        thread_pool_args = []
        thread = 1

        for chunk in vnics:
            thread_pool_args.append(
                [self.ucs, chunk, 'vnic', thread, statsq])
            thread += 1

        for chunk in vhbas:
            thread_pool_args.append(
                [self.ucs, chunk, 'vhba', thread, statsq])
            thread += 1

        # this is a custom thread throttling function. Could probably utilize ThreadPools but wanted to have a little
        #  more control.
        self._query_thread_pool(thread_pool_args,
                                pool_size=parallelism_thread_count)

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
        ucs, adapter_chunk, adaptor_type, thread_id, statsq = thread_args

        data = None
        if adaptor_type == 'vnic':
            data = ucs.get_vnic_stats(vnic=adapter_chunk, ignore_error=True)
        elif adaptor_type == 'vhba':
            data = ucs.get_vhba_stats(vhba=adapter_chunk, ignore_error=True)

        if data:
            statsq.put_nowait(data)

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


