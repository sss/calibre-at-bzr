#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os, socket, struct, subprocess
from distutils.spawn import find_executable

from PyQt4 import pyqtconfig

from setup import isosx, iswindows, islinux

OSX_SDK = '/Developer/SDKs/MacOSX10.4u.sdk'

os.environ['MACOSX_DEPLOYMENT_TARGET'] = '10.4'

NMAKE = RC = msvc = MT = win_inc = win_lib = win_ddk = None
if iswindows:
    from distutils import msvc9compiler
    msvc = msvc9compiler.MSVCCompiler()
    msvc.initialize()
    NMAKE = msvc.find_exe('nmake.exe')
    RC = msvc.find_exe('rc.exe')
    SDK = os.environ.get('WINSDK', r'C:\Program Files\Microsoft SDKs\Windows\v6.0A')
    DDK = os.environ.get('WINDDK', r'Q:\WinDDK\7600.16385.0')
    win_ddk = [DDK+'\\inc\\'+x for x in ('api',)]
    win_inc = os.environ['include'].split(';')
    win_lib = os.environ['lib'].split(';')
    for p in win_inc:
        if 'SDK' in p:
            MT = os.path.join(os.path.dirname(p), 'bin', 'mt.exe')
    MT = os.path.join(SDK, 'bin', 'mt.exe')

QMAKE = '/Volumes/sw/qt/bin/qmake' if isosx else 'qmake'
if find_executable('qmake-qt4'):
    QMAKE = find_executable('qmake-qt4')
elif find_executable('qmake'):
    QMAKE = find_executable('qmake')
QMAKE = os.environ.get('QMAKE', QMAKE)

PKGCONFIG = find_executable('pkg-config')
PKGCONFIG = os.environ.get('PKG_CONFIG', PKGCONFIG)

def run_pkgconfig(name, envvar, default, flag, prefix):
    ans = []
    if envvar:
        ans = os.environ.get(envvar, default)
        ans = [x.strip() for x in ans.split(os.pathsep)]
        ans = [x for x in ans if x and (prefix=='-l' or os.path.exists(x))]
    if not ans:
        try:
            raw = subprocess.Popen([PKGCONFIG, flag, name],
                stdout=subprocess.PIPE).stdout.read()
            ans = [x.strip() for x in raw.split(prefix)]
            ans = [x for x in ans if x and (prefix=='-l' or os.path.exists(x))]
        except:
            print 'Failed to run pkg-config:', PKGCONFIG, 'for:', name

    return ans

def pkgconfig_include_dirs(name, envvar, default):
    return run_pkgconfig(name, envvar, default, '--cflags-only-I', '-I')

def pkgconfig_lib_dirs(name, envvar, default):
    return run_pkgconfig(name, envvar, default,'--libs-only-L', '-L')

def pkgconfig_libs(name, envvar, default):
    return run_pkgconfig(name, envvar, default,'--libs-only-l', '-l')

def consolidate(envvar, default):
    val = os.environ.get(envvar, default)
    ans = [x.strip() for x in val.split(os.pathsep)]
    return [x for x in ans if x and os.path.exists(x)]

pyqt = pyqtconfig.Configuration()

qt_inc = pyqt.qt_inc_dir
qt_lib = pyqt.qt_lib_dir
ft_lib_dirs = []
ft_libs = []
jpg_libs = []
jpg_lib_dirs = []
poppler_objs = []
fc_inc = '/usr/include/fontconfig'
fc_lib = '/usr/lib'
podofo_inc = '/usr/include/podofo'
podofo_lib = '/usr/lib'

if iswindows:
    prefix  = r'C:\cygwin\home\kovid\sw'
    sw_inc_dir  = os.path.join(prefix, 'include')
    sw_lib_dir  = os.path.join(prefix, 'lib')
    fc_inc = os.path.join(sw_inc_dir, 'fontconfig')
    fc_lib = sw_lib_dir
    png_inc_dirs = [sw_inc_dir]
    png_lib_dirs = [sw_lib_dir]
    png_libs = ['png12']
    jpg_lib_dirs = [sw_lib_dir]
    jpg_libs = ['jpeg']
    ft_lib_dirs = [sw_lib_dir]
    ft_libs = ['freetype']
    poppler_inc_dirs = consolidate('POPPLER_INC_DIR',
            r'%s\poppler;%s'%(sw_inc_dir, sw_inc_dir))

    popplerqt4_inc_dirs = poppler_inc_dirs + [poppler_inc_dirs[1]+r'\qt4']
    poppler_lib_dirs = consolidate('POPPLER_LIB_DIR', sw_lib_dir)
    popplerqt4_lib_dirs = poppler_lib_dirs
    poppler_libs = ['poppler']
    popplerqt4_libs = poppler_libs + ['QtCore4', 'QtGui4']
    magick_inc_dirs = [os.path.join(prefix, 'build', 'ImageMagick-6.5.6')]
    magick_lib_dirs = [os.path.join(magick_inc_dirs[0], 'VisualMagick', 'lib')]
    magick_libs = ['CORE_RL_wand_', 'CORE_RL_magick_']
    podofo_inc = os.path.join(sw_inc_dir, 'podofo')
    podofo_lib = sw_lib_dir
elif isosx:
    fc_inc = '/sw/include/fontconfig'
    fc_lib = '/sw/lib'
    poppler_inc_dirs = consolidate('POPPLER_INC_DIR',
            '/sw/build/poppler-0.12.2/poppler:/sw/build/poppler-0.12.2')
    popplerqt4_inc_dirs = poppler_inc_dirs + [poppler_inc_dirs[0]+'/qt4']
    poppler_lib_dirs = consolidate('POPPLER_LIB_DIR',
            '/sw/lib')
    popplerqt4_lib_dirs = poppler_lib_dirs
    poppler_libs     = popplerqt4_libs = ['poppler']
    podofo_inc = '/sw/podofo'
    podofo_lib = '/sw/lib'
    magick_inc_dirs = consolidate('MAGICK_INC',
        '/sw/include/ImageMagick')
    magick_lib_dirs = consolidate('MAGICK_LIB',
        '/sw/lib')
    magick_libs = ['MagickWand', 'MagickCore']
    png_inc_dirs = consolidate('PNG_INC_DIR', '/sw/include')
    png_lib_dirs = consolidate('PNG_LIB_DIR', '/sw/lib')
    png_libs = ['png12']
else:
    # Include directories
    poppler_inc_dirs = pkgconfig_include_dirs('poppler',
        'POPPLER_INC_DIR', '/usr/include/poppler')
    popplerqt4_inc_dirs = pkgconfig_include_dirs('poppler-qt4', '', '')
    if not popplerqt4_inc_dirs:
        popplerqt4_inc_dirs = poppler_inc_dirs + [poppler_inc_dirs[0]+'/qt4']
    png_inc_dirs = pkgconfig_include_dirs('libpng', 'PNG_INC_DIR',
        '/usr/include')
    magick_inc_dirs = pkgconfig_include_dirs('MagickWand', 'MAGICK_INC', '/usr/include/ImageMagick')

    # Library directories
    poppler_lib_dirs = popplerqt4_lib_dirs = pkgconfig_lib_dirs('poppler', 'POPPLER_LIB_DIR',
        '/usr/lib')
    png_lib_dirs = pkgconfig_lib_dirs('libpng', 'PNG_LIB_DIR', '/usr/lib')
    magick_lib_dirs = pkgconfig_lib_dirs('MagickWand', 'MAGICK_LIB', '/usr/lib')

    # Libraries
    poppler_libs = pkgconfig_libs('poppler', '', '')
    if not poppler_libs:
        poppler_libs = ['poppler']
    popplerqt4_libs = pkgconfig_libs('poppler-qt4', '', '')
    if not popplerqt4_libs:
        popplerqt4_libs = ['poppler-qt4', 'poppler']
    magick_libs = pkgconfig_libs('MagickWand', '', '')
    if not magick_libs:
        magick_libs = ['MagickWand', 'MagickCore']
    png_libs = ['png']


fc_inc = os.environ.get('FC_INC_DIR', fc_inc)
fc_lib = os.environ.get('FC_LIB_DIR', fc_lib)
fc_error = None if os.path.exists(os.path.join(fc_inc, 'fontconfig.h')) else \
    ('fontconfig header files not found on your system. '
            'Try setting the FC_INC_DIR and FC_LIB_DIR environment '
            'variables.')


poppler_error = None
if not poppler_inc_dirs or not os.path.exists(
        os.path.join(poppler_inc_dirs[0], 'OutputDev.h')):
    poppler_error = \
    ('Poppler not found on your system. Various PDF related',
    ' functionality will not work. Use the POPPLER_INC_DIR and',
    ' POPPLER_LIB_DIR environment variables.')

popplerqt4_error = None
if not popplerqt4_inc_dirs or not os.path.exists(
        os.path.join(popplerqt4_inc_dirs[-1], 'poppler-qt4.h')):
    popplerqt4_error = \
            ('Poppler Qt4 bindings not found on your system.')

magick_error = None
if not magick_inc_dirs or not os.path.exists(os.path.join(magick_inc_dirs[0],
    'wand')):
    magick_error = ('ImageMagick not found on your system. '
            'Try setting the environment variables MAGICK_INC '
            'and MAGICK_LIB to help calibre locate the inclue and libbrary '
            'files.')

podofo_lib = os.environ.get('PODOFO_LIB_DIR', podofo_lib)
podofo_inc = os.environ.get('PODOFO_INC_DIR', podofo_inc)
podofo_error = None if os.path.exists(os.path.join(podofo_inc, 'podofo.h')) else \
        ('PoDoFo not found on your system. Various PDF related',
    ' functionality will not work. Use the PODOFO_INC_DIR and',
    ' PODOFO_LIB_DIR environment variables.')

def get_ip_address(ifname):
    import fcntl
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    return socket.inet_ntoa(fcntl.ioctl(
        s.fileno(),
        0x8915,  # SIOCGIFADDR
        struct.pack('256s', ifname[:15])
    )[20:24])

try:
    if islinux:
        HOST=get_ip_address('eth0')
    else:
        HOST='192.168.1.2'
except:
    try:
        HOST=get_ip_address('wlan0')
    except:
        HOST='192.168.1.2'

PROJECT=os.path.basename(os.path.abspath('.'))


