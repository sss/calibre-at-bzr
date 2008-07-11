__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
import shutil
''' Post installation script for linux '''
import sys, os, re

from subprocess import check_call, call
from calibre import __version__, __appname__

from calibre.devices import devices

DEVICES = devices()

DESTDIR = ''
if os.environ.has_key('DESTDIR'):
    DESTDIR = os.environ['DESTDIR']

entry_points = {
        'console_scripts': [ \
                             'prs500    = calibre.devices.prs500.cli.main:main', 
                             'lrf-meta  = calibre.ebooks.lrf.meta:main', 
                             'rtf-meta  = calibre.ebooks.metadata.rtf:main', 
                             'pdf-meta  = calibre.ebooks.metadata.pdf:main', 
                             'lit-meta  = calibre.ebooks.metadata.lit:main',
                             'opf-meta  = calibre.ebooks.metadata.opf:main',
                             'epub-meta = calibre.ebooks.metadata.epub:main',
                             'txt2lrf   = calibre.ebooks.lrf.txt.convert_from:main', 
                             'html2lrf  = calibre.ebooks.lrf.html.convert_from:main',
                             'markdown-calibre  = calibre.ebooks.markdown.markdown:main',
                             'lit2lrf   = calibre.ebooks.lrf.lit.convert_from:main',
                             'epub2lrf  = calibre.ebooks.lrf.epub.convert_from:main',
                             'rtf2lrf   = calibre.ebooks.lrf.rtf.convert_from:main',
                             'web2disk  = calibre.web.fetch.simple:main',
                             'feeds2disk = calibre.web.feeds.main:main',
                             'feeds2lrf = calibre.ebooks.lrf.feeds.convert_from:main',
                             'web2lrf   = calibre.ebooks.lrf.web.convert_from:main',
                             'pdf2lrf   = calibre.ebooks.lrf.pdf.convert_from:main',
                             'mobi2lrf  = calibre.ebooks.lrf.mobi.convert_from:main',
                             'fb22lrf   = calibre.ebooks.lrf.fb2.convert_from:main',
                             'fb2-meta  = calibre.ebooks.metadata.fb2:main',
                             'any2lrf   = calibre.ebooks.lrf.any.convert_from:main',
                             'lrf2lrs   = calibre.ebooks.lrf.lrfparser:main',
                             'lrs2lrf   = calibre.ebooks.lrf.lrs.convert_from:main',
                             'pdfreflow = calibre.ebooks.lrf.pdf.reflow:main',
                             'isbndb    = calibre.ebooks.metadata.isbndb:main',
                             'librarything = calibre.ebooks.metadata.library_thing:main',
                             'mobi2oeb  = calibre.ebooks.mobi.reader:main',
                             'lrf2html  = calibre.ebooks.lrf.html.convert_to:main',
                             'calibre-debug      = calibre.debug:main',
                             'calibredb          = calibre.library.cli:main',
                             'calibre-fontconfig = calibre.utils.fontconfig:main',
                             'calibre-parallel   = calibre.parallel:main',
                           ], 
        'gui_scripts'    : [ 
                            __appname__+' = calibre.gui2.main:main',
                            'lrfviewer = calibre.gui2.lrf_renderer.main:main',
                            ],
      }


def options(option_parser):
    parser = option_parser() 
    options = parser.option_list
    for group in parser.option_groups:
        options += group.option_list
    opts = []
    for opt in options:
        opts.extend(opt._short_opts)
        opts.extend(opt._long_opts)
    return opts

def opts_and_words(name, op, words):
    opts  = '|'.join(options(op))
    words = '|'.join([w.replace("'", "\\'") for w in words]) 
    return '_'+name+'()'+\
'''
{
    local cur opts
    local IFS=$'|\\t'
    COMPREPLY=()
    cur="${COMP_WORDS[COMP_CWORD]}"
    opts="%s"
    words="%s"
    
    case "${cur}" in
      -* )
         COMPREPLY=( $(compgen -W "${opts}" -- ${cur}) )
         COMPREPLY=( $( echo ${COMPREPLY[@]} | sed 's/ /\\\\ /g' | tr '\\n' '\\t' ) )
         return 0
         ;;      
      *  )
         COMPREPLY=( $(compgen -W "${words}" -- ${cur}) )
         COMPREPLY=( $( echo ${COMPREPLY[@]} | sed 's/ /\\\\ /g' | tr '\\n' '\\t' ) )
         return 0
         ;;
    esac

}
complete -F _'''%(opts, words) + name + ' ' + name +"\n\n"


def opts_and_exts(name, op, exts):
    opts = ' '.join(options(op))
    exts.extend([i.upper() for i in exts])
    exts='|'.join(exts)
    return '_'+name+'()'+\
'''
{
    local cur prev opts
    COMPREPLY=()
    cur="${COMP_WORDS[COMP_CWORD]}"
    prev="${COMP_WORDS[COMP_CWORD-1]}"
    opts="%s"
    pics="@(jpg|jpeg|png|gif|bmp|JPG|JPEG|PNG|GIF|BMP)"

    case "${prev}" in
      --cover )
           _filedir "${pics}"
           return 0
           ;;
    esac

    case "${cur}" in
      --cover )
         _filedir "${pics}"
         return 0
         ;;
      -* )
         COMPREPLY=( $(compgen -W "${opts}" -- ${cur}) )
         return 0
         ;;
      *  )
        _filedir '@(%s)'
        return 0
        ;;
    esac

}
complete -o filenames -F _'''%(opts,exts) + name + ' ' + name +"\n\n"

use_destdir = False

def open_file(path, mode='wb'):
    if use_destdir:
        if os.path.isabs(path):
            path = path[1:]
        path = os.path.join(DESTDIR, path)
    if not os.path.exists(os.path.dirname(path)):
        os.makedirs(os.path.dirname(path))
    return open(path, mode)

def setup_completion(fatal_errors):
    try:
        print 'Setting up bash completion...',
        sys.stdout.flush()
        from calibre.ebooks.lrf.html.convert_from import option_parser as htmlop
        from calibre.ebooks.lrf.txt.convert_from import option_parser as txtop
        from calibre.ebooks.lrf.meta import option_parser as metaop
        from calibre.ebooks.lrf.lrfparser import option_parser as lrf2lrsop
        from calibre.gui2.lrf_renderer.main import option_parser as lrfviewerop
        from calibre.ebooks.lrf.pdf.reflow import option_parser as pdfhtmlop
        from calibre.ebooks.mobi.reader import option_parser as mobioeb
        from calibre.web.feeds.main import option_parser as feeds2disk
        from calibre.web.feeds.recipes import titles as feed_titles
        from calibre.ebooks.lrf.feeds.convert_from import option_parser as feeds2lrf
        
        f = open_file('/etc/bash_completion.d/libprs500')
        f.close()
        os.remove(f.name)
        f = open_file('/etc/bash_completion.d/calibre')
        
        f.write('# calibre Bash Shell Completion\n')
        f.write(opts_and_exts('html2lrf', htmlop, 
                              ['htm', 'html', 'xhtml', 'xhtm', 'rar', 'zip', 'php']))
        f.write(opts_and_exts('txt2lrf', txtop, ['txt']))
        f.write(opts_and_exts('lit2lrf', htmlop, ['lit']))
        f.write(opts_and_exts('epub2lrf', htmlop, ['epub']))
        f.write(opts_and_exts('rtf2lrf', htmlop, ['rtf']))
        f.write(opts_and_exts('mobi2lrf', htmlop, ['mobi', 'prc']))
        f.write(opts_and_exts('fb22lrf', htmlop, ['fb2']))
        f.write(opts_and_exts('pdf2lrf', htmlop, ['pdf']))
        f.write(opts_and_exts('any2lrf', htmlop, 
            ['epub', 'htm', 'html', 'xhtml', 'xhtm', 'rar', 'zip', 
             'txt', 'lit', 'rtf', 'pdf', 'prc', 'mobi', 'fb2']))
        f.write(opts_and_exts('lrf2lrs', lrf2lrsop, ['lrf']))
        f.write(opts_and_exts('lrf-meta', metaop, ['lrf']))
        f.write(opts_and_exts('rtf-meta', metaop, ['rtf']))
        f.write(opts_and_exts('pdf-meta', metaop, ['pdf']))
        f.write(opts_and_exts('lit-meta', metaop, ['lit']))
        f.write(opts_and_exts('opf-meta', metaop, ['opf']))
        f.write(opts_and_exts('epub-meta', metaop, ['epub']))
        f.write(opts_and_exts('lrfviewer', lrfviewerop, ['lrf']))
        f.write(opts_and_exts('pdfrelow', pdfhtmlop, ['pdf']))
        f.write(opts_and_exts('mobi2oeb', mobioeb, ['mobi', 'prc']))
        f.write(opts_and_words('feeds2disk', feeds2disk, feed_titles))
        f.write(opts_and_words('feeds2lrf', feeds2lrf, feed_titles))
        f.write('''
_prs500_ls()
{
  local pattern search listing prefix
  pattern="$1"
  search="$1"
  if [[ -n "{$pattern}" ]]; then
    if [[ "${pattern:(-1)}" == "/" ]]; then
      pattern=""
    else
      pattern="$(basename ${pattern} 2> /dev/null)"
      search="$(dirname ${search} 2> /dev/null)"
    fi
  fi

  if [[  "x${search}" == "x" || "x${search}" == "x." ]]; then
    search="/"
  fi

  listing="$(prs500 ls ${search} 2>/dev/null)"

  prefix="${search}"
  if [[ "x${prefix:(-1)}" != "x/" ]]; then
    prefix="${prefix}/"
  fi

  echo $(compgen -P "${prefix}" -W "${listing}" "${pattern}") 
}

_prs500()
{
  local cur prev 
  cur="${COMP_WORDS[COMP_CWORD]}"
  prev="${COMP_WORDS[COMP_CWORD-1]}"
  COMPREPLY=()
  case "${prev}" in
    ls|rm|mkdir|touch|cat )        
        COMPREPLY=( $(_prs500_ls "${cur}") )
        return 0
        ;;
    cp )
        if [[ ${cur} == prs500:* ]]; then
          COMPREPLY=( $(_prs500_ls "${cur:7}") )
          return 0
        else
          _filedir
          return 0
        fi
        ;;
    prs500 )
        COMPREPLY=( $(compgen -W "cp ls rm mkdir touch cat info books df" "${cur}") )
        return 0
        ;;
    * )
        if [[ ${cur} == prs500:* ]]; then
          COMPREPLY=( $(_prs500_ls "${cur:7}") )
          return 0
        else
          if [[ ${prev} == prs500:* ]]; then
            _filedir
            return 0
          else
            COMPREPLY=( $(compgen -W "prs500:" "${cur}") )
            return 0
          fi
          return 0
        fi
       ;;
  esac
}
complete -o nospace  -F _prs500 prs500

''')
        f.close()
        print 'done'
    except:
        if fatal_errors:
            raise
        print 'failed'
        import traceback
        traceback.print_exc()
        
def setup_udev_rules(group_file, reload, fatal_errors):
    print 'Trying to setup udev rules...'
    sys.stdout.flush()
    groups = open(group_file, 'rb').read()
    group = 'plugdev' if 'plugdev' in groups else 'usb'
    udev = open_file('/etc/udev/rules.d/95-calibre.rules')
    udev.write('''# Sony Reader PRS-500\n'''
               '''BUS=="usb", SYSFS{idProduct}=="029b", SYSFS{idVendor}=="054c", MODE="660", GROUP="%s"\n'''%(group,)
             )
    udev.close()
    fdi = open_file('/usr/share/hal/fdi/policy/20thirdparty/10-calibre.fdi')
    fdi.write('<?xml version="1.0" encoding="UTF-8"?>\n\n<deviceinfo version="0.2">\n')
    for cls in DEVICES:
        fdi.write(\
'''
  <device>
      <match key="usb_device.vendor_id" int="%(vendor_id)s">
          <match key="usb_device.product_id" int="%(product_id)s">
              <merge key="calibre.deviceclass" type="string">%(cls)s</merge>
          </match>
      </match>
  </device>
'''%dict(cls=cls.__name__, vendor_id=cls.VENDOR_ID, product_id=cls.PRODUCT_ID,
         prog=__appname__))
        fdi.write('\n'+cls.get_fdi())
    fdi.write('\n</deviceinfo>\n')
    fdi.close()
    if reload:
        called = False
        for hal in ('hald', 'hal', 'haldaemon'):
            hal = os.path.join('/etc/init.d', hal)
            if os.access(hal, os.X_OK):
                call((hal, 'restart'))
                called = True
                break
        if not called and os.access('/etc/rc.d/rc.hald', os.X_OK):
            call(('/etc/rc.d/rc.hald', 'restart'))
        
        try:
            check_call('udevadm control --reload_rules', shell=True)
        except:
            try:
                check_call('udevcontrol reload_rules', shell=True)
            except:
                try:
                    check_call('/etc/init.d/udev reload', shell=True)
                except:
                    if fatal_errors:
                        raise Exception("Couldn't reload udev, you may have to reboot")
                    print >>sys.stderr, "Couldn't reload udev, you may have to reboot"

def option_parser():
    from optparse import OptionParser
    parser = OptionParser()
    parser.add_option('--use-destdir', action='store_true', default=False, dest='destdir',
                      help='If set, respect the environment variable DESTDIR when installing files')
    parser.add_option('--do-not-reload-udev-hal', action='store_true', dest='dont_reload', default=False,
                      help='If set, do not try to reload udev rules and HAL FDI files')
    parser.add_option('--group-file', default='/etc/group', dest='group_file',
                      help='File from which to read group information. Default: %default')
    parser.add_option('--dont-check-root', action='store_true', default=False, dest='no_root',
                      help='If set, do not check if we are root.')
    parser.add_option('--make-errors-fatal', action='store_true', default=False, 
                      dest='fatal_errors', help='If set die on errors.')
    return parser

def install_man_pages(fatal_errors):
    from bz2 import compress
    import subprocess
    print 'Installing MAN pages...'
    manpath = '/usr/share/man/man1'
    f = open_file('/tmp/man_extra', 'wb')
    f.write('[see also]\nhttp://%s.kovidgoyal.net\n'%__appname__)
    f.close()
    for src in entry_points['console_scripts']:
        prog = src[:src.index('=')].strip()
        if prog in ('prs500', 'pdf-meta', 'epub-meta', 'lit-meta', 
                    'markdown-calibre', 'calibre-debug', 'fb2-meta',
                    'calibre-fontconfig', 'calibre-parallel'):
            continue
        help2man = ('help2man', prog, '--name', 'part of %s'%__appname__,
                    '--section', '1', '--no-info', '--include',
                    f.name, '--manual', __appname__)
        manfile = os.path.join(manpath, prog+'.1'+__appname__+'.bz2')
        try:
            p = subprocess.Popen(help2man, stdout=subprocess.PIPE)
        except OSError, err:
            import errno
            if err.errno != errno.ENOENT:
                raise
            print 'Failed to install MAN pages as help2man is missing from your system'
            break
        raw = re.compile(r'^\.IP\s*^([A-Z :]+)$', re.MULTILINE).sub(r'.SS\n\1', p.stdout.read())
        if not raw.strip():
            print 'Unable to create MAN page for', prog
            continue
        open_file(manfile).write(compress(raw))
        
     
    

def post_install():
    parser = option_parser()
    opts = parser.parse_args()[0]
    
    if not opts.no_root and os.geteuid() != 0:
        print >> sys.stderr, 'You must be root to run this command.'
        sys.exit(1)
        
    global use_destdir
    use_destdir = opts.destdir
    
    setup_udev_rules(opts.group_file, not opts.dont_reload, opts.fatal_errors)
    setup_completion(opts.fatal_errors)
    setup_desktop_integration(opts.fatal_errors)
    install_man_pages(opts.fatal_errors)
        
    try:
        from PyQt4 import Qt
        if Qt.PYQT_VERSION < int('0x40301', 16):
            print 'WARNING: You need PyQt >= 4.3.1 for the GUI. You have', Qt.PYQT_VERSION_STR, '\nYou may experience crashes or other strange behavior.'
    except ImportError:
        print 'WARNING: You do not have PyQt4 installed. The GUI will not work.'
    

    
VIEWER = '''\
[Desktop Entry]
Version=%s
Type=Application
Name=LRF Viewer
Comment=Viewer for LRF files (SONY ebook format files)
TryExec=lrfviewer
Exec=lrfviewer %%F
Icon=calibre-viewer
MimeType=application/x-sony-bbeb;
Categories=Graphics;Viewer;
'''%(__version__,)

GUI = '''\
[Desktop Entry]
Version=%s
Type=Application
Name=calibre - Ebook library management
Comment=E-book library management
TryExec=calibre
Exec=calibre
Icon=calibre-gui
Categories=Office;
'''%(__version__,)

MIME = '''\
<?xml version="1.0"?>
<mime-info xmlns='http://www.freedesktop.org/standards/shared-mime-info'>
    <mime-type type="application/x-sony-bbeb">
        <comment>SONY E-book compiled format</comment>
        <glob pattern="*.lrf"/>
    </mime-type>
    <mime-type type="text/lrs">
        <comment>SONY E-book source format</comment>
        <glob pattern="*.lrs"/>
    </mime-type>
</mime-info>
'''

def render_svg(image, dest):
    from PyQt4.QtGui import QPainter, QImage
    from PyQt4.QtSvg import QSvgRenderer
    svg = QSvgRenderer(image.readAll())
    painter = QPainter()
    image = QImage(128,128,QImage.Format_ARGB32_Premultiplied)
    painter.begin(image)
    painter.setRenderHints(QPainter.Antialiasing|QPainter.TextAntialiasing|QPainter.SmoothPixmapTransform|QPainter.HighQualityAntialiasing)
    painter.setCompositionMode(QPainter.CompositionMode_SourceOver)
    svg.render(painter)
    painter.end()
    image.save(dest)

def setup_desktop_integration(fatal_errors):
    try:
        from PyQt4.QtCore import QFile
        from calibre.gui2 import images_rc # Load images
        from tempfile import mkdtemp
        
        print 'Setting up desktop integration...'
        
        
        tdir = mkdtemp()
        cwd = os.getcwdu()
        try:
            os.chdir(tdir)
            render_svg(QFile(':/images/mimetypes/lrf.svg'), os.path.join(tdir, 'calibre-lrf.png'))
            check_call('xdg-icon-resource install --context mimetypes --size 128 calibre-lrf.png application-lrf', shell=True)
            check_call('xdg-icon-resource install --context mimetypes --size 128 calibre-lrf.png text-lrs', shell=True)
            QFile(':library').copy(os.path.join(tdir, 'calibre-gui.png'))
            check_call('xdg-icon-resource install --size 128 calibre-gui.png calibre-gui', shell=True)
            render_svg(QFile(':/images/viewer.svg'), os.path.join(tdir, 'calibre-viewer.png'))
            check_call('xdg-icon-resource install --size 128 calibre-viewer.png calibre-viewer', shell=True)
            
            f = open('calibre-lrfviewer.desktop', 'wb')
            f.write(VIEWER)
            f.close()
            f = open('calibre-gui.desktop', 'wb')
            f.write(GUI)
            f.close()
            check_call('xdg-desktop-menu install ./calibre-gui.desktop ./calibre-lrfviewer.desktop', shell=True)
            f = open('calibre-mimetypes', 'wb')
            f.write(MIME)
            f.close()
            check_call('xdg-mime install calibre-mimetypes', shell=True)
        finally:
            os.chdir(cwd)
            shutil.rmtree(tdir)
    except Exception, err:
        if fatal_errors:
            raise
        print >>sys.stderr, 'Could not setup desktop integration. Error:'
        print err
 
         
if __name__ == '__main__':
    post_install()
    
    
      

