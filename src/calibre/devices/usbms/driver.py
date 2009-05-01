from __future__ import with_statement
__license__   = 'GPL v3'
__copyright__ = '2009, John Schember <john at nachtimwald.com>'
'''
Generic USB Mass storage device driver. This is not a complete stand alone
driver. It is intended to be subclassed with the relevant parts implemented
for a particular device.
'''

import os, fnmatch, shutil
from itertools import cycle

from calibre.ebooks.metadata import authors_to_string
from calibre.devices.usbms.cli import CLI
from calibre.devices.usbms.device import Device
from calibre.devices.usbms.books import BookList, Book
from calibre.devices.errors import DeviceError, FreeSpaceError
from calibre.devices.mime import mime_type_ext

# CLI must come before Device as it implments the CLI functions that
# are inherited from the device interface in Device.
class USBMS(CLI, Device):

    name           = 'USBMS Base Device Interface'
    description    = _('Communicate with an eBook reader.')
    author         = _('John Schember')
    supported_platforms = ['windows', 'osx', 'linux']

    FORMATS = []
    EBOOK_DIR_MAIN = ''
    EBOOK_DIR_CARD_A = ''
    EBOOK_DIR_CARD_B = ''
    SUPPORTS_SUB_DIRS = False
    CAN_SET_METADATA = False

    def reset(self, key='-1', log_packets=False, report_progress=None):
        Device.reset(self, key=key, log_packets=log_packets,
                        report_progress=report_progress)

    def get_device_information(self, end_session=True):
        """
        Ask device for device information. See L{DeviceInfoQuery}.
        @return: (device name, device version, software version on device, mime type)
        """
        return (self.__class__.__name__, '', '', '')

    def books(self, oncard=None, end_session=True):
        from calibre.ebooks.metadata.meta import path_to_ext
        bl = BookList()

        if oncard == 'carda' and not self._card_a_prefix:
            return bl
        elif oncard == 'cardb' and not self._card_b_prefix:
            return bl
        elif oncard and oncard != 'carda' and oncard != 'cardb':
            return bl

        prefix = self._card_a_prefix if oncard == 'carda' else self._card_b_prefix if oncard == 'cardb' else self._main_prefix
        ebook_dir = self.EBOOK_DIR_CARD_A if oncard == 'carda' else self.EBOOK_DIR_CARD_B if oncard == 'cardb' else self.EBOOK_DIR_MAIN

        # Get all books in the ebook_dir directory
        if self.SUPPORTS_SUB_DIRS:
            for path, dirs, files in os.walk(os.path.join(prefix, ebook_dir)):
                # Filter out anything that isn't in the list of supported ebook types
                for book_type in self.FORMATS:
                    for filename in fnmatch.filter(files, '*.%s' % (book_type)):
                        bl.append(self.__class__.book_from_path(os.path.join(path, filename)))
        else:
            path = os.path.join(prefix, ebook_dir)
            for filename in os.listdir(path):
                if path_to_ext(filename) in self.FORMATS:
                    bl.append(self.__class__.book_from_path(os.path.join(path, filename)))
        return bl

    def _sanity_check(self, on_card, files):
        if on_card == 'carda' and not self._card_a_prefix:
            raise ValueError(_('The reader has no storage card in this slot.'))
        elif on_card == 'cardb' and not self._card_b_prefix:
            raise ValueError(_('The reader has no storage card in this slot.'))
        elif on_card and on_card not in ('carda', 'cardb'):
            raise DeviceError(_('The reader has no storage card in this slot.'))

        if on_card == 'carda':
            path = os.path.join(self._card_a_prefix, self.EBOOK_DIR_CARD_A)
        if on_card == 'cardb':
            path = os.path.join(self._card_b_prefix, self.EBOOK_DIR_CARD_B)
        else:
            path = os.path.join(self._main_prefix, self.EBOOK_DIR_MAIN)

        def get_size(obj):
            if hasattr(obj, 'seek'):
                obj.seek(0, os.SEEK_END)
                size = obj.tell()
                obj.seek(0)
                return size
            return os.path.getsize(obj)

        sizes = [get_size(f) for f in files]
        size = sum(sizes)

        if not on_card and size > self.free_space()[0] - 2*1024*1024:
            raise FreeSpaceError(_("There is insufficient free space in main memory"))
        if on_card == 'carda' and size > self.free_space()[1] - 1024*1024:
            raise FreeSpaceError(_("There is insufficient free space on the storage card"))
        if on_card == 'cardb' and size > self.free_space()[2] - 1024*1024:
            raise FreeSpaceError(_("There is insufficient free space on the storage card"))
        return path

    def upload_books(self, files, names, on_card=False, end_session=True,
                     metadata=None):

        path = self._sanity_check(on_card, files)

        paths = []
        names = iter(names)
        metadata = iter(metadata)

        for infile in files:
            newpath = path

            if self.SUPPORTS_SUB_DIRS:
                mdata = metadata.next()

                if 'tags' in mdata.keys():
                    for tag in mdata['tags']:
                        if tag.startswith(_('News')):
                            newpath = os.path.join(newpath, 'news')
                            newpath = os.path.join(newpath, mdata.get('title', ''))
                            newpath = os.path.join(newpath, mdata.get('timestamp', ''))
                            break
                        elif tag.startswith('/'):
                            newpath = path
                            newpath += tag
                            newpath = os.path.normpath(newpath)
                            break

                if newpath == path:
                    newpath = os.path.join(newpath, mdata.get('authors', _('Unknown')))
                    newpath = os.path.join(newpath, mdata.get('title', _('Unknown')))

            if not os.path.exists(newpath):
                os.makedirs(newpath)

            filepath = os.path.join(newpath, names.next())
            paths.append(filepath)

            if hasattr(infile, 'read'):
                infile.seek(0)

                dest = open(filepath, 'wb')
                shutil.copyfileobj(infile, dest, 10*1024*1024)

                dest.flush()
                dest.close()
            else:
                shutil.copy2(infile, filepath)

        return zip(paths, cycle([on_card]))

    @classmethod
    def add_books_to_metadata(cls, locations, metadata, booklists):
        for location in locations:
            path = location[0]
            blist = 2 if location[1] == 'cardb' else 1 if location[1] == 'carda' else 0

            book = cls.book_from_path(path)

            if not book in booklists[blist]:
                booklists[blist].append(book)


    def delete_books(self, paths, end_session=True):
        for path in paths:
            if os.path.exists(path):
                # Delete the ebook
                os.unlink(path)
                if self.SUPPORTS_SUB_DIRS:
                    try:
                        os.removedirs(os.path.dirname(path))
                    except:
                        pass

    @classmethod
    def remove_books_from_metadata(cls, paths, booklists):
        for path in paths:
            for bl in booklists:
                for book in bl:
                    if path.endswith(book.path):
                        bl.remove(book)

    def sync_booklists(self, booklists, end_session=True):
        # There is no meta data on the device to update. The device is treated
        # as a mass storage device and does not use a meta data xml file like
        # the Sony Readers.
        pass

    @classmethod
    def metadata_from_path(cls, path):
        from calibre.ebooks.metadata.meta import metadata_from_formats
        return metadata_from_formats([path])

    @classmethod
    def book_from_path(cls, path):
        from calibre.ebooks.metadata.meta import path_to_ext
        fileext = path_to_ext(path)
        mi = cls.metadata_from_path(path)
        mime = mime_type_ext(fileext)
        authors = authors_to_string(mi.authors)

        book = Book(path, mi.title, authors, mime)
        return book

