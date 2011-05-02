# -*- coding: utf-8 -*-

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from calibre.devices.usbms.driver import USBMS
from calibre.ebooks import BOOK_EXTENSIONS

class USER_DEFINED(USBMS):

    name           = 'User Defined USB driver'
    gui_name       = 'User Defined USB Device'
    author         = 'Kovid Goyal'
    supported_platforms = ['windows', 'osx', 'linux']

    # Ordered list of supported formats
    FORMATS     = BOOK_EXTENSIONS

    VENDOR_ID   = 0xFFFF
    PRODUCT_ID  = 0xFFFF
    BCD         = None

    EBOOK_DIR_MAIN = ''
    EBOOK_DIR_CARD_A = ''

    VENDOR_NAME      = []
    WINDOWS_MAIN_MEM = ''
    WINDOWS_CARD_A_MEM = ''

    OSX_MAIN_MEM = 'Device Main Memory'

    MAIN_MEMORY_VOLUME_LABEL  = 'Device Main Memory'

    SUPPORTS_SUB_DIRS = True

    EXTRA_CUSTOMIZATION_MESSAGE = [
        _('USB Vendor ID (in hex)'),
        _('USB Product ID (in hex)'),
        _('USB Revision ID (in hex)'),
        _('Windows main memory vendor string'),
        _('Windows main memory ID string'),
        _('Windows card A vendor string'),
        _('Windows card A ID string'),
        _('Main memory folder'),
        _('Card A folder'),
    ]
    EXTRA_CUSTOMIZATION_DEFAULT = [
                '0x0000',
                '0x0000',
                '0x0000',
                '',
                '',
                '',
                '',
                '',
                '',
    ]
    OPT_USB_VENDOR_ID           = 0
    OPT_USB_PRODUCT_ID          = 1
    OPT_USB_REVISION_ID         = 2
    OPT_USB_WINDOWS_MM_VEN_ID   = 3
    OPT_USB_WINDOWS_MM_ID       = 4
    OPT_USB_WINDOWS_CA_VEN_ID   = 5
    OPT_USB_WINDOWS_CA_ID       = 6
    OPT_MAIN_MEM_FOLDER         = 7
    OPT_CARD_A_FOLDER           = 8

    def initialize(self):
        try:
            e = self.settings().extra_customization
            self.VENDOR_ID          = int(e[self.OPT_USB_VENDOR_ID], 16)
            self.PRODUCT_ID         = int(e[self.OPT_USB_PRODUCT_ID], 16)
            self.BCD                = [int(e[self.OPT_USB_REVISION_ID], 16)]
            if e[self.OPT_USB_WINDOWS_MM_VEN_ID]:
                self.VENDOR_NAME.append(e[self.OPT_USB_WINDOWS_MM_VEN_ID])
            if e[self.OPT_USB_WINDOWS_CA_VEN_ID] and \
                    e[self.OPT_USB_WINDOWS_CA_VEN_ID] not in self.VENDOR_NAME:
                self.VENDOR_NAME.append(e[self.OPT_USB_WINDOWS_CA_VEN_ID])
            self.WINDOWS_MAIN_MEM   = e[self.OPT_USB_WINDOWS_MM_ID] + '&'
            self.WINDOWS_CARD_A_MEM = e[self.OPT_USB_WINDOWS_CA_ID] + '&'
            self.EBOOK_DIR_MAIN     = e[self.OPT_MAIN_MEM_FOLDER]
            self.EBOOK_DIR_CARD_A   = e[self.OPT_CARD_A_FOLDER]
        except:
            import traceback
            traceback.print_exc()
        USBMS.initialize(self)