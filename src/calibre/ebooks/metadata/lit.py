__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
'''
Support for reading the metadata from a LIT file.
'''

import cStringIO, os

from calibre.ebooks.metadata import MetaInformation
from calibre.ebooks.metadata.opf2 import OPF

def get_metadata(stream):
    from calibre.ebooks.lit.reader import LitContainer
    from calibre.utils.logging import Log
    litfile = LitContainer(stream, Log())
    src = litfile.get_metadata().encode('utf-8')
    litfile = litfile._litfile
    opf = OPF(cStringIO.StringIO(src), os.getcwd())
    mi = MetaInformation(opf)
    covers = []
    for item in opf.iterguide():
        if 'cover' not in item.get('type', '').lower():
            continue
        ctype = item.get('type')
        href = item.get('href', '')
        candidates = [href, href.replace('&', '%26')]
        for item in litfile.manifest.values():
            if item.path in candidates:
                try:
                    covers.append((litfile.get_file('/data/'+item.internal),
                                   ctype))
                except:
                    pass
                break
    covers.sort(cmp=lambda x, y:cmp(len(x[0]), len(y[0])), reverse=True)
    idx = 0
    if len(covers) > 1:
        if covers[1][1] == covers[0][1]+'-standard':
            idx = 1
    mi.cover_data = ('jpg', covers[idx][0])
    return mi

