from __future__ import with_statement
__license__ = 'GPL 3'
__copyright__ = '2010, sengian <sengian1@gmail.com>'
__docformat__ = 'restructuredtext en'

import re, htmlentitydefs

_ascii_pat = None

def clean_ascii_chars(txt, charlist=None):
    '''
    Remove ASCII control chars: 0 to 8 and 11, 12, 14-31 by default
    This is all control chars except \\t,\\n and \\r
    '''
    if not txt:
        return ''
    global _ascii_pat
    if _ascii_pat is None:
        chars = list(range(8)) + [0x0B, 0x0C] + list(range(0x0E, 0x1F))
        _ascii_pat = re.compile(u'|'.join(map(unichr, chars)))

    if charlist is None:
        pat = _ascii_pat
    else:
        pat = re.compile(u'|'.join(map(unichr, charlist)))
    return pat.sub('', txt)

##
# Fredrik Lundh: http://effbot.org/zone/re-sub.htm#unescape-html
# Removes HTML or XML character references and entities from a text string.
#
# @param text The HTML (or XML) source text.
# @return The plain text, as a Unicode string, if necessary.

def unescape(text, rm=False, rchar=u''):
    def fixup(m, rm=rm, rchar=rchar):
        text = m.group(0)
        if text[:2] == "&#":
            # character reference
            try:
                if text[:3] == "&#x":
                    return unichr(int(text[3:-1], 16))
                else:
                    return unichr(int(text[2:-1]))
            except ValueError:
                pass
        else:
            # named entity
            try:
                text = unichr(htmlentitydefs.name2codepoint[text[1:-1]])
            except KeyError:
                pass
        if rm:
            return rchar #replace by char
        return text # leave as is
    return re.sub("&#?\w+;", fixup, text)
