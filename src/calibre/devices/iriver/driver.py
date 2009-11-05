#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from calibre.devices.usbms.driver import USBMS

class IRIVER_STORY(USBMS):

    name           = 'Iriver Story Device Interface'
    gui_name       = 'Iriver Story'
    description    = _('Communicate with the Iriver Story reader.')
    author         = _('Kovid Goyal')
    supported_platforms = ['windows', 'osx', 'linux']

    # Ordered list of supported formats
    FORMATS     = ['epub', 'pdf', 'txt']

    VENDOR_ID   = [0x1006]
    PRODUCT_ID  = [0x4023]
    BCD         = [0x0323]

    VENDOR_NAME = 'IRIVER'
    WINDOWS_MAIN_MEM = 'STORY'
    WINDOWS_CARD_A_MEM = 'STORY'

    #OSX_MAIN_MEM = 'Kindle Internal Storage Media'
    #OSX_CARD_A_MEM = 'Kindle Card Storage Media'

    MAIN_MEMORY_VOLUME_LABEL  = 'Story Main Memory'
    STORAGE_CARD_VOLUME_LABEL = 'Story Storage Card'

    SUPPORTS_SUB_DIRS = True

    def windows_sort_drives(self, drives):
        main = drives.get('main', None)
        card = drives.get('carda', None)
        if card and main and card < main:
            drives['main'] = card
            drives['carda'] = main

        return drives

