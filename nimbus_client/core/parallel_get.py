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
    def __init__(self, streem_id, file_name, blocks_count, file_to_save, callback_func):
        self.__lock = threading.Lock()
        self.streem_id = streem_id
        self.file_name = file_name
        self.blocks_count = blocks_count
        self.downloaded_blocks = 0
        self.out_file = file_to_save#tempfile.NamedTemporaryFile(prefix='nibbler-download-%s-'%file_name)
        self.callback = callback_func
        self.error = None

        try:
            open(self.out_file, 'w').close()
        except IOError, err:
            raise LocalPathException("Can't open for write file %s"%self.out_file)

    def save_block(self, seek, data):
        self.__lock.acquire()
        try:
            self.downloaded_blocks += 1
            fobj = None
            try:
                if not data:
                    raise Exception('No data found')

                fobj = open(self.out_file, 'r+b')
                fobj.seek(seek)
                fobj.write(data)
                logger.debug('Saved %s %s %s'%(self.file_name, seek, len(data)))
            except Exception, err:
                self.error = "Can't save data block %s:%s. Details: %s"%\
                                (self.file_name, seek, err)
            finally:
                if fobj:
                    fobj.close()

            if self.downloaded_blocks >= self.blocks_count:
                self.callback(self.streem_id, self.error)
        finally:
            self.__lock.release()



class GetWorker(threading.Thread):
    QUEUE = Queue()

    def __init__(self, fabnet_gateway):
        threading.Thread.__init__(self)
        self.fabnet_gateway = fabnet_gateway

    def run(self):
        while True:
            out_streem = data = None
            job = GetWorker.QUEUE.get()
            try:
                if job == QUIT_JOB:
                    break

                out_streem, key, replica_count, seek, checksum = job
                data = self.fabnet_gateway.get(key, replica_count)
                if not data:
                    raise Exception('No data found...')

                if checksum != hashlib.sha1(data).hexdigest():
                    raise Exception('Data block for key %s has invalid checksum!'%key)
            except Exception, err:
                logger.error('[GetWorker][%s] %s'%(job, err))
            finally:
                if out_streem:
                    try:
                        out_streem.save_block(seek, data)
                    except Exception, err:
                        logger.error('[GetWorker][%s][save_block] %s'%(job, err))

                GetWorker.QUEUE.task_done()


class GetDataManager:
    def __init__(self, fabnet_gateway, workers_count, callback_func):
        self.workers = []
        self.fabnet_gateway = fabnet_gateway
        self.get_data_callback = callback_func

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

    def get_file(self, file_md, file_to_save):
        file_streem = FileStreem(file_md.id, file_md.name, len(file_md.chunks), \
                                    file_to_save, self.get_data_callback)

        for chunk in file_md.chunks:
            GetWorker.QUEUE.put((file_streem, chunk.key, file_md.replica_count, \
                                    chunk.seek, chunk.checksum))

