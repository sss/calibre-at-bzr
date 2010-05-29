__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from calibre.devices.usbms.driver import USBMS

class TECLAST_K3(USBMS):

    name           = 'Teclast K3 Device Interface'
    gui_name       = 'K3'
    description    = _('Communicate with the Teclast K3 reader.')
    author         = 'Kovid Goyal'
    supported_platforms = ['windows', 'osx', 'linux']

    # Ordered list of supported formats
    FORMATS     = ['epub', 'fb2', 'doc', 'pdf', 'txt']

    VENDOR_ID   = [0x071b]
    PRODUCT_ID  = [0x3203]
    BCD         = [0x0000]

    VENDOR_NAME      = 'TECLAST'
    WINDOWS_MAIN_MEM = 'DIGITAL_PLAYER'
    WINDOWS_CARD_A_MEM = 'DIGITAL_PLAYER'

    MAIN_MEMORY_VOLUME_LABEL  = 'K3 Main Memory'
    STORAGE_CARD_VOLUME_LABEL = 'K3 Storage Card'

    EBOOK_DIR_MAIN = ''
    EBOOK_DIR_CARD_A = ''
    SUPPORTS_SUB_DIRS = True


class NEWSMY(TECLAST_K3):
    name = 'Newsmy device interface'
    gui_name = 'Newsmy'
    description    = _('Communicate with the Newsmy reader.')

    FORMATS = ['epub', 'fb2', 'pdb', 'html', 'pdf', 'txt', 'skt']

    VENDOR_NAME      = ''
    WINDOWS_MAIN_MEM = 'NEWSMY'
    WINDOWS_CARD_A_MEM = 'USBDISK____SD'

class IPAPYRUS(TECLAST_K3):

    name = 'iPapyrus device interface'
    gui_name = 'iPapyrus'
    description    = _('Communicate with the iPapyrus reader.')

    FORMATS = ['epub', 'pdf', 'txt']

    VENDOR_NAME      = 'E_READER'
    WINDOWS_MAIN_MEM = ''

