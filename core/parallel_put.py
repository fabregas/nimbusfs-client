#!/usr/bin/python
"""
Copyright (C) 2012 Konstantin Andrusenko
    See the documentation for further information on copyrights,
    or contact the author. All Rights Reserved.

@package client.parallel_put
@author Konstantin Andrusenko
@date October 24, 2012

This module contains the implementation of PutDataManager
for parallel files upload to fabnet.
"""
import time
import threading
from Queue import Queue

from constants import CHUNK_SIZE, FG_ERROR_TIMEOUT
from logger import logger

QUIT_JOB = None

class PutWorker(threading.Thread):
    QUEUE = Queue()

    def __init__(self, fabnet_gateway, save_metadata_callback):
        threading.Thread.__init__(self)
        self.fabnet_gateway = fabnet_gateway
        self.save_metadata_callback = save_metadata_callback

    def run(self):
        while True:
            job = PutWorker.QUEUE.get()
            try:
                if job == QUIT_JOB:
                    break

                f_path, seek, size, file_md = job

                f_obj = open(f_path, 'rb')
                try:
                    f_obj.seek(seek)
                    data = f_obj.read(size)
                    logger.debug('Read %s %s %s %s'%(file_md.name, seek, size, len(data)))
                finally:
                    f_obj.close()

                try:
                    key, checksum = self.fabnet_gateway.put(data, replica_count=file_md.replica_count)
                except Exception, err:
                    logger.error('Cant put data block from file %s. Wait %s seconds and try again...'%(file_md.name, FG_ERROR_TIMEOUT))
                    time.sleep(FG_ERROR_TIMEOUT)
                    PutWorker.QUEUE.put(job)
                    continue

                file_md.append_chunk(key, checksum, seek, size)

                if file_md.is_all_chunks():
                    logger.debug('File %s is uploaded. Updating metadata...'%file_md.name)
                    self.save_metadata_callback(file_md)
            except Exception, err:
                logger.error('[PutWorker][%s] %s'%(job, err))
            finally:
                PutWorker.QUEUE.task_done()


class PutDataManager:
    def __init__(self, fabnet_gateway, save_metadata_callback, workers_count):
        self.workers = []
        self.fabnet_gateway = fabnet_gateway

        for i in xrange(workers_count):
            worker = PutWorker(fabnet_gateway, save_metadata_callback)
            worker.setName('PutWorker#%i'%i)
            self.workers.append(worker)

    def start(self):
        for worker in self.workers:
            worker.start()

    def stop(self):
        for worker in self.workers:
            PutWorker.QUEUE.put(QUIT_JOB)

        for worker in self.workers:
            if worker.is_alive():
                worker.join()

    def put_file(self, file_md, file_path):
        full_chunks_cnt = file_md.size / CHUNK_SIZE
        for i in xrange(full_chunks_cnt):
            PutWorker.QUEUE.put((file_path, i*CHUNK_SIZE, CHUNK_SIZE, file_md))

        rest =  file_md.size % CHUNK_SIZE
        if rest:
            PutWorker.QUEUE.put((file_path, full_chunks_cnt*CHUNK_SIZE, rest, file_md))

