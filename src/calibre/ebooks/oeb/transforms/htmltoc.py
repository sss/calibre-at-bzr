'''
HTML-TOC-adding transform.
'''
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2008, Marshall T. Vandegrift <llasram@gmail.com>'

from calibre.ebooks.oeb.base import XML, XHTML, XHTML_NS
from calibre.ebooks.oeb.base import XHTML_MIME, CSS_MIME
from calibre.ebooks.oeb.base import element

__all__ = ['HTMLTOCAdder']

DEFAULT_TITLE = __('Table of Contents')

STYLE_CSS = {
    'nested': """
.calibre_toc_header {
  text-align: center;
}
.calibre_toc_block {
  margin-left: 1.2em;
  text-indent: -1.2em;
}
.calibre_toc_block .calibre_toc_block {
  margin-left: 2.4em;
}
.calibre_toc_block .calibre_toc_block .calibre_toc_block {
  margin-left: 3.6em;
}
""",
   
    'centered': """
.calibre_toc_header {
  text-align: center;
}
.calibre_toc_block {
  text-align: center;
}
body > .calibre_toc_block {
  margin-top: 1.2em;
}
"""
    }

class HTMLTOCAdder(object):
    def __init__(self, title=None, style='nested'):
        self.title = title
        self.style = style
    
    @classmethod
    def config(cls, cfg):
        group = cfg.add_group('htmltoc', _('HTML TOC generation options.'))
        group('toc_title', ['--toc-title'], default=None, 
              help=_('Title for any generated in-line table of contents.'))
        return cfg

    @classmethod
    def generate(cls, opts):
        return cls(title=opts.toc_title)
    
    def __call__(self, oeb, context):
        if 'toc' in oeb.guide:
            return
        if not getattr(getattr(oeb, 'toc', False), 'nodes', False):
            return
        oeb.logger.info('Generating in-line TOC...')
        title = self.title or oeb.translate(DEFAULT_TITLE)
        style = self.style
        if style not in STYLE_CSS:
            oeb.logger.error('Unknown TOC style %r' % style)
            style = 'nested'
        id, css_href = oeb.manifest.generate('tocstyle', 'tocstyle.css')
        oeb.manifest.add(id, css_href, CSS_MIME, data=STYLE_CSS[style])
        language = str(oeb.metadata.language[0])
        contents = element(None, XHTML('html'), nsmap={None: XHTML_NS},
                           attrib={XML('lang'): language})
        head = element(contents, XHTML('head'))
        htitle = element(head, XHTML('title'))
        htitle.text = title
        element(head, XHTML('link'), rel='stylesheet', type=CSS_MIME,
                href=css_href)
        body = element(contents, XHTML('body'),
                       attrib={'class': 'calibre_toc'})
        h1 = element(body, XHTML('h1'),
                     attrib={'class': 'calibre_toc_header'})
        h1.text = title
        self.add_toc_level(body, oeb.toc)
        id, href = oeb.manifest.generate('contents', 'contents.xhtml')
        item = oeb.manifest.add(id, href, XHTML_MIME, data=contents)
        oeb.spine.add(item, linear=False)
        oeb.guide.add('toc', 'Table of Contents', href)

    def add_toc_level(self, elem, toc):
        for node in toc:
            block = element(elem, XHTML('div'),
                            attrib={'class': 'calibre_toc_block'})
            line = element(block, XHTML('a'),
                           attrib={'href': node.href,
                                   'class': 'calibre_toc_line'})
            line.text = node.title
            self.add_toc_level(block, node)
