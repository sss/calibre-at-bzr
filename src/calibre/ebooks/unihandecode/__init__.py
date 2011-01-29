# -*- coding: utf-8 -*-

__license__ = 'GPL 3'
__copyright__ = '2010, Hiroshi Miura <miurahr@linux.com>'
__docformat__ = 'restructuredtext en'
__all__ = ["Unihandecoder"]

'''
Decode unicode text to an ASCII representation of the text. 
Translate unicode characters to ASCII.

inspired from John's unidecode library.
Copyright(c) 2009, John Schember

Tranliterate the string from unicode characters to ASCII in Chinese and others.

'''

class Unihandecoder(object):
    preferred_encoding = None
    decoder = None

    def __init__(self, lang="zh", encoding='utf-8'):
        self.preferred_encoding = encoding
        if lang in [u"ja","ja",u"Ja","Ja",u"Japanese"]:
            from calibre.ebooks.unihandecode.jadecoder import Jadecoder
            self.decoder = Jadecoder()
        elif lang in [u"kr", "kr", u"Kr", "Kr", u"Korean"]:
            from calibre.ebooks.unihandecode.krdecoder import Krdecoder
            self.decoder = Krdecoder()
        elif lang in [u"vn", "vn", u"Vietnum"]:
            from calibre.ebooks.unihandecode.vndecoder import Vndecoder
            self.decoder = Vndecoder()
        else: #zh and others
            from calibre.ebooks.unihandecode.unidecoder import Unidecoder
            self.decoder = Unidecoder()

    def decode(self, text):
        try:
            unicode # python2
            if not isinstance(text, unicode):
                try:
                    text = unicode(text)
                except:
                    try:
                        text = text.decode(self.preferred_encoding)
                    except:
                        text = text.decode('utf-8', 'replace')
        except: # python3, str is unicode
            pass
        return self.decoder.decode(text)

def unidecode(text):
    '''
    backword compatibility to unidecode
    '''
    from calibre.ebooks.unihandecode.unidecoder import Unidecoder
    decoder = Unihandecoder()
    return decoder.decode(text)
