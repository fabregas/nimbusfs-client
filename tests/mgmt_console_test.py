import os
import sys
import time
import socket
import random
import string
import unittest
from sst.actions import *
from sst import runtests

from tinydav import WebDAVClient, HTTPUserError, HTTPServerError

from util_mocked_id_client import get_test_idepositbox_client, OK, WAIT, FAIL
from id_client.web.web_server import MgmtServer
from id_client.media_storage import MediaStorage
from id_client.constants import *

xpath = get_element_by_xpath

KEY_NAME = 'UFD 2.0 Silicon-Power4G'
KS_PATH = './tests/cert/test_cl_1024.ks'
KS_PASSWORD = 'qwerty123'


class RANDOM:
    def __init__(self, length):
        self.length = length
        self.__seek = 0

    def read(self, rlen):
        if self.__seek >= self.length:
            return None
        if rlen > (self.length - self.__seek):
            rlen = self.length - self.__seek
        self.__seek += rlen
        return ''.join(random.choice(string.letters) for i in xrange(rlen))

    def __len__(self):
        return self.length



class MgmtConsoleTest(runtests.SSTTestCase):
    mocked_id_client = None
    mgmt_console = None

    def init_console(self):
        self.mocked_id_client = get_test_idepositbox_client()
        self.mgmt_console = MgmtServer('127.0.0.1', 9999, self.mocked_id_client)
        self.mgmt_console.start()
        for i in xrange(20):
            if self.mgmt_console.is_ready():
                break
            time.sleep(.5)
        else:
            raise Exception('Management console does not started!')

        self.mocked_id_client.simulate_id_client(OK, area={'get_available_media_storages': []})

    def destroy_console(self):
        self.mocked_id_client.simulate_fabnet_gw(OK)
        self.mgmt_console.stop()
        print 'console is destroyed!'

    def base_console_test(self):
        go_to('http://127.0.0.1:9999/')
        assert_title_contains('iDepositBox')
        wait_for(assert_element, id='home', css_class='active')
        assert_text(xpath('//*[@id="wind"]/div[1]/h3'), 'iDepositBox management console')
        assert_text_contains(xpath('//*[@id="wind"]/div[3]/p'), 'iDepositBox 2013')
        assert_text(xpath('//*[@id="home"]/a'), 'Home')
        assert_text(xpath('//*[@id="settings"]/a'), 'Settings')
        assert_text(xpath('//*[@id="key_mgmt"]/a'), 'Key management')
        assert_text(xpath('//*[@id="about"]/a'), 'About')
        assert_text(xpath('//*[@id="contact"]/a'), 'Contact')

    def home_check(self, ks_list, serv_status, sync_status, inpr_files=[]):
        #ks path
        if len(ks_list) < 2:
            wait_for(assert_element, id='ksPathLabel', css_class='label') 
            assert_displayed('ksPathLabel')
            assert_css_property('ksPath', 'display', 'none')
            if not ks_list:
                assert_element(id='ksPathLabel', css_class='label-important')
                assert_text('ksPathLabel', 'Not found')
            else:
                assert_text('ksPathLabel', ks_list[0])
        else:
            raise Exception('not implemented!')

        #serv status
        wait_for(assert_element, id='serv_status', css_class='label') 
        wait_for(assert_text, 'serv_status', serv_status)
        if serv_status == 'Stopped':
            assert_element(id='serv_status', css_class='label-important')
        elif serv_status == 'Started':
            assert_element(id='serv_status', css_class='label-success')

        #sync_status
        wait_for(assert_text, 'sync_status', sync_status)
        if sync_status == 'All files are synchronized':
            assert_element(id='sync_status', css_class='label-success')
        else:
            assert_element(id='sync_status', css_class='label-warning')

        assert_css_property('inpr_tbl', 'display', 'none')
        if not inpr_files:
            assert_css_property('pr_tl', 'display', 'none')
        else:
            assert_displayed('pr_tl')
            click_element('pr_tl')
            wait_for(assert_displayed, 'inpr_tbl')
            wait_for(assert_table_has_rows, 'inpr_tbl', len(inpr_files)+1)
            assert_text(xpath('//*[@id="d_pr"]/span'), '0%')
            #assert_css_property('pr_tl', 'width', '100%')
            is_up_tr = None
            for i, (f_name, f_size, is_upload) in enumerate(inpr_files):
                tr = i+2
                icon = 'icon-arrow-%s'% ('up' if is_upload else 'down')
                assert_attribute(xpath('//*[@id="inpr_tbl"]/tbody/tr[%i]/td[1]/span[1]'%tr), 'class', icon)
                assert_text_contains(xpath('//*[@id="inpr_tbl"]/tbody/tr[%i]/td[1]'%tr), f_name)
                assert_text(xpath('//*[@id="inpr_tbl"]/tbody/tr[%i]/td[2]'%tr), '%s b'%f_size)
                assert_text(xpath('//*[@id="inpr_tbl"]/tbody/tr[%i]/td[3]'%tr), '0 b')
                if is_upload:
                    assert_attribute(xpath('//*[@id="inpr_tbl"]/tbody/tr[%i]/td[1]/span[2]'%tr), 'class', 'icon-globe')
                if is_up_tr is None:
                    is_up_tr = is_upload
                elif is_up_tr != is_upload:
                    is_up_tr = 'both'

            if is_up_tr==True:
                icon = 'icon-arrow-up'
            elif is_up_tr==False:
                icon = 'icon-arrow-down'
            else:
                icon = 'icon-refresh'
            assert_attribute(xpath('//*[@id="sync_status"]/span'), "class", "%s icon-white"%icon)
            click_element('pr_tl')
            wait_for(assert_css_property, 'inpr_tbl', 'display', 'none')



        #btb
        assert_element(id='startstop', css_class='btn')
        if serv_status == 'Stopped':
            assert_element(id='startstop', css_class='btn-success')
            assert_text('startstop', 'Start service')
        else:
            assert_element(id='startstop', css_class='btn-danger')
            assert_text('startstop', 'Stop service')

        if not ks_list:
            assert_attribute('startstop', 'disabled', 'true')

        assert_css_property('pwdModal', 'display', 'none')
        assert_css_property('spinModal', 'display', 'none')
        assert_css_property('events_list_modal', 'display', 'none')


    def home_click_start(self, pwd):
        click_element('startstop')
        wait_for(assert_displayed, 'pwdModal')
        write_textfield('pwdEdit', pwd, clear=False)
        click_element(get_element(tag='a', text='Start'))
        wait_for(assert_css_property, 'pwdModal', 'display', 'none')
        wait_for(assert_css_property, 'spinModal', 'display', 'none')
        if pwd != KS_PASSWORD:
            assert_text_contains('err_msg', 'pin-code is invalid!')
        else:
            self.home_check([KEY_NAME], 'Started', 'All files are synchronized')

    def home_click_stop(self):
        click_element('startstop')
        self.home_check([KEY_NAME], 'Stopped', 'Unknown')

    def send_file(self, file_name, file_len):
        client = WebDAVClient("127.0.0.1", 9997)
        response = client.put('/%s'%file_name, RANDOM(file_len), "text/plain")
        self.assertEqual(response.statusline, 'HTTP/1.1 201 Created')

    def get_file(self, file_name):
        client = WebDAVClient("127.0.0.1", 9997)
        client.timeout = 1
        try:
            response = client.get('/%s'%file_name)
        except socket.timeout, err:
            pass
        except Exception, err:
            print 'get_file error: %s'%err

    def test_main(self):
        self.init_console()
        try:
            self.base_console_test()
            self.home_check([], 'Stopped', 'Unknown')

            media = MediaStorage(KEY_NAME, KS_PATH)
            self.mocked_id_client.simulate_id_client(OK, area={'get_available_media_storages': [media]})
            wait_for(assert_text, 'ksPathLabel', KEY_NAME) 
            self.home_check([KEY_NAME], 'Stopped', 'Unknown')

            self.home_click_start('fake')
            self.home_click_start(KS_PASSWORD)
            self.home_click_stop()

            self.home_click_start(KS_PASSWORD)

            self.send_file('test_file.txt', 344)
            self.send_file('second_file_name.hmtl', 2331)

            self.mocked_id_client.simulate_fabnet_gw(WAIT)
            dyn_cache = os.path.join(self.mocked_id_client.get_config()['cache_dir'], 'dynamic_cache')
            for item in os.listdir(dyn_cache):
                os.remove(os.path.join(dyn_cache, item))
            self.get_file('test_file.txt')

            self.home_check([KEY_NAME], 'Started', 'In progress ', [('test_file.txt', 344, False)]) 

            self.send_file('third_file.avi', 233)
            self.home_check([KEY_NAME], 'Started', 'In progress ', [('test_file.txt', 344, False), 
                                                            ('third_file.avi', 233, True)]) 
            self.mocked_id_client.simulate_fabnet_gw(OK)
            time.sleep(3.5)

            self.mocked_id_client.simulate_fabnet_gw(WAIT)
            self.send_file('last_file.kst', 666)

            self.home_check([KEY_NAME], 'Started', 'In progress ', [('last_file.kst', 666, True)]) 
            self.mocked_id_client.simulate_fabnet_gw(OK)

            #read alert message
            assert_text_contains(xpath('//*[@id="nimbus_alerts"]/div/p'), 'You have 1 an unread alerts!')
            click_element(xpath('//*[@id="nimbus_alerts"]/div/p/button')) #read btn
            wait_for(assert_displayed, 'events_list_modal')
            assert_text(xpath('//*[@id="events_list_modal"]/div[1]/h3'), 'Alerts')
        
            assert_table_row_contains_text('event_tbl', 1, ('.*', 'File /test_file.txt IO error.*'), True)
            
            click_element(xpath('//*[@id="events_list_modal"]/div[3]/a[2]'))#Close btn
                
            self.mocked_id_client.simulate_id_client(OK, area={'get_available_media_storages': [],
                                                            'key_storage_status': 0})
            self.home_check([KEY_NAME], 'Stopped', 'Unknown') 
        finally:
            print 'FINALLY'
            self.destroy_console()



if __name__ == '__main__':
    if os.environ.get('SKIP_WEB_TESTS', 'false') == 'true':
        print('skipped')
        sys.exit(0)
    unittest.main()

