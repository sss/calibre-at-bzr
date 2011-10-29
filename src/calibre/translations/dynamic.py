'''
Dynamic language lookup of translations for user-visible strings.
'''

__license__   = 'GPL v3'
__copyright__ = '2008, Marshall T. Vandegrift <llasram@gmail.com>'

import cStringIO
from gettext import GNUTranslations
from calibre.utils.localization import get_lc_messages_path, ZipFile

__all__ = ['translate']

_CACHE = {}

def translate(lang, text):
    trans = None
    if lang in _CACHE:
        trans = _CACHE[lang]
    else:
        mpath = get_lc_messages_path(lang)
        if mpath is not None:
            with ZipFile(P('localization/locales.zip',
                allow_user_override=False), 'r') as zf:
                try:
                    buf = cStringIO.StringIO(zf.read(mpath + '/messages.mo'))
                except:
                    pass
                else:
                    trans = GNUTranslations(buf)
                    _CACHE[lang] = trans
    if trans is None:
        return getattr(__builtins__, '_', lambda x: x)(text)
    return trans.ugettext(text)
