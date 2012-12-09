import os
import sys

def process_form_dir(path):
    if not os.path.exists(path):
        raise Exception('Directory %s does not exists!'%path)

    for f_name in os.listdir(path):
        f_path = os.path.join(path, f_name)
        if not os.path.isfile(f_path) or not f_name.endswith('.ui'):
            continue

        dest = os.path.join(path, f_name[:-2]+'py')
        print '-> Generating %s ...'%(dest,)
        ret = os.system('pyside-uic %s > %s'%(f_path, dest))
        if ret:
            raise Exception('Cant generate form from file: %s'%f_path)

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print 'usage: %s <forms directory>'%sys.argv[0]
        sys.exit(1)

    path = sys.argv[1]

    try:
        process_form_dir(path)
    except Exception, err:
        print 'ERROR: %s'%err
        sys.exit(1)

    print 'OK!'
    sys.exit(0)
