#!/usr/bin/python
import sys, os, shutil, time, tempfile, socket, fcntl, struct, cStringIO, pycurl, re
sys.path.append('src')
import subprocess
from subprocess import check_call as _check_call
from functools import partial
#from pyvix.vix import Host, VIX_SERVICEPROVIDER_VMWARE_WORKSTATION
def get_ip_address(ifname):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    return socket.inet_ntoa(fcntl.ioctl(
        s.fileno(),
        0x8915,  # SIOCGIFADDR
        struct.pack('256s', ifname[:15])
    )[20:24])
    
HOST=get_ip_address('eth0')
PROJECT=os.path.basename(os.getcwd())

from calibre import __version__, __appname__

PREFIX = "/var/www/calibre.kovidgoyal.net"
DOWNLOADS = PREFIX+"/htdocs/downloads"
DOCS = PREFIX+"/htdocs/apidocs"
USER_MANUAL = PREFIX+'/htdocs/user_manual'
HTML2LRF = "src/calibre/ebooks/lrf/html/demo"
TXT2LRF  = "src/calibre/ebooks/lrf/txt/demo"
MOBILEREAD = 'ftp://dev.mobileread.com/calibre/'
BUILD_SCRIPT ='''\
#!/bin/bash
cd ~/build && \
rsync -avz --exclude src/calibre/plugins --exclude docs --exclude .bzr --exclude .build --exclude build --exclude dist --exclude "*.pyc" --exclude "*.pyo" rsync://%(host)s/work/%(project)s . && \
cd %(project)s && \
mkdir -p build dist src/calibre/plugins && \
%%s && \
rm -rf build/* dist/* && \
%%s %%s
'''%dict(host=HOST, project=PROJECT) 
check_call = partial(_check_call, shell=True)
#h = Host(hostType=VIX_SERVICEPROVIDER_VMWARE_WORKSTATION)


def tag_release():
    print 'Tagging release'
    check_call('bzr tag '+__version__)
    check_call('bzr commit --unchanged -m "IGN:Tag release"')
            
def installer_name(ext):
    if ext in ('exe', 'dmg'):
        return 'dist/%s-%s.%s'%(__appname__, __version__, ext)
    return 'dist/%s-%s-i686.%s'%(__appname__, __version__, ext)

def start_vm(vm, ssh_host, build_script, sleep=75):
    vmware = ('vmware', '-q', '-x', '-n', vm)
    subprocess.Popen(vmware)
    t = tempfile.NamedTemporaryFile(suffix='.sh')
    t.write(build_script)
    t.flush()
    print 'Waiting for VM to startup'
    while subprocess.call('ping -q -c1 '+ssh_host, shell=True, stdout=open('/dev/null', 'w')) != 0:
        time.sleep(5)
    time.sleep(20)
    print 'Trying to SSH into VM'
    subprocess.check_call(('scp', t.name, ssh_host+':build-'+PROJECT))
    subprocess.check_call('ssh -t %s bash build-%s'%(ssh_host, PROJECT), shell=True)

def build_windows():
    installer = installer_name('exe')
    vm = '/vmware/Windows XP/Windows XP Professional.vmx'
    start_vm(vm, 'windows', BUILD_SCRIPT%('python setup.py develop', 'python','windows_installer.py'))
    subprocess.check_call(('scp', 'windows:build/%s/dist/*.exe'%PROJECT, 'dist'))
    if not os.path.exists(installer):
        raise Exception('Failed to build installer '+installer)
    subprocess.Popen(('ssh', 'windows', 'shutdown', '-s', '-t', '0'))
    return os.path.basename(installer)

def build_osx():
    installer = installer_name('dmg')
    vm = '/vmware/Mac OSX/Mac OSX.vmx'
    python = '/Library/Frameworks/Python.framework/Versions/Current/bin/python' 
    start_vm(vm, 'osx', BUILD_SCRIPT%('sudo %s setup.py develop'%python, python, 'osx_installer.py'))
    subprocess.check_call(('scp', 'osx:build/%s/dist/*.dmg'%PROJECT, 'dist'))
    if not os.path.exists(installer):
        raise Exception('Failed to build installer '+installer)
    subprocess.Popen(('ssh', 'osx', 'sudo', '/sbin/shutdown', '-h', 'now'))
    return os.path.basename(installer)
  

def build_linux():
    installer = installer_name('tar.bz2')
    vm = '/vmware/linux/libprs500-gentoo.vmx'
    start_vm(vm, 'linux', BUILD_SCRIPT%('sudo python setup.py develop', 'python','linux_installer.py'))
    subprocess.check_call(('scp', 'linux:/tmp/%s'%os.path.basename(installer), 'dist'))
    if not os.path.exists(installer):
        raise Exception('Failed to build installer '+installer)
    subprocess.Popen(('ssh', 'linux', 'sudo', '/sbin/poweroff'))
    return os.path.basename(installer)

def build_installers():
    return build_linux(), build_windows(), build_osx()

def upload_demo():
    check_call('''html2lrf --title='Demonstration of html2lrf' --author='Kovid Goyal' '''
               '''--header --output=/tmp/html2lrf.lrf %s/demo.html '''
               '''--serif-family "/usr/share/fonts/corefonts, Times New Roman" '''
               '''--mono-family  "/usr/share/fonts/corefonts, Andale Mono" '''
               ''''''%(HTML2LRF,))
    check_call('cd src/calibre/ebooks/lrf/html/demo/ && zip -j /tmp/html-demo.zip * /tmp/html2lrf.lrf')
    check_call('''scp /tmp/html-demo.zip divok:%s/'''%(DOWNLOADS,))
    check_call('''txt2lrf -t 'Demonstration of txt2lrf' -a 'Kovid Goyal' '''
               '''--header -o /tmp/txt2lrf.lrf %s/demo.txt'''%(TXT2LRF,) )
    check_call('cd src/calibre/ebooks/lrf/txt/demo/ && zip -j /tmp/txt-demo.zip * /tmp/txt2lrf.lrf')
    check_call('''scp /tmp/txt-demo.zip divok:%s/'''%(DOWNLOADS,))

def curl_list_dir(url=MOBILEREAD, listonly=1):
    c = pycurl.Curl()
    c.setopt(pycurl.URL, url)
    c.setopt(c.FTP_USE_EPSV, 1)
    c.setopt(c.NETRC, c.NETRC_REQUIRED)
    c.setopt(c.FTPLISTONLY, listonly)
    c.setopt(c.FTP_CREATE_MISSING_DIRS, 1)
    b = cStringIO.StringIO()
    c.setopt(c.WRITEFUNCTION, b.write)
    c.perform()
    c.close()
    return b.getvalue().split() if listonly else b.getvalue().splitlines()

def curl_delete_file(path, url=MOBILEREAD):
    c = pycurl.Curl()
    c.setopt(pycurl.URL, url)
    c.setopt(c.FTP_USE_EPSV, 1)
    c.setopt(c.NETRC, c.NETRC_REQUIRED)
    print 'Deleting file %s on %s'%(path, url)
    c.setopt(c.QUOTE, ['dele '+ path])
    c.perform()
    c.close()
    

def curl_upload_file(stream, url):
    c = pycurl.Curl()
    c.setopt(pycurl.URL, url)
    c.setopt(pycurl.UPLOAD, 1)
    c.setopt(c.NETRC, c.NETRC_REQUIRED)
    c.setopt(pycurl.READFUNCTION, stream.read)
    stream.seek(0, 2)
    c.setopt(pycurl.INFILESIZE_LARGE, stream.tell())
    stream.seek(0)
    c.setopt(c.NOPROGRESS, 0)
    c.setopt(c.FTP_CREATE_MISSING_DIRS, 1)
    print 'Uploading file %s to url %s' % (getattr(stream, 'name', ''), url)
    try:
        c.perform()
        c.close()
    except:
        pass
    files = curl_list_dir(listonly=0)
    for line in files:
        line = line.split()
        if url.endswith(line[-1]):
            size = long(line[4])
            stream.seek(0,2)
            if size != stream.tell():
                raise RuntimeError('curl failed to upload %s correctly'%getattr(stream, 'name', ''))
                             
        
    
def upload_installer(name):
    bname = os.path.basename(name)
    pat = re.compile(bname.replace(__version__, r'\d+\.\d+\.\d+'))
    for f in curl_list_dir():
        if pat.search(f):
            curl_delete_file('/calibre/'+f)
    curl_upload_file(open(name, 'rb'), MOBILEREAD+os.path.basename(name))

def upload_installers():
    for i in ('dmg', 'exe', 'tar.bz2'):
        upload_installer(installer_name(i))
        
    check_call('''ssh divok echo %s \\> %s/latest_version'''%(__version__, DOWNLOADS))
        
        
def upload_docs():
    check_call('''epydoc --config epydoc.conf''')
    check_call('''scp -r docs/html divok:%s/'''%(DOCS,))
    check_call('''epydoc -v --config epydoc-pdf.conf''')
    check_call('''scp docs/pdf/api.pdf divok:%s/'''%(DOCS,))

def upload_user_manual():
    cwd = os.getcwdu()
    os.chdir('src/calibre/manual')
    try:
        check_call('make clean html')
        check_call('ssh divok rm -rf %s/\\*'%USER_MANUAL)
        check_call('scp -r .build/html/* divok:%s'%USER_MANUAL)
    finally:
        os.chdir(cwd)
        
def build_src_tarball():
    check_call('bzr export dist/calibre-%s.tar.bz2'%__version__)
    
def upload_src_tarball():
    check_call('ssh divok rm -f %s/calibre-\*.tar.bz2'%DOWNLOADS)
    check_call('scp dist/calibre-*.tar.bz2 divok:%s/'%DOWNLOADS)

def stage_one():
    shutil.rmtree('build')
    os.mkdir('build')
    shutil.rmtree('docs')
    os.mkdir('docs')
    check_call("sudo python setup.py develop", shell=True)
    check_call('sudo rm src/%s/gui2/images_rc.pyc'%__appname__, shell=True)
    check_call('make', shell=True)
    tag_release()
    upload_demo()
    
def stage_two():
    subprocess.check_call('rm -rf dist/*', shell=True)
    build_installers()
    build_src_tarball()    

def stage_three():
    print 'Uploading installers...'
    upload_installers()
    print 'Uploading to PyPI'
    upload_src_tarball()
    upload_docs()
    upload_user_manual()
    check_call('python setup.py register bdist_egg --exclude-source-files upload')
    check_call('''rm -rf dist/* build/*''')

def main(args=sys.argv):
    print 'Starting stage one...'
    stage_one()
    print 'Starting stage two...'
    stage_two()
    print 'Starting stage three...'
    stage_three()
    print 'Finished'
    return 0    
        
    
if __name__ == '__main__':
    sys.exit(main())
