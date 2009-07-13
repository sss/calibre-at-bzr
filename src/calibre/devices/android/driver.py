#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'


from calibre.devices.usbms.driver import USBMS

class ANDROID(USBMS):
    name           = 'Android driver'
    description    = _('Communicate with Android phones.')
    author         = 'Kovid Goyal'
    supported_platforms = ['windows', 'osx', 'linux']


    # Ordered list of supported formats
    FORMATS     = ['epub']

    VENDOR_ID   = [
            0x0bb4,
            ]
    PRODUCT_ID  = [0x0c02]
    BCD         = [0x100]
    EBOOK_DIR_MAIN = 'wordplayer/calibre'

    VENDOR_NAME      = 'HTC'
    WINDOWS_MAIN_MEM = 'ANDROID_PHONE'

    OSX_MAIN_MEM = 'HTC Android Phone Media'

    MAIN_MEMORY_VOLUME_LABEL  = 'Android Internal Memory'

    SUPPORTS_SUB_DIRS = True


