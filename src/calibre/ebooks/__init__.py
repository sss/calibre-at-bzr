from __future__ import with_statement
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'

'''
Code for the conversion of ebook formats and the reading of metadata
from various formats.
'''

import traceback, os
from calibre import CurrentDir

class ConversionError(Exception):

    def __init__(self, msg, only_msg=False):
        Exception.__init__(self, msg)
        self.only_msg = only_msg

class UnknownFormatError(Exception):
    pass

class DRMError(ValueError):
    pass

class ParserError(ValueError):
    pass

BOOK_EXTENSIONS = ['lrf', 'rar', 'zip', 'rtf', 'lit', 'txt', 'txtz', 'htm', 'xhtm',
                   'html', 'xhtml', 'pdf', 'pdb', 'pdr', 'prc', 'mobi', 'azw', 'doc',
                   'epub', 'fb2', 'djvu', 'lrx', 'cbr', 'cbz', 'cbc', 'oebzip',
                   'rb', 'imp', 'odt', 'chm', 'tpz', 'azw1', 'pml', 'pmlz', 'mbp', 'tan', 'snb']

class HTMLRenderer(object):

    def __init__(self, page, loop):
        self.page, self.loop = page, loop
        self.data = ''
        self.exception = self.tb = None

    def __call__(self, ok):
        from PyQt4.Qt import QImage, QPainter, QByteArray, QBuffer
        try:
            if not ok:
                raise RuntimeError('Rendering of HTML failed.')
            de = self.page.mainFrame().documentElement()
            pe = de.findFirst('parsererror')
            if not pe.isNull():
                raise ParserError(pe.toPlainText())
            image = QImage(self.page.viewportSize(), QImage.Format_ARGB32)
            image.setDotsPerMeterX(96*(100/2.54))
            image.setDotsPerMeterY(96*(100/2.54))
            painter = QPainter(image)
            self.page.mainFrame().render(painter)
            painter.end()
            ba = QByteArray()
            buf = QBuffer(ba)
            buf.open(QBuffer.WriteOnly)
            image.save(buf, 'JPEG')
            self.data = str(ba.data())
        except Exception, e:
            self.exception = e
            self.traceback = traceback.format_exc()
        finally:
            self.loop.exit(0)


def extract_cover_from_embedded_svg(html, base, log):
    from lxml import etree
    from calibre.ebooks.oeb.base import XPath, SVG, XLINK
    root = etree.fromstring(html)

    svg = XPath('//svg:svg')(root)
    if len(svg) == 1 and len(svg[0]) == 1 and svg[0][0].tag == SVG('image'):
        image = svg[0][0]
        href = image.get(XLINK('href'), None)
        path = os.path.join(base, *href.split('/'))
        if href and os.access(path, os.R_OK):
            return open(path, 'rb').read()

def extract_calibre_cover(raw, base, log):
    from calibre.ebooks.BeautifulSoup import BeautifulSoup
    soup = BeautifulSoup(raw)
    matches = soup.find(name=['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'span',
        'font', 'br'])
    images = soup.findAll('img')
    if matches is None and len(images) == 1 and \
            images[0].get('alt', '')=='cover':
        img = images[0]
        img = os.path.join(base, *img['src'].split('/'))
        if os.path.exists(img):
            return open(img, 'rb').read()

def render_html_svg_workaround(path_to_html, log, width=590, height=750):
    from calibre.ebooks.oeb.base import SVG_NS
    raw = open(path_to_html, 'rb').read()
    data = None
    if SVG_NS in raw:
        try:
            data = extract_cover_from_embedded_svg(raw,
                   os.path.dirname(path_to_html), log)
        except:
            pass
    if data is None:
        try:
            data = extract_calibre_cover(raw, os.path.dirname(path_to_html), log)
        except:
            pass
    if data is None:
        renderer = render_html(path_to_html, width, height)
        data = getattr(renderer, 'data', None)
    return data


def render_html(path_to_html, width=590, height=750, as_xhtml=True):
    from PyQt4.QtWebKit import QWebPage
    from PyQt4.Qt import QEventLoop, QPalette, Qt, QUrl, QSize
    from calibre.gui2 import is_ok_to_use_qt
    if not is_ok_to_use_qt(): return None
    path_to_html = os.path.abspath(path_to_html)
    with CurrentDir(os.path.dirname(path_to_html)):
        page = QWebPage()
        pal = page.palette()
        pal.setBrush(QPalette.Background, Qt.white)
        page.setPalette(pal)
        page.setViewportSize(QSize(width, height))
        page.mainFrame().setScrollBarPolicy(Qt.Vertical, Qt.ScrollBarAlwaysOff)
        page.mainFrame().setScrollBarPolicy(Qt.Horizontal, Qt.ScrollBarAlwaysOff)
        loop = QEventLoop()
        renderer = HTMLRenderer(page, loop)
        page.loadFinished.connect(renderer, type=Qt.QueuedConnection)
        if as_xhtml:
            page.mainFrame().setContent(open(path_to_html, 'rb').read(),
                    'application/xhtml+xml', QUrl.fromLocalFile(path_to_html))
        else:
            page.mainFrame().load(QUrl.fromLocalFile(path_to_html))
        loop.exec_()
    renderer.loop = renderer.page = None
    page.loadFinished.disconnect()
    del page
    del loop
    if isinstance(renderer.exception, ParserError) and as_xhtml:
        return render_html(path_to_html, width=width, height=height,
                as_xhtml=False)
    return renderer

def check_ebook_format(stream, current_guess):
    ans = current_guess
    if current_guess.lower() in ('prc', 'mobi', 'azw', 'azw1'):
        stream.seek(0)
        if stream.read(3) == 'TPZ':
            ans = 'tpz'
        stream.seek(0)
    return ans

def normalize(x):
    if isinstance(x, unicode):
        import unicodedata
        x = unicodedata.normalize('NFKC', x)
    return x

def calibre_cover(title, author_string, series_string=None,
        output_format='jpg', title_size=46, author_size=36):
    title = normalize(title)
    author_string = normalize(author_string)
    series_string = normalize(series_string)
    from calibre.utils.magick.draw import create_cover_page, TextLine
    lines = [TextLine(title, title_size), TextLine(author_string, author_size)]
    if series_string:
        lines.append(TextLine(series_string, author_size))
    return create_cover_page(lines, I('library.png'), output_format='jpg')

