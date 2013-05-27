#!/usr/bin/python
import sys
import os
from subprocess import PIPE, Popen

VER_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), 'id_client/version.py'))

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print ('usage: %s <version>'%sys.argv[0])
        sys.exit(1)

    version = sys.argv[1]
    open(VER_FILE, 'w').write('#I am an auto-generated file! Dont touch me!!!\n\nVERSION="%s"'%version)
    os.system('git reset HEAD')
    os.system('git add %s'%VER_FILE)
    ret = os.system('git commit -m "updated version.py for %s"'%version)
    if ret:
        print ('ERROR! Can not commit changes!')
        sys.exit(1)

    ret = os.system('git tag -a %s'%version)
    if ret:
        print ('ERROR! Can not set new tag "%s"'%version)
        sys.exit(1)

    proc = Popen('git describe --always --tag'.split(), stdout=PIPE, stderr=PIPE)
    tag, cerr = proc.communicate()
    if proc.returncode:
        print ('ERROR! "git describe --always --tags" failed: %s'%cerr)
        sys.exit(1)

    print ('Version "%s" is bumped ;)'%version)
    sys.exit(0)

