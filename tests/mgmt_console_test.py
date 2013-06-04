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
from util_mocked_ca_service import MockedCAServer
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
        assert_text_contains(xpath('//*[@id="wind"]/div[3]/p'), '2013 iDepositBox software')
        assert_text(xpath('//*[@id="home"]/a'), 'Home')
        assert_text(xpath('//*[@id="settings"]/a'), 'Settings')
        assert_text(xpath('//*[@id="key_mgmt"]/a'), 'Key management')
        assert_text(xpath('//*[@id="about"]/a'), 'About')

    def check_help(self):
        click_element(get_element(css_class="help"))
        wait_for(assert_element, css_class="popover")
        click_element('wind')
        fails(assert_element, css_class="popover")

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
            #assert_css_property('pr_tl', 'width', '100%')
            is_up_tr = None
            for i, (f_name, f_size, is_upload) in enumerate(inpr_files):
                tr = i+2
                icon = 'icon-arrow-%s'% ('up' if is_upload else 'down')
                assert_attribute(xpath('//*[@id="inpr_tbl"]/tbody/tr[%i]/td[1]/span[1]'%tr), 'class', icon)
                assert_text_contains(xpath('//*[@id="inpr_tbl"]/tbody/tr[%i]/td[1]'%tr), f_name)
                assert_text(xpath('//*[@id="inpr_tbl"]/tbody/tr[%i]/td[2]'%tr), '%s b'%f_size)
                if is_upload:
                    assert_text(xpath('//*[@id="inpr_tbl"]/tbody/tr[%i]/td[3]'%tr), '40%')
                    assert_attribute(xpath('//*[@id="inpr_tbl"]/tbody/tr[%i]/td[1]/span[2]'%tr), 'class', 'icon-globe')
                else:
                    assert_text(xpath('//*[@id="inpr_tbl"]/tbody/tr[%i]/td[3]'%tr), '0%')
                if is_up_tr is None:
                    is_up_tr = is_upload
                elif is_up_tr != is_upload:
                    is_up_tr = 'both'

            if is_up_tr==True:
                icon = 'icon-arrow-up'
                perc = '40%'
            elif is_up_tr==False:
                icon = 'icon-arrow-down'
                perc = '0%'
            else:
                icon = 'icon-refresh'
                perc = '20%'
            assert_text(xpath('//*[@id="d_pr"]/span'), perc)
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

    def home_page_test(self):
        self.home_check([], 'Stopped', 'Unknown')
        self.check_help()

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
        time.sleep(1)
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

    def settings_page_test(self):
        cur_config = self.mocked_id_client.get_config()

        go_to('http://127.0.0.1:9999/settings')
        wait_for(assert_attribute, 'parDownCnt','value', str(cur_config['parallel_get_count']))
        assert_attribute('parUpCnt', 'value', str(cur_config['parallel_get_count']))
        assert_attribute(xpath("//*[@id='logLevel']/option[@selected='selected']"), 'value', cur_config['log_level'])
        assert_attribute(xpath("//*[@id='mountType']/option[@selected='selected']"), 'value', cur_config['mount_type'])
        assert_attribute('webdavHost', 'value', str(cur_config['webdav_bind_host']))
        assert_attribute('webdavPort', 'value', str(cur_config['webdav_bind_port']))
        assert_attribute('apply_btn', 'disabled', 'true')

        write_textfield('parUpCnt', '999')
        click_element('apply_btn')
        wait_for(assert_text_contains, 'err_msg', 'Invalid simultaneous uploads count number! Expecting numeric value in range')
        new_config = self.mocked_id_client.get_config()
        self.assertEqual(new_config, cur_config)

        write_textfield('parUpCnt', '10')
        write_textfield('parDownCnt', '5')
        write_textfield('webdavHost', 'my_hostname')
        write_textfield('webdavPort', '9876')
        set_dropdown_value('logLevel', value='ERROR')
        click_element('apply_btn')
        wait_for(assert_text_contains, 'err_msg', 'Settings are applied!')
        assert_attribute('apply_btn', 'disabled', 'true')
        new_config = self.mocked_id_client.get_config()
        self.assertEqual(new_config['parallel_get_count'], 5)
        self.assertEqual(new_config['parallel_put_count'], 10)
        self.assertEqual(new_config['webdav_bind_host'], 'my_hostname')
        self.assertEqual(new_config['webdav_bind_port'], '9876')
        self.assertEqual(new_config['log_level'], 'ERROR')
        self.assertEqual(new_config['mount_type'], cur_config['mount_type'])

        click_element(xpath('//*[@id="err_msg"]/button'))
        set_dropdown_value('mountType', value='local')
        click_element('apply_btn')
        wait_for(assert_text_contains, 'err_msg', 'Settings are applied!')
        new_new_config = self.mocked_id_client.get_config()
        self.assertEqual(new_new_config['mount_type'], 'local')
        new_new_config['mount_type'] = new_config['mount_type']
        self.assertEqual(new_config, new_new_config)

        set_dropdown_value('mountType', value=new_config['mount_type'])
        click_element('apply_btn')
        self.check_help()

    def check_key_management_basic(self, act_ks=None, gen_ks=None):
        assert_css_property('pwdModal', 'display', 'none')
        assert_css_property('succGenCertModal', 'display', 'none')
        assert_css_property('blockDevAskModal', 'display', 'none')
        assert_css_property('spinModal', 'display', 'none')
        assert_element(id='info_form', css_class='hidden')
        assert_element(id='gen_form', css_class='hidden')
        if not act_ks:
            wait_for(get_element_by_xpath, '//*[@id="ks_info_select_alert"]/div/span')
            assert_text_contains(xpath('//*[@id="ks_info_select_alert"]/div/span'), 'No key chain found!')
            assert_element(id='open_btn', css_class='disabled')
        else:
            wait_for(get_element_by_xpath, '//*[@id="ksPath"]/option[1]')
            assert_text(xpath('//*[@id="ksPath"]/option[1]'), act_ks)

        if not gen_ks:
            assert_text_contains(xpath('//*[@id="ks_gen_select_alert"]/div/span'), 'No suitable device found!')
            assert_element(id='gen_btn', css_class='disabled')
        else:
            assert_text(xpath('//*[@id="ksNewPath"]/option[1]'), gen_ks)


    def key_management_page_test(self):
        self.mocked_id_client.simulate_id_client(OK, area={'get_available_media_storages': []}, flush=True)
        go_to('http://127.0.0.1:9999/key_mgmt')
        self.check_key_management_basic()
        self.check_help()

        os.system('rm -rf /tmp/test.keystorage')
        media = MediaStorage(KEY_NAME, '/tmp/test.keystorage')
        self.mocked_id_client.simulate_id_client(OK, area={'get_available_media_storages': [media]})

        go_to('http://127.0.0.1:9999/key_mgmt')
        self.check_key_management_basic(gen_ks=KEY_NAME)
        click_element('gen_btn')

        ca_server = MockedCAServer(9998)
        ca_server.start()
        time.sleep(1)
        try:
            assert_element(id='generate_btn', css_class='disabled')
            write_textfield('act_key', 'fake')
            write_textfield('password', '123')
            write_textfield('re_password', '12345') 
            click_element('generate_btn')
            wait_for(get_element_by_xpath, '//*[@id="gen_alert_field"]/div/span')
            assert_text_contains(xpath('//*[@id="gen_alert_field"]/div/span'), 'Pin-codes are not equal!')
            click_element(xpath('//*[@id="gen_alert_field"]/div/button'))

            write_textfield('re_password', '123') 
            click_element('generate_btn')
            wait_for(get_element_by_xpath, '//*[@id="gen_alert_field"]/div/span')
            assert_text_contains(xpath('//*[@id="gen_alert_field"]/div/span'), 'Password is too short')
            click_element(xpath('//*[@id="gen_alert_field"]/div/button'))

            write_textfield('password', 'qwerty123')
            write_textfield('re_password', 'qwerty123') 
            click_element('generate_btn')
            wait_for(get_element_by_xpath, '//*[@id="gen_alert_field"]/div/span')
            assert_text_contains(xpath('//*[@id="gen_alert_field"]/div/span'), 'Activation key "fake" does not found!')
            click_element(xpath('//*[@id="gen_alert_field"]/div/button'))

            write_textfield('act_key', 'DGDSFGASGFGFDSAA')
            click_element('generate_btn')
            wait_for(get_element_by_xpath, '//*[@id="gen_alert_field"]/div/span')
            assert_text_contains(xpath('//*[@id="gen_alert_field"]/div/span'), 'Details: Can not update key chain!\nNo certificate matches private key')
            click_element(xpath('//*[@id="gen_alert_field"]/div/button'))

            os.system('cp ./tests/cert/test_pri_only.ks /tmp/test.keystorage')
            execute_script("$.gen_ks_info.ks_path = 'blockdev:/tmp/rrrr';")
            click_element('generate_btn')
            wait_for(assert_displayed, 'blockDevAskModal')
            click_element(xpath('//*[@id="blockDevAskModal"]/div/a[2]'))
            wait_for(assert_css_property, 'blockDevAskModal', 'display', 'none')

            click_element('generate_btn')
            wait_for(assert_displayed, 'blockDevAskModal')
            execute_script("$.gen_ks_info.ks_path = 'file:/tmp/test.keystorage';")
            click_element(xpath('//*[@id="blockDevAskModal"]/div/a[1]'))

            wait_for(assert_displayed, 'succGenCertModal')
            click_element(xpath('//*[@id="succGenCertModal"]/div/a'))
            self.check_key_management_basic(act_ks=KEY_NAME)
        finally:
            ca_server.stop()

        click_element('open_btn')
        wait_for(assert_displayed, 'pwdModal')
        write_textfield('pwdEdit', 'blablalbla')
        click_element(xpath('//*[@id="pwdModal"]/div/a'))
        wait_for(get_element_by_xpath, '//*[@id="alert_field"]/div/span')
        assert_text_contains(xpath('//*[@id="alert_field"]/div/span'), 'Can not open key chain! Maybe pin-code is invalid!')

        click_element('open_btn')
        wait_for(assert_displayed, 'pwdModal')
        write_textfield('pwdEdit', KS_PASSWORD)
        click_element(xpath('//*[@id="pwdModal"]/div/a'))
        wait_for(assert_text, xpath('//*[@id="info_form"]/div[1]/h4'), 'Certificate information')
        assert_text_contains('cert_txt', 'O=iDepositBox software, OU=clients.idepositbox.com')
        click_element('back_btn')
        self.check_key_management_basic(act_ks=KEY_NAME)

    def about_test(self):
        go_to('http://127.0.0.1:9999/about')
        assert_text_contains('about_info', 'Web site:')
        assert_text_contains('about_info', 'Twitter:')
        assert_text_contains('about_info', 'Version %s'%self.mocked_id_client.get_version())

    def test_main(self):
        self.init_console()
        try:
            self.base_console_test()

            self.home_page_test()
            self.settings_page_test()
            self.key_management_page_test()
            self.about_test()
        finally:
            print 'FINALLY'
            self.destroy_console()



if __name__ == '__main__':
    if os.environ.get('SKIP_WEB_TESTS', 'false') == 'true':
        print('skipped')
        sys.exit(0)
    unittest.main()

