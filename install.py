#####################################################
# For manual installation (for test purposes only!)
#####################################################
import sys
import os
import tempfile

if not sys.platform.startswith('linux'):
    print ('ERROR! This script for Linux only')
    sys.exit(1)

if os.geteuid() != 0:
    print("You need to have root privileges to run this script.\nPlease try again, this time using 'sudo'. Exiting.")
    sys.exit(1)

tmp_path = tempfile.mkdtemp('idp-install')

os.system('cp -r ./bin %s'%tmp_path)
os.system('cp -r ./id_client %s'%tmp_path)
os.system('cp -r ./nimbus_client %s'%tmp_path)
os.system('cp -r ./third-party %s'%tmp_path)

os.system('chown root:root %s -R'%tmp_path)
os.system('chmod 555 %s -R'%tmp_path)
os.system('chmod 4755 %s -R'%os.path.join(tmp_path, 'bin'))

if os.path.exists('/opt/idepositbox'):
    os.system('rm -rf /opt/idepositbox/*')
else:
    os.system('mkdir -p /opt/idepositbox')

os.system('chmod 555 /opt/idepositbox')
os.system('mv %s/* /opt/idepositbox'%tmp_path)
if not os.path.exists('/usr/bin/idepositbox'):
    os.system('ln -s /opt/idepositbox/bin/idepositbox_gui /usr/bin/idepositbox')

os.system('rm -rf %s'%tmp_path)

print ('iDepositBox client is installed to /opt/idepositbox')

print('-'*80)
print('Make sure that you have installed packages:')
print('   --> python-crypto (pycrypto)')
print('   --> PySide (if you want GUI)')
print('-'*80)

