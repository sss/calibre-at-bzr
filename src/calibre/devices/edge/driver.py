# -*- coding: utf-8 -*-

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal'
__docformat__ = 'restructuredtext en'

'''
Device driver for Barns and Nobel's Nook
'''


from calibre.devices.usbms.driver import USBMS

class EDGE(USBMS):

    name           = 'Edge Device Interface'
    gui_name       = _('Entourage Edge')
    description    = _('Communicate with the Entourage Edge.')
    author         = 'Kovid Goyal'
    supported_platforms = ['windows', 'linux', 'osx']

    # Ordered list of supported formats
    FORMATS     = ['epub', 'pdf']

    VENDOR_ID   = [0x0bb4]
    PRODUCT_ID  = [0x0c02]
    BCD         = [0x0223]

    VENDOR_NAME = 'ANDROID'
    WINDOWS_MAIN_MEM = '__FILE-STOR_GADG'
    WINDOWS_CARD_A_MEM = '__FILE-STOR_GADG'

    MAIN_MEMORY_VOLUME_LABEL  = 'Edge Main Memory'
    STORAGE_CARD_VOLUME_LABEL = 'Edge Storage Card'

    EBOOK_DIR_MAIN = 'download'
    SUPPORTS_SUB_DIRS = True

    def windows_sort_drives(self, drives):
        main = drives.get('main', None)
        card = drives.get('carda', None)
        if card and main and card < main:
            drives['main'] = card
            drives['carda'] = main

        return drives

