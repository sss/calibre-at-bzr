#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os

from calibre.devices.usbms.driver import USBMS
from calibre import prints
prints

class PALMPRE(USBMS):

    name           = 'Palm Pre Device Interface'
    gui_name       = 'Palm Pre'
    description    = _('Communicate with the Palm Pre')
    author         = 'Kovid Goyal'
    supported_platforms = ['windows', 'osx', 'linux']

    # Ordered list of supported formats
    FORMATS     = ['epub', 'mobi', 'prc', 'pdb', 'txt']

    VENDOR_ID   = [0x0830]
    PRODUCT_ID  = [0x8004, 0x8002, 0x0101]
    BCD         = [0x0316]

    VENDOR_NAME = 'PALM'
    WINDOWS_MAIN_MEM = 'PRE'

    EBOOK_DIR_MAIN = 'E-books'


class AVANT(USBMS):
    name           = 'Booq Avant Device Interface'
    gui_name       = 'bq Avant'
    description    = _('Communicate with the Bq Avant')
    author         = 'Kovid Goyal'
    supported_platforms = ['windows', 'osx', 'linux']

    # Ordered list of supported formats
    FORMATS     = ['epub', 'fb2', 'html', 'rtf', 'pdf', 'txt']

    VENDOR_ID   = [0x0525]
    PRODUCT_ID  = [0xa4a5]
    BCD         = [0x0319]

    VENDOR_NAME = 'E-BOOK'
    WINDOWS_MAIN_MEM = WINDOWS_CARD_A_MEM = 'READER'

    EBOOK_DIR_MAIN = ''
    SUPPORTS_SUB_DIRS = True

class SWEEX(USBMS):
    # Identical to the Promedia
    name           = 'Sweex Device Interface'
    gui_name       = 'Sweex/Kogan/Q600/Wink'
    description    = _('Communicate with the Sweex/Kogan/Q600/Wink')
    author         = 'Kovid Goyal'
    supported_platforms = ['windows', 'osx', 'linux']

    # Ordered list of supported formats
    FORMATS     = ['epub', 'mobi', 'prc', 'fb2', 'html', 'rtf', 'chm', 'pdf', 'txt']

    VENDOR_ID   = [0x0525, 0x177f]
    PRODUCT_ID  = [0xa4a5, 0x300]
    BCD         = [0x0319, 0x110, 0x325]

    VENDOR_NAME = ['SWEEX', 'LINUX']
    WINDOWS_MAIN_MEM = WINDOWS_CARD_A_MEM = ['EBOOKREADER', 'FILE-STOR_GADGET']

    EBOOK_DIR_MAIN = ''
    SUPPORTS_SUB_DIRS = True


class PDNOVEL(USBMS):
    name = 'Pandigital Novel device interface'
    gui_name = 'PD Novel'
    description = _('Communicate with the Pandigital Novel')
    author = 'Kovid Goyal'
    supported_platforms = ['windows', 'linux', 'osx']
    FORMATS = ['epub', 'pdf']

    VENDOR_ID   = [0x18d1]
    PRODUCT_ID  = [0xb004, 0xa004]
    BCD         = [0x224]

    VENDOR_NAME = 'ANDROID'
    WINDOWS_MAIN_MEM = WINDOWS_CARD_A_MEM = '__UMS_COMPOSITE'
    THUMBNAIL_HEIGHT = 130

    EBOOK_DIR_MAIN = EBOOK_DIR_CARD_A = 'eBooks'
    SUPPORTS_SUB_DIRS = False
    DELETE_EXTS = ['.jpg', '.jpeg', '.png']


    def upload_cover(self, path, filename, metadata, filepath):
        coverdata = getattr(metadata, 'thumbnail', None)
        if coverdata and coverdata[2]:
            with open('%s.jpg' % os.path.join(path, filename), 'wb') as coverfile:
                coverfile.write(coverdata[2])

class PDNOVEL_KOBO(PDNOVEL):
    name = 'Pandigital Kobo device interface'
    gui_name = 'PD Novel (Kobo)'
    description = _('Communicate with the Pandigital Novel')

    BCD         = [0x222]

    EBOOK_DIR_MAIN = 'eBooks'

    def upload_cover(self, path, filename, metadata, filepath):
        coverdata = getattr(metadata, 'thumbnail', None)
        if coverdata and coverdata[2]:
            dirpath = os.path.join(path, '.thumbnail')
            if not os.path.exists(dirpath):
                os.makedirs(dirpath)
            with open(os.path.join(dirpath, filename+'.jpg'), 'wb') as coverfile:
                coverfile.write(coverdata[2])


class VELOCITYMICRO(USBMS):
    name = 'VelocityMicro device interface'
    gui_name = 'VelocityMicro'
    description = _('Communicate with the VelocityMicro')
    author = 'Kovid Goyal'
    supported_platforms = ['windows', 'linux', 'osx']
    FORMATS = ['epub', 'pdb', 'txt', 'html', 'pdf']

    VENDOR_ID   = [0x18d1]
    PRODUCT_ID  = [0xb015]
    BCD         = [0x224]

    VENDOR_NAME = 'ANDROID'
    WINDOWS_MAIN_MEM = WINDOWS_CARD_A_MEM = '__UMS_COMPOSITE'

    EBOOK_DIR_MAIN = 'eBooks'
    SUPPORTS_SUB_DIRS = False

class GEMEI(USBMS):
    name           = 'Gemei Device Interface'
    gui_name       = 'GM2000'
    description    = _('Communicate with the GM2000')
    author         = 'Kovid Goyal'
    supported_platforms = ['windows', 'osx', 'linux']

    # Ordered list of supported formats
    FORMATS     = ['epub', 'chm', 'html', 'pdb', 'pdf', 'txt']

    VENDOR_ID   = [0x07c4]
    PRODUCT_ID  = [0xa4a5]
    BCD         = None

    VENDOR_NAME = 'CHINA'
    WINDOWS_MAIN_MEM = WINDOWS_CARD_A_MEM = 'CHIP'

    EBOOK_DIR_MAIN = 'eBooks'
    SUPPORTS_SUB_DIRS = True

class LUMIREAD(USBMS):
    name           = 'Acer Lumiread Device Interface'
    gui_name       = 'Lumiread'
    description    = _('Communicate with the Acer Lumiread')
    author         = 'Kovid Goyal'
    supported_platforms = ['windows', 'osx', 'linux']

    # Ordered list of supported formats
    FORMATS     = ['epub', 'pdf', 'mobi', 'chm', 'txt', 'doc', 'docx', 'rtf']

    VENDOR_ID   = [0x1025]
    PRODUCT_ID  = [0x048d]
    BCD         = [0x323]

    EBOOK_DIR_MAIN = EBOOK_DIR_CARD_A = 'books'
    SUPPORTS_SUB_DIRS = True

    THUMBNAIL_HEIGHT = 200

    VENDOR_NAME = 'ACER'
    WINDOWS_MAIN_MEM = WINDOWS_CARD_A_MEM = 'LUMIREAD_600'

    def upload_cover(self, path, filename, metadata, filepath):
        if metadata.thumbnail and metadata.thumbnail[-1]:
            cfilepath = filepath.replace('/', os.sep)
            cfilepath = cfilepath.replace(os.sep+'books'+os.sep,
                    os.sep+'covers'+os.sep, 1)
            pdir = os.path.dirname(cfilepath)
            if not os.path.exists(pdir):
                os.makedirs(pdir)
            with open(cfilepath+'.jpg', 'wb') as f:
                f.write(metadata.thumbnail[-1])

class ALURATEK_COLOR(USBMS):

    name           = 'Aluratek Color Device Interface'
    gui_name       = 'Aluratek Color'
    description    = _('Communicate with the Aluratek Color')
    author         = 'Kovid Goyal'
    supported_platforms = ['windows', 'osx', 'linux']

    # Ordered list of supported formats
    FORMATS     = ['epub', 'fb2', 'txt', 'pdf']

    VENDOR_ID   = [0x1f3a]
    PRODUCT_ID  = [0x1000]
    BCD         = [0x0002]

    EBOOK_DIR_MAIN = EBOOK_DIR_CARD_A = 'books'

    VENDOR_NAME = ['USB_2.0', 'EZREADER']
    WINDOWS_MAIN_MEM = WINDOWS_CARD_A_MEM = ['USB_FLASH_DRIVER', '.']

class TREKSTOR(USBMS):

    name           = 'Trekstor E-book player device interface'
    gui_name       = 'Trekstor'
    description    = _('Communicate with the Trekstor')
    author         = 'Kovid Goyal'
    supported_platforms = ['windows', 'osx', 'linux']

    # Ordered list of supported formats
    FORMATS     = ['epub', 'txt', 'pdf']

    VENDOR_ID   = [0x1e68]
    PRODUCT_ID  = [0x0041, 0x0042, 0x0052, 0x004e, 0x0056,
            0x003e, # This is for the EBOOK_PLAYER_5M https://bugs.launchpad.net/bugs/792091
            0x5cL, # This is for the 4ink http://www.mobileread.com/forums/showthread.php?t=191318
            ]
    BCD         = [0x0002, 0x100]

    EBOOK_DIR_MAIN = 'Ebooks'

    VENDOR_NAME = 'TREKSTOR'
    WINDOWS_MAIN_MEM = WINDOWS_CARD_A_MEM = ['EBOOK_PLAYER_7',
            'EBOOK_PLAYER_5M', 'EBOOK-READER_3.0', 'EREADER_PYRUS']
    SUPPORTS_SUB_DIRS = True
    SUPPORTS_SUB_DIRS_DEFAULT = False

class EEEREADER(USBMS):

    name           = 'Asus EEE Reader device interface'
    gui_name       = 'EEE Reader'
    description    = _('Communicate with the EEE Reader')
    author         = 'Kovid Goyal'
    supported_platforms = ['windows', 'osx', 'linux']

    # Ordered list of supported formats
    FORMATS     = ['epub', 'fb2', 'txt', 'pdf']

    VENDOR_ID   = [0x0b05]
    PRODUCT_ID  = [0x178f, 0x17a1]
    BCD         = [0x0319]

    EBOOK_DIR_MAIN = EBOOK_DIR_CARD_A = 'Book'

    VENDOR_NAME = ['LINUX', 'ASUS']
    WINDOWS_MAIN_MEM = WINDOWS_CARD_A_MEM = ['FILE-STOR_GADGET', 'EEE_NOTE']

class ADAM(USBMS):

    name = 'Notion Ink Adam device interface'
    gui_name = 'Adam'

    description    = _('Communicate with the Adam tablet')
    author         = 'Kovid Goyal'
    supported_platforms = ['windows', 'osx', 'linux']

    # Ordered list of supported formats
    FORMATS     = ['epub', 'pdf', 'doc']

    VENDOR_ID   = [0x0955]
    PRODUCT_ID  = [0x7100]
    BCD         = [0x9999]

    EBOOK_DIR_MAIN = 'eBooks'

    VENDOR_NAME = 'NI'
    WINDOWS_MAIN_MEM = WINDOWS_CARD_A_MEM = ['ADAM']
    SUPPORTS_SUB_DIRS = True

class NEXTBOOK(USBMS):

    name           = 'Nextbook device interface'
    gui_name       = 'Nextbook'
    description    = _('Communicate with the Nextbook Reader')
    author         = 'Kovid Goyal'
    supported_platforms = ['windows', 'osx', 'linux']

    # Ordered list of supported formats
    FORMATS     = ['epub', 'fb2', 'txt', 'pdf']

    VENDOR_ID   = [0x05e3]
    PRODUCT_ID  = [0x0726]
    BCD         = [0x021a]

    EBOOK_DIR_MAIN = ''

    VENDOR_NAME = ['NEXT2', 'BK7005']
    WINDOWS_MAIN_MEM = WINDOWS_CARD_A_MEM = ['1.0.14', 'PLAYER']
    SUPPORTS_SUB_DIRS = True
    THUMBNAIL_HEIGHT = 120

    '''
    def upload_cover(self, path, filename, metadata, filepath):
        if metadata.thumbnail and metadata.thumbnail[-1]:
            path = path.replace('/', os.sep)
            is_main = path.startswith(self._main_prefix)
            prefix = None
            if is_main:
                prefix = self._main_prefix
            else:
                if self._card_a_prefix and \
                    path.startswith(self._card_a_prefix):
                    prefix = self._card_a_prefix
                elif self._card_b_prefix and \
                        path.startswith(self._card_b_prefix):
                    prefix = self._card_b_prefix
            if prefix is None:
                prints('WARNING: Failed to find prefix for:', filepath)
                return
            thumbnail_dir = os.path.join(prefix, '.Cover')

            relpath = os.path.relpath(filepath, prefix)
            if relpath.startswith('..\\'):
                relpath = relpath[3:]
            thumbnail_dir = os.path.join(thumbnail_dir, relpath)
            if not os.path.exists(thumbnail_dir):
                os.makedirs(thumbnail_dir)
            with open(os.path.join(thumbnail_dir, filename+'.jpg'), 'wb') as f:
                f.write(metadata.thumbnail[-1])
    '''

class MOOVYBOOK(USBMS):

    name           = 'Moovybook device interface'
    gui_name       = 'Moovybook'
    description    = _('Communicate with the Moovybook Reader')
    author         = 'Kovid Goyal'
    supported_platforms = ['windows', 'osx', 'linux']

    # Ordered list of supported formats
    FORMATS     = ['epub', 'txt', 'pdf']

    VENDOR_ID   = [0x1cae]
    PRODUCT_ID  = [0x9b08]
    BCD         = [0x02]

    EBOOK_DIR_MAIN = ''

    SUPPORTS_SUB_DIRS = True

    def get_main_ebook_dir(self, for_upload=False):
        return 'Books' if for_upload else self.EBOOK_DIR_MAIN

class COBY(USBMS):

    name           = 'COBY MP977 device interface'
    gui_name       = 'COBY'
    description    = _('Communicate with the COBY')
    author         = 'Kovid Goyal'
    supported_platforms = ['windows', 'osx', 'linux']

    # Ordered list of supported formats
    FORMATS     = ['epub', 'pdf']

    VENDOR_ID   = [0x1e74]
    PRODUCT_ID  = [0x7121]
    BCD         = [0x02]
    VENDOR_NAME = 'USB_2.0'
    WINDOWS_MAIN_MEM = WINDOWS_CARD_A_MEM = 'MP977_DRIVER'

    EBOOK_DIR_MAIN = ''

    SUPPORTS_SUB_DIRS = False

    def get_carda_ebook_dir(self, for_upload=False):
        if for_upload:
            return 'eBooks'
        return self.EBOOK_DIR_CARD_A

class EX124G(USBMS):

    name = 'Motorola Ex124G device interface'
    gui_name = 'Ex124G'
    description = _('Communicate with the Ex124G')

    author         = 'Kovid Goyal'
    supported_platforms = ['windows', 'osx', 'linux']

    # Ordered list of supported formats
    FORMATS     = ['mobi', 'prc', 'azw']

    VENDOR_ID   = [0x0e8d]
    PRODUCT_ID  = [0x0002]
    BCD         = [0x0100]
    VENDOR_NAME = 'MOTOROLA'
    WINDOWS_MAIN_MEM = WINDOWS_CARD_A_MEM = '_PHONE'

    EBOOK_DIR_MAIN = 'eBooks'

    SUPPORTS_SUB_DIRS = False

    def get_carda_ebook_dir(self, for_upload=False):
        if for_upload:
            return 'eBooks'
        return self.EBOOK_DIR_CARD_A


