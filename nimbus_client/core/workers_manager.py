#!/usr/bin/python
"""
Copyright (C) 2012 Konstantin Andrusenko
    See the documentation for further information on copyrights,
    or contact the author. All Rights Reserved.

@package nimbus_client.core.workers_manager
@author Konstantin Andrusenko
@date October 24, 2012

This module contains the implementation of PutWorker, GetWorker and WorkersManager classes
"""
import time
import threading
from Queue import Queue

from constants import MAX_DATA_BLOCK_SIZE, FG_ERROR_TIMEOUT
from logger import logger

QUIT_JOB = None

class PutWorker(threading.Thread):
    def __init__(self, queue, fabnet_gateway, transactions_manager):
        threading.Thread.__init__(self)
        self.fabnet_gateway = fabnet_gateway
        self.transactions_manager = transactions_manager
        self.queue = transactions_manager.get_upload_queue()

    def stop(self):
        self.queue.put(QUIT_JOB)

    def run(self):
        while True:
            job = self.queue.get()
            data_block = None
            try:
                if job == QUIT_JOB:
                    break
                
                transaction, seek = job
                data_block,_ = transaction.get_data_block(seek)

                try:
                    key = self.fabnet_gateway.put(data_block, replica_count=transaction.get_replica_count(), allow_rewrite=False)
                except Exception, err:
                    logger.error('Put data block error: %s'%err)
                    logger.error('Cant put data block from file %s. Wait %s seconds and try again...'%(transaction.get_file_path(), FG_ERROR_TIMEOUT))
                    time.sleep(FG_ERROR_TIMEOUT)
                    self.queue.put(job)
                    continue

                self.transactions_manager.update_transaction(transaction.get_id(), seek, is_failed=False, foreign_name=key)
            except Exception, err:
                logger.error('[PutWorker][%s] %s'%(job, err))
            finally:
                if data_block:
                    data_block.close()
                self.queue.task_done()

class GetWorker(threading.Thread):
    def __init__(self, queue, fabnet_gateway, transactions_manager):
        threading.Thread.__init__(self)
        self.fabnet_gateway = fabnet_gateway
        self.transactions_manager = transactions_manager
        self.queue = transactions_manager.get_download_queue()

    def stop(self):
        self.queue.put(QUIT_JOB)

    def run(self):
        while True:
            out_streem = data = None
            job = self.queue.get()
            w_db = None
            try:
                if job == QUIT_JOB:
                    break

                transaction, seek = job
                data_block,_ = transaction.get_data_block(seek)
                w_db = data_block.clone()

                self.fabnet_gateway.get(data_block.get_name(), transaction.get_replica_count(), w_db)
                w_db.close()
            except Exception, err:
                logger.error('[GetWorker][%s] %s'%(job, err))
            finally:
                if w_db:
                    w_db.close()
                self.queue.task_done()


class WorkersManager:
    def __init__(self, worker_class, fabnet_gateway, transactions_manager, workers_count):
        self.__workers = []
        self.__queue = Queue()

        for i in xrange(workers_count):
            worker = worker_class(self.__queue, fabnet_gateway, transactions_manager)
            worker.setName('%s#%i'%(worker_class.__name__, i))
            self.__workers.append(worker)

    def start(self):
        for worker in self.__workers:
            worker.start()

    def stop(self):
        for worker in self.__workers:
            worker.stop()

        for worker in self.__workers:
            if worker.is_alive():
                worker.join()

