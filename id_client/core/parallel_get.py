#!/usr/bin/python
"""
Copyright (C) 2012 Konstantin Andrusenko
    See the documentation for further information on copyrights,
    or contact the author. All Rights Reserved.

@package client.parallel_get
@author Konstantin Andrusenko
@date October 24, 2012

This module contains the implementation of GetDataManager
for parallel files download from fabnet.
"""
import time
import tempfile
import threading
import hashlib
from Queue import Queue

from constants import FG_ERROR_TIMEOUT
from logger import logger

QUIT_JOB = None

class FileStreem:
    def __init__(self, file_name, blocks_count):
        self.__lock = threading.Lock()
        self.file_name = file_name
        self.blocks_count = blocks_count
        self.downloaded_blocks = 0
        self.file_obj = tempfile.NamedTemporaryFile(prefix='nibbler-download-%s-'%file_name)
        self.is_error = False

    def save_block(self, seek, data):
        self.__lock.acquire()
        try:
            self.downloaded_blocks += 1
            fobj = None
            try:
                fobj = open(self.file_obj.name, 'r+b')
                fobj.seek(seek)
                fobj.write(data)
                logger.debug('Saved %s %s %s'%(self.file_name, seek, len(data)))
            except Exception, err:
                self.is_error = True
                raise err
            finally:
                if fobj:
                    fobj.close()

        finally:
            self.__lock.release()

    def wait_get(self):
        while True:
            self.__lock.acquire()
            try:
                if self.downloaded_blocks >= self.blocks_count:
                    break
            finally:
                self.__lock.release()

        if self.is_error:
            self.file_obj.close()
            raise Exception('Saving downloaded file %s failed!'%self.file_name)

    def get_file_obj(self):
        return self.file_obj


class GetWorker(threading.Thread):
    QUEUE = Queue()

    def __init__(self, fabnet_gateway):
        threading.Thread.__init__(self)
        self.fabnet_gateway = fabnet_gateway

    def run(self):
        while True:
            job = GetWorker.QUEUE.get()
            try:
                if job == QUIT_JOB:
                    break

                out_streem, key, replica_count, seek, checksum = job

                try:
                    data = self.fabnet_gateway.get(key, replica_count)
                    if not data:
                        raise Exception('No data found...')
                except Exception, err:
                    logger.error('Cant get data block for key %s. Details: %s'%(key, err))
                    logger.error('Wait %s seconds and try again...'%(FG_ERROR_TIMEOUT,))
                    time.sleep(FG_ERROR_TIMEOUT)
                    GetWorker.QUEUE.put(job)
                    continue

                if checksum != hashlib.sha1(data).hexdigest():
                    raise Exception('Data block for key %s has invalid checksum!'%key)

                out_streem.save_block(seek, data)
            except Exception, err:
                logger.error('[GetWorker][%s] %s'%(job, err))
            finally:
                GetWorker.QUEUE.task_done()


class GetDataManager:
    def __init__(self, fabnet_gateway, workers_count):
        self.workers = []
        self.fabnet_gateway = fabnet_gateway

        for i in xrange(workers_count):
            worker = GetWorker(fabnet_gateway)
            worker.setName('GetWorker#%i'%i)
            self.workers.append(worker)

    def start(self):
        for worker in self.workers:
            worker.start()

    def stop(self):
        for worker in self.workers:
            GetWorker.QUEUE.put(QUIT_JOB)

        for worker in self.workers:
            if worker.is_alive():
                worker.join()

    def get_file(self, file_md):
        file_streem = FileStreem(file_md.name, len(file_md.chunks))

        for chunk in file_md.chunks:
            GetWorker.QUEUE.put((file_streem, chunk.key, file_md.replica_count, chunk.seek, chunk.checksum))

        return file_streem
