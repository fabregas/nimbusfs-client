import os
import copy
import tempfile
import shutil
import threading
import time
import hashlib
import random
from datetime import datetime

from id_client.idepositbox_client import IdepositboxClient
from nimbus_client.core import fabnet_gateway
from nimbus_client.core.fri.fri_base import FabnetPacketResponse
from nimbus_client.core import data_block
from id_client.idepositbox_client import IdepositboxClient, Config
from id_client.constants import MOUNT_EXPORT

OK = 'ok'
FAIL = 'fail'
WAIT = 'wait'

class MockedFriClient:
    #modes: OK FAIL WAIT
    MODE = OK
    _LOCK = threading.Lock()

    @classmethod
    def get_mode(cls):
        cls._LOCK.acquire()
        try:
            return cls.MODE
        finally:
            cls._LOCK.release()

    @classmethod
    def change_mode(cls, new_mode):
        cls._LOCK.acquire()
        try:
            cls.MODE = new_mode
        finally:
            cls._LOCK.release()

    def __init__(self, is_ssl=None, cert=None, session_id=None):
        if not is_ssl:
            raise Exception('[MockedFriClient] NimbusFS backend accept SSL based transport only!')
        if not cert:
            raise Exception('[MockedFriClient] No client certificate found!')

        try:
            int(session_id)
        except ValueError:
            raise Exception('[MockedFriClient] Invalid session_id "%s"'%session_id)

        self.data_map = {}

    def call_sync(self, node_addr, packet, FRI_CLIENT_TIMEOUT):
        if self.get_mode() == FAIL:
            return FabnetPacketResponse(ret_code=1, ret_message='test exception from backend')
        elif self.get_mode() == WAIT:
            while self.get_mode() == WAIT:
                #print 'waiting MockedFriClient.call_sync()...'
                time.sleep(1)
            return self.call_sync(node_addr, packet, FRI_CLIENT_TIMEOUT)

        if packet.method == 'GetKeysInfo':
            ret_keys = []
            key = packet.parameters.get('key', None)
            ret_keys.append((key, False, 'some_mode_addr'))
            return FabnetPacketResponse(ret_parameters={'keys_info': ret_keys})

        elif packet.method == 'PutKeysInfo':
            primary_key = packet.parameters.get('key', None)
            if not primary_key:
                primary_key = hashlib.sha1(datetime.utcnow().isoformat()+str(random.randint(0,1000000))).hexdigest()
            return FabnetPacketResponse(ret_parameters={'key_info': (primary_key, 'some_mode_addr')})

        elif packet.method == 'ClientPutData':
            replica_count = packet.parameters.get('replica_count', None)
            if replica_count != 2:
                return FabnetPacketResponse(ret_code=1, ret_message='invalid replica_count value "%s"'%replica_count)
            key = packet.parameters.get('key', None)
            if key:
                primary_key = key
            else:
                primary_key = hashlib.sha1(datetime.utcnow().isoformat()+str(random.randint(0,1000000))).hexdigest()

            data = packet.binary_data.data()
            source_checksum = hashlib.sha1(data).hexdigest()

            self.data_map[primary_key] = data

            time.sleep(.1)
            return FabnetPacketResponse(ret_parameters={'key': primary_key, 'checksum': source_checksum})

        elif packet.method == 'GetDataBlock':
            time.sleep(0.1)

            raw_data = self.data_map.get(packet.parameters['key'], None)
            if raw_data is None:
                return FabnetPacketResponse(ret_code=324, ret_message='No data found!')

            return FabnetPacketResponse(binary_data=raw_data, ret_parameters={'checksum': hashlib.sha1(raw_data).hexdigest()})


class MockedIdepositboxClient(IdepositboxClient):
    MODE = OK
    MODE_AREA = {}
    FABNET_GW = MockedFriClient
    _LOCK = threading.Lock()

    @classmethod
    def get_mode(cls):
        cls._LOCK.acquire()
        try:
            return cls.MODE
        finally:
            cls._LOCK.release()

    @classmethod
    def get_mode_area(cls):
        cls._LOCK.acquire()
        try:
            if not cls.MODE_AREA:
                return {}
            return copy.copy(cls.MODE_AREA)
        finally:
            cls._LOCK.release()

    @classmethod
    def simulate_id_client(cls, mode, area=None, flush=False):
        cls._LOCK.acquire()
        try:
            cls.MODE = mode
            if flush:
                cls.MODE_AREA = {}
            if isinstance(area, str):
                area = {area: None}
            if not isinstance(area, dict):
                raise Exception('area argument should be string or dict!')
            cls.MODE_AREA.update(area)
        finally:
            cls._LOCK.release()

    @classmethod
    def simulate_fabnet_gw(cls, mode):
        cls.FABNET_GW.change_mode(mode)

    def __getattribute__(self, attr):
        while MockedIdepositboxClient.get_mode() == WAIT:
            area = MockedIdepositboxClient.get_mode_area()
            if area and attr not in area:
                break
            time.sleep(1)
            #print 'IdepositboxClient is locked...'

        area = MockedIdepositboxClient.get_mode_area()
        if MockedIdepositboxClient.get_mode() == FAIL:
            if not area or attr in area:
                raise Exception('Simulated exception from IdepositboxClient.%s'%attr)

        if attr in area:
            #return mocked method
            return lambda *a, **kwa: area[attr]

        return IdepositboxClient.__getattribute__(self, attr)


def get_test_idepositbox_client(log_level='INFO'):
    cache_dir = os.path.join(tempfile.gettempdir(), 'test_idepositbox_cache')
    if os.path.exists(cache_dir):
        shutil.rmtree(cache_dir)
    os.mkdir(cache_dir)
    conf_path = os.path.join(cache_dir, 'test_idepositbox.conf')

    Config.get_config_file_path = lambda a: conf_path
    fabnet_gateway.FriClient = MockedFriClient
    data_block.READ_TRY_COUNT = 1

    config = Config()
    config.log_level = log_level
    config.mount_type = MOUNT_EXPORT
    config.cache_dir = cache_dir
    config.webdav_bind_host = '127.0.0.1'
    config.webdav_bind_port = 9997
    config.ca_address = '127.0.0.1:9998'
    config.save()
    return MockedIdepositboxClient()


'''
use case:

    from util_mocked_id_client import get_test_idepositbox_client, OK, WAIT, FAIL
    from id_client.web.web_server import MgmtServer

    mocked_id_client = get_test_idepositbox_client()
    mgmt_console = MgmtServer('127.0.0.1', 9999, mocked_id_client)
    mgmt_console.start()
    ...
    mocked_id_client.simulate_id_client(FAIL, area='get_available_media_storages')
    ...
    mocked_id_client.simulate_fabnet_gw(WAIT)
    ...
    mocked_id_client.simulate_fabnet_gw(OK)
    ...
    mocked_id_client.simulate_id_client(OK, area={'get_available_media_storages', mocked_resp})
    ...
    mgmt_console.stop()
    ...
'''

