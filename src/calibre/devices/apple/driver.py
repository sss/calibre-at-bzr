# -*- coding: utf-8 -*-

__license__   = 'GPL v3'
__copyright__ = '2010, Gregory Riker'
__docformat__ = 'restructuredtext en'


import cStringIO, ctypes, datetime, os, re, shutil, subprocess, sys, tempfile, time
from calibre.constants import __appname__, __version__, DEBUG
from calibre import fit_image
from calibre.constants import isosx, iswindows
from calibre.devices.errors import UserFeedback
from calibre.devices.usbms.deviceconfig import DeviceConfig
from calibre.devices.interface import DevicePlugin
from calibre.ebooks.BeautifulSoup import BeautifulSoup
from calibre.ebooks.metadata import MetaInformation
from calibre.ebooks.metadata.epub import set_metadata
from calibre.library.server.utils import strftime
from calibre.utils.config import config_dir
from calibre.utils.date import isoformat, now, parse_date
from calibre.utils.localization import get_lang
from calibre.utils.logging import Log
from calibre.utils.zipfile import ZipFile

from PIL import Image as PILImage

if isosx:
    try:
        import appscript
        appscript
    except:
        # appscript fails to load on 10.4
        appscript = None

if iswindows:
    import pythoncom, win32com.client

class DriverBase(DeviceConfig, DevicePlugin):
    # Needed for config_widget to work
    FORMATS = ['epub', 'pdf']

    @classmethod
    def _config_base_name(cls):
        return 'iTunes'

class ITUNES(DriverBase):
    '''
    Calling sequences:
    Initialization:
        can_handle() or can_handle_windows()
        reset()
        open()
        card_prefix()
        can_handle()
        set_progress_reporter()
        get_device_information()
        card_prefix()
        free_space()
        (Job 1 Get device information finishes)
        can_handle()
        set_progress_reporter()
        books() (once for each storage point)
        settings()
        settings()
        can_handle() (~1x per second OSX while idle)
    Delete:
        delete_books()
        remove_books_from_metadata()
        sync_booklists()
        card_prefix()
        free_space()
    Upload:
        settings()
        set_progress_reporter()
        upload_books()
        add_books_to_metadata()
        set_progress_reporter()
        sync_booklists()
        card_prefix()
        free_space()
    '''

    name = 'Apple device interface'
    gui_name = 'Apple device'
    icon = I('devices/ipad.png')
    description    = _('Communicate with iBooks through iTunes.')
    supported_platforms = ['osx','windows']
    author = 'GRiker'
    #: The version of this plugin as a 3-tuple (major, minor, revision)
    version        = (0,8,0)

    OPEN_FEEDBACK_MESSAGE = _(
        'Apple device detected, launching iTunes, please wait ...')


    # Product IDs:
    #  0x1291   iPod Touch
    #  0x1292   iPhone 3G
    #  0x????   iPhone 3GS
    #  0x129a   iPad
    #  0x????   iPhone 4
    VENDOR_ID = [0x05ac]
    PRODUCT_ID = [0x1291,0x1292,0x129a]
    BCD = [0x01]

    # iTunes enumerations
    Sources = [
                'Unknown',
                'Library',
                'iPod',
                'AudioCD',
                'MP3CD',
                'Device',
                'RadioTuner',
                'SharedLibrary']

    ArtworkFormat = [
                'Unknown',
                'JPEG',
                'PNG',
                'BMP'
                ]

    PlaylistKind = [
                'Unknown',
                'Library',
                'User',
                'CD',
                'Device',
                'Radio Tuner'
                ]

    PlaylistSpecialKind = [
                'Unknown',
                'Purchased Music',
                'Party Shuffle',
                'Podcasts',
                'Folder',
                'Video',
                'Music',
                'Movies',
                'TV Shows',
                'Books',
                ]

    SearchField = [
                'All',
                'Visible',
                'Artists',
                'Albums',
                'Composers',
                'SongNames',
                ]

    # Cover art size limits
    MAX_COVER_WIDTH = 510
    MAX_COVER_HEIGHT = 680

    # Properties
    cached_books = {}
    cache_dir = os.path.join(config_dir, 'caches', 'itunes')
    description_prefix = "added by calibre"
    ejected = False
    iTunes= None
    iTunes_media = None
    library_orphans = None
    log = Log()
    manual_sync_mode = False
    path_template = 'iTunes/%s - %s.epub'
    problem_titles = []
    problem_msg = None
    report_progress = None
    update_list = []
    sources = None
    update_msg = None
    update_needed = False

    # Public methods
    def add_books_to_metadata(self, locations, metadata, booklists):
        '''
        Add locations to the booklists. This function must not communicate with
        the device.
        @param locations: Result of a call to L{upload_books}
        @param metadata: List of MetaInformation objects, same as for
        :method:`upload_books`.
        @param booklists: A tuple containing the result of calls to
                                (L{books}(oncard=None), L{books}(oncard='carda'),
                                L{books}(oncard='cardb')).
        '''
        if DEBUG:
            self.log.info("ITUNES.add_books_to_metadata()")

        task_count = float(len(self.update_list))

        # Delete any obsolete copies of the book from the booklist
        if self.update_list:
            if False:
                self._dump_booklist(booklists[0], header='before',indent=2)
                self._dump_update_list(header='before',indent=2)
                self._dump_cached_books(header='before',indent=2)

            for (j,p_book) in enumerate(self.update_list):
                if False:
                    if isosx:
                        self.log.info("  looking for %s" %
                            str(p_book['lib_book'])[-9:])
                    elif iswindows:
                        self.log.info(" looking for '%s' by %s (%s)" %
                                        (p_book['title'],p_book['author'], p_book['uuid']))

                # Purge the booklist, self.cached_books
                for i,bl_book in enumerate(booklists[0]):
                    if bl_book.uuid == p_book['uuid']:
                        # Remove from booklists[0]
                        booklists[0].pop(i)
                        if False:
                            if isosx:
                                self.log.info("  removing old %s %s from booklists[0]" %
                                    (p_book['title'], str(p_book['lib_book'])[-9:]))
                            elif iswindows:
                                self.log.info(" removing old '%s' from booklists[0]" %
                                                (p_book['title']))

                        # If >1 matching uuid, remove old title
                        matching_uuids = 0
                        for cb in self.cached_books:
                            if self.cached_books[cb]['uuid'] == p_book['uuid']:
                                matching_uuids += 1

                        if matching_uuids > 1:
                            for cb in self.cached_books:
                                if self.cached_books[cb]['uuid'] == p_book['uuid']:
                                    if self.cached_books[cb]['title'] == p_book['title'] and \
                                       self.cached_books[cb]['author'] == p_book['author']:
                                        if DEBUG:
                                            self._dump_cached_book(self.cached_books[cb],header="removing from self.cached_books:", indent=2)
                                        self.cached_books.pop(cb)
                                        break
                            break
                if self.report_progress is not None:
                    self.report_progress(j+1/task_count, _('Updating device metadata listing...'))

            if self.report_progress is not None:
                self.report_progress(1.0, _('Updating device metadata listing...'))

        # Add new books to booklists[0]
        for new_book in locations[0]:
            if DEBUG:
                self.log.info("  adding '%s' by '%s' to booklists[0]" %
                    (new_book.title, new_book.author))
            booklists[0].append(new_book)

        if DEBUG:
            self._dump_booklist(booklists[0],header='after',indent=2)
            self._dump_cached_books(header='after',indent=2)

    def books(self, oncard=None, end_session=True):
        """
        Return a list of ebooks on the device.
        @param oncard:  If 'carda' or 'cardb' return a list of ebooks on the
                        specific storage card, otherwise return list of ebooks
                        in main memory of device. If a card is specified and no
                        books are on the card return empty list.
        @return: A BookList.

        Implementation notes:
        iTunes does not sync purchased books, they are only on the device.  They are visible, but
        they are not backed up to iTunes.  Since calibre can't manage them, don't show them in the
        list of device books.

        """
        if not oncard:
            if DEBUG:
                self.log.info("ITUNES:books(oncard=%s)" % oncard)

            # Fetch a list of books from iPod device connected to iTunes


            if 'iPod' in self.sources:
                booklist = BookList(self.log)
                cached_books = {}

                if isosx:
                    library_books = self._get_library_books()
                    device_books = self._get_device_books()
                    book_count = float(len(device_books))
                    for (i,book) in enumerate(device_books):
                        this_book = Book(book.name(), book.artist())
                        this_book.path = self.path_template % (book.name(), book.artist())
                        try:
                            this_book.datetime = parse_date(str(book.date_added())).timetuple()
                        except:
                            pass
                        this_book.db_id = None
                        this_book.device_collections = []
                        this_book.library_id = library_books[this_book.path] if this_book.path in library_books else None
                        this_book.size = book.size()
                        this_book.uuid = book.album()
                        # Hack to discover if we're running in GUI environment
                        if self.report_progress is not None:
                            this_book.thumbnail = self._generate_thumbnail(this_book.path, book)
                        else:
                            this_book.thumbnail = None
                        booklist.add_book(this_book, False)

                        cached_books[this_book.path] = {
                         'title':book.name(),
                         'author':[book.artist()],
                         'lib_book':library_books[this_book.path] if this_book.path in library_books else None,
                         'dev_book':book,
                         'uuid': book.composer()
                         }

                        if self.report_progress is not None:
                            self.report_progress(i+1/book_count, _('%d of %d') % (i+1, book_count))
                    self._purge_orphans(library_books, cached_books)

                elif iswindows:
                    try:
                        pythoncom.CoInitialize()
                        self.iTunes = win32com.client.Dispatch("iTunes.Application")
                        library_books = self._get_library_books()
                        device_books = self._get_device_books()
                        book_count = float(len(device_books))
                        for (i,book) in enumerate(device_books):
                            this_book = Book(book.Name, book.Artist)
                            this_book.path = self.path_template % (book.Name, book.Artist)
                            try:
                                this_book.datetime = parse_date(str(book.DateAdded)).timetuple()
                            except:
                                pass
                            this_book.db_id = None
                            this_book.device_collections = []
                            this_book.library_id = library_books[this_book.path] if this_book.path in library_books else None
                            this_book.size = book.Size
                            # Hack to discover if we're running in GUI environment
                            if self.report_progress is not None:
                                this_book.thumbnail = self._generate_thumbnail(this_book.path, book)
                            else:
                                this_book.thumbnail = None
                            booklist.add_book(this_book, False)

                            cached_books[this_book.path] = {
                             'title':book.Name,
                             'author':book.Artist,
                             'lib_book':library_books[this_book.path] if this_book.path in library_books else None,
                             'uuid': book.Composer,
                             'format': 'pdf' if book.KindAsString.startswith('PDF') else 'epub'
                             }

                            if self.report_progress is not None:
                                self.report_progress(i+1/book_count,
                                        _('%d of %d') % (i+1, book_count))
                        self._purge_orphans(library_books, cached_books)

                    finally:
                        pythoncom.CoUninitialize()

                if self.report_progress is not None:
                    self.report_progress(1.0, _('finished'))
                self.cached_books = cached_books
                if DEBUG:
                    self._dump_booklist(booklist, 'returning from books()', indent=2)
                    self._dump_cached_books('returning from books()',indent=2)
                return booklist
        else:
            return []

    def can_handle(self, device_info, debug=False):
        '''
        Unix version of :method:`can_handle_windows`

        :param device_info: Is a tupe of (vid, pid, bcd, manufacturer, product,
        serial number)

        Confirm that:
            - iTunes is running
            - there is an iPod-type device connected
        This gets called first when the device fingerprint is read, so it needs to
        instantiate iTunes if necessary
        This gets called ~1x/second while device fingerprint is sensed
        '''
        if appscript is None:
            return False

        if self.iTunes:
            # Check for connected book-capable device
            self.sources = self._get_sources()
            if 'iPod' in self.sources:
                #if DEBUG:
                    #sys.stdout.write('.')
                    #sys.stdout.flush()
                return True
            else:
                if DEBUG:
                    sys.stdout.write('-')
                    sys.stdout.flush()
                return False
        else:
            # Called at entry
            # We need to know if iTunes sees the iPad
            # It may have been ejected
            if DEBUG:
                self.log.info("ITUNES.can_handle()")

            self._launch_iTunes()
            self.sources = self._get_sources()
            if (not 'iPod' in self.sources) or (self.sources['iPod'] == ''):
                attempts = 9
                while attempts:
                    # If iTunes was just launched, device may not be detected yet
                    self.sources = self._get_sources()
                    if (not 'iPod' in self.sources) or (self.sources['iPod'] == ''):
                        attempts -= 1
                        time.sleep(0.5)
                        if DEBUG:
                            self.log.warning(" waiting for connected iPad, attempt #%d" % (10 - attempts))
                    else:
                        if DEBUG:
                            self.log.info(' found connected iPad')
                        break
                else:
                    # iTunes running, but not connected iPad
                    if DEBUG:
                        self.log.info(' self.ejected = True')
                    self.ejected = True
                    return False

            self._discover_manual_sync_mode(wait = 2 if self.initial_status == 'launched' else 0)
            return True

    def can_handle_windows(self, device_id, debug=False):
        '''
        Optional method to perform further checks on a device to see if this driver
        is capable of handling it. If it is not it should return False. This method
        is only called after the vendor, product ids and the bcd have matched, so
        it can do some relatively time intensive checks. The default implementation
        returns True. This method is called only on windows. See also
        :method:`can_handle`.

        :param device_info: On windows a device ID string. On Unix a tuple of
        ``(vendor_id, product_id, bcd)``.

        iPad implementation notes:
        It is necessary to use this method to check for the presence of a connected
        iPad, as we have to return True if we can handle device interaction, or False if not.

        '''
        if self.iTunes:
            # We've previously run, so the user probably ejected the device
            try:
                pythoncom.CoInitialize()
                self.sources = self._get_sources()
                if 'iPod' in self.sources:
                    if DEBUG:
                        sys.stdout.write('.')
                        sys.stdout.flush()
                    if DEBUG:
                        self.log.info('ITUNES.can_handle_windows:\n confirming connected iPad')
                    self.ejected = False
                    self._discover_manual_sync_mode()
                    return True
                else:
                    if DEBUG:
                        self.log.info("ITUNES.can_handle_windows():\n device ejected")
                    self.ejected = True
                    return False
            except:
                # iTunes connection failed, probably not running anymore

                self.log.error("ITUNES.can_handle_windows():\n lost connection to iTunes")
                return False
            finally:
                pythoncom.CoUninitialize()

        else:
            if DEBUG:
                self.log.info("ITUNES:can_handle_windows():\n Launching iTunes")

            try:
                pythoncom.CoInitialize()
                self._launch_iTunes()
                self.sources = self._get_sources()
                if (not 'iPod' in self.sources) or (self.sources['iPod'] == ''):
                    attempts = 9
                    while attempts:
                        # If iTunes was just launched, device may not be detected yet
                        self.sources = self._get_sources()
                        if (not 'iPod' in self.sources) or (self.sources['iPod'] == ''):
                            attempts -= 1
                            time.sleep(0.5)
                            if DEBUG:
                                self.log.warning(" waiting for connected iPad, attempt #%d" % (10 - attempts))
                        else:
                            if DEBUG:
                                self.log.info(' found connected iPad in iTunes')
                            break
                    else:
                        # iTunes running, but not connected iPad
                        if DEBUG:
                            self.log.info(' iDevice has been ejected')
                        self.ejected = True
                        return False

                self.log.info(' found connected iPad in sources')
                self._discover_manual_sync_mode(wait=1.0)

            finally:
                pythoncom.CoUninitialize()

            return True

    def card_prefix(self, end_session=True):
        '''
        Return a 2 element list of the prefix to paths on the cards.
        If no card is present None is set for the card's prefix.
        E.G.
        ('/place', '/place2')
        (None, 'place2')
        ('place', None)
        (None, None)
        '''
        return (None,None)

    @classmethod
    def config_widget(cls):
        '''
        Return a QWidget with settings for the device interface
        '''
        cw = DriverBase.config_widget()
        # Turn off the Save template
        cw.opt_save_template.setVisible(False)
        cw.label.setVisible(False)
        # Repurpose the checkbox
        cw.opt_read_metadata.setText(_("Use Series as Category in iTunes/iBooks"))
        return cw

    def delete_books(self, paths, end_session=True):
        '''
        Delete books at paths on device.
        iTunes doesn't let us directly delete a book on the device.
        If the requested paths are deletable (i.e., it's in the Library|Books list),
        delete the paths from the library, then resync iPad

        '''
        self.problem_titles = []
        self.problem_msg = _("Some books not found in iTunes database.\n"
                              "Delete using the iBooks app.\n"
                              "Click 'Show Details' for a list.")
        self.log.info("ITUNES:delete_books()")
        for path in paths:
            if self.cached_books[path]['lib_book']:
                if DEBUG:
                    self.log.info(" Deleting '%s' from iTunes library" % (path))

                if isosx:
                    self._remove_from_iTunes(self.cached_books[path])
                    if self.manual_sync_mode:
                        self._remove_from_device(self.cached_books[path])
                elif iswindows:
                    try:
                        pythoncom.CoInitialize()
                        self.iTunes = win32com.client.Dispatch("iTunes.Application")
                        self._remove_from_iTunes(self.cached_books[path])
                        if self.manual_sync_mode:
                            self._remove_from_device(self.cached_books[path])
                    finally:
                        pythoncom.CoUninitialize()

                if not self.manual_sync_mode:
                    self.update_needed = True
                    self.update_msg = "Deleted books from device"
                else:
                    self.log.info(" skipping sync phase, manual_sync_mode: True")
            else:
                if self.manual_sync_mode:
                    metadata = MetaInformation(self.cached_books[path]['title'],
                                               [self.cached_books[path]['author']])
                    metadata.uuid = self.cached_books[path]['uuid']

                    if isosx:
                        self._remove_existing_copy(self.cached_books[path],metadata)
                    elif iswindows:
                        try:
                            pythoncom.CoInitialize()
                            self.iTunes = win32com.client.Dispatch("iTunes.Application")
                            self._remove_existing_copy(self.cached_books[path],metadata)
                        finally:
                            pythoncom.CoUninitialize()

                else:
                    self.problem_titles.append("'%s' by %s" %
                     (self.cached_books[path]['title'],self.cached_books[path]['author']))

    def eject(self):
        '''
        Un-mount / eject the device from the OS. This does not check if there
        are pending GUI jobs that need to communicate with the device.
        '''
        if DEBUG:
            self.log.info("ITUNES:eject(): ejecting '%s'" % self.sources['iPod'])
        if isosx:
            self.iTunes.eject(self.sources['iPod'])
        elif iswindows:
            if 'iPod' in self.sources:
                try:
                    pythoncom.CoInitialize()
                    self.iTunes = win32com.client.Dispatch("iTunes.Application")
                    self.iTunes.sources.ItemByName(self.sources['iPod']).EjectIPod()

                finally:
                    pythoncom.CoUninitialize()

        self.iTunes = None
        self.sources = None

    def free_space(self, end_session=True):
        """
        Get free space available on the mountpoints:
          1. Main memory
          2. Card A
          3. Card B

        @return: A 3 element list with free space in bytes of (1, 2, 3). If a
        particular device doesn't have any of these locations it should return -1.

        In Windows, a sync-in-progress blocks this call until sync is complete
        """
        if DEBUG:
            self.log.info("ITUNES:free_space()")

        free_space = 0
        if isosx:
            if 'iPod' in self.sources:
                connected_device = self.sources['iPod']
                free_space = self.iTunes.sources[connected_device].free_space()

        elif iswindows:
            if 'iPod' in self.sources:

                while True:
                    try:
                        try:
                            pythoncom.CoInitialize()
                            self.iTunes = win32com.client.Dispatch("iTunes.Application")
                            connected_device = self.sources['iPod']
                            free_space = self.iTunes.sources.ItemByName(connected_device).FreeSpace
                        finally:
                            pythoncom.CoUninitialize()
                            break
                    except:
                        self.log.error(' waiting for free_space() call to go through')

        return (free_space,-1,-1)

    def get_device_information(self, end_session=True):
        """
        Ask device for device information. See L{DeviceInfoQuery}.
        @return: (device name, device version, software version on device, mime type)
        """
        if DEBUG:
            self.log.info("ITUNES:get_device_information()")

        return ('iDevice','hw v1.0','sw v1.0', 'mime type normally goes here')

    def get_file(self, path, outfile, end_session=True):
        '''
        Read the file at C{path} on the device and write it to outfile.
        @param outfile: file object like C{sys.stdout} or the result of an C{open} call
        '''
        if DEBUG:
            self.log.info("ITUNES.get_file(): exporting '%s'" % path)
        outfile.write(open(self.cached_books[path]['lib_book'].location().path).read())

    def open(self):
        '''
        Perform any device specific initialization. Called after the device is
        detected but before any other functions that communicate with the device.
        For example: For devices that present themselves as USB Mass storage
        devices, this method would be responsible for mounting the device or
        if the device has been automounted, for finding out where it has been
        mounted. The base class within USBMS device.py has a implementation of
        this function that should serve as a good example for USB Mass storage
        devices.

        Note that most of the initialization is necessarily performed in can_handle(), as
        we need to talk to iTunes to discover if there's a connected iPod
        '''
        if DEBUG:
            self.log.info("ITUNES.open()")

        # Confirm/create thumbs archive
        archive_path = os.path.join(self.cache_dir, "thumbs.zip")

        if not os.path.exists(self.cache_dir):
            if DEBUG:
                self.log.info(" creating thumb cache '%s'" % self.cache_dir)
            os.makedirs(self.cache_dir)

        if not os.path.exists(archive_path):
            self.log.info(" creating zip archive")
            zfw = ZipFile(archive_path, mode='w')
            zfw.writestr("iTunes Thumbs Archive",'')
            zfw.close()
        else:
            if DEBUG:
                self.log.info(" existing thumb cache at '%s'" % archive_path)

    def remove_books_from_metadata(self, paths, booklists):
        '''
        Remove books from the metadata list. This function must not communicate
        with the device.
        @param paths: paths to books on the device.
        @param booklists:  A tuple containing the result of calls to
                                (L{books}(oncard=None), L{books}(oncard='carda'),
                                L{books}(oncard='cardb')).

        NB: This will not find books that were added by a different installation of calibre
            as uuids are different
        '''
        if DEBUG:
            self.log.info("ITUNES.remove_books_from_metadata()")
        for path in paths:
            self._dump_cached_book(self.cached_books[path], indent=2)

            # Purge the booklist, self.cached_books
            for i,bl_book in enumerate(booklists[0]):
                if False:
                    self.log.info(" evaluating '%s'" % bl_book.uuid)
                if bl_book.uuid == self.cached_books[path]['uuid']:
                    # Remove from booklists[0]
                    booklists[0].pop(i)

                    for cb in self.cached_books:
                        if self.cached_books[cb]['uuid'] == self.cached_books[path]['uuid']:
                            self.cached_books.pop(cb)
                            break
                    break

        if False:
            self._dump_booklist(booklists[0], indent = 2)
            self._dump_cached_books(indent=2)

    def reset(self, key='-1', log_packets=False, report_progress=None,
            detected_device=None) :
        """
        :key: The key to unlock the device
        :log_packets: If true the packet stream to/from the device is logged
        :report_progress: Function that is called with a % progress
                                (number between 0 and 100) for various tasks
                                If it is called with -1 that means that the
                                task does not have any progress information
        :detected_device: Device information from the device scanner
        """
        if DEBUG:
            self.log.info("ITUNES.reset()")

    def set_progress_reporter(self, report_progress):
        '''
        @param report_progress: Function that is called with a % progress
                                (number between 0 and 100) for various tasks
                                If it is called with -1 that means that the
                                task does not have any progress information
        '''
        self.report_progress = report_progress

    def sync_booklists(self, booklists, end_session=True):
        '''
        Update metadata on device.
        @param booklists: A tuple containing the result of calls to
                                (L{books}(oncard=None), L{books}(oncard='carda'),
                                L{books}(oncard='cardb')).
        '''

        if DEBUG:
            self.log.info("ITUNES.sync_booklists()")

        if self.update_needed:
            if DEBUG:
                self.log.info(' calling _update_device')
            self._update_device(msg=self.update_msg, wait=False)
            self.update_needed = False

        # Inform user of any problem books
        if self.problem_titles:
            raise UserFeedback(self.problem_msg,
                                  details='\n'.join(self.problem_titles), level=UserFeedback.WARN)
        self.problem_titles = []
        self.problem_msg = None
        self.update_list = []

    def total_space(self, end_session=True):
        """
        Get total space available on the mountpoints:
            1. Main memory
            2. Memory Card A
            3. Memory Card B

        @return: A 3 element list with total space in bytes of (1, 2, 3). If a
        particular device doesn't have any of these locations it should return 0.
        """
        if DEBUG:
            self.log.info("ITUNES:total_space()")
        capacity = 0
        if isosx:
            if 'iPod' in self.sources:
                connected_device = self.sources['iPod']
                capacity = self.iTunes.sources[connected_device].capacity()

        return (capacity,-1,-1)

    def upload_books(self, files, names, on_card=None, end_session=True,
                     metadata=None):
        '''
        Upload a list of books to the device. If a file already
        exists on the device, it should be replaced.
        This method should raise a L{FreeSpaceError} if there is not enough
        free space on the device. The text of the FreeSpaceError must contain the
        word "card" if C{on_card} is not None otherwise it must contain the word "memory".
        :files: A list of paths and/or file-like objects.
        :names: A list of file names that the books should have
        once uploaded to the device. len(names) == len(files)
        :return: A list of 3-element tuples. The list is meant to be passed
        to L{add_books_to_metadata}.
        :metadata: If not None, it is a list of :class:`MetaInformation` objects.
        The idea is to use the metadata to determine where on the device to
        put the book. len(metadata) == len(files). Apart from the regular
        cover (path to cover), there may also be a thumbnail attribute, which should
        be used in preference. The thumbnail attribute is of the form
        (width, height, cover_data as jpeg).
        '''

        new_booklist = []
        self.update_list = []
        file_count = float(len(files))
        self.problem_titles = []
        self.problem_msg = _("Some cover art could not be converted.\n"
                                     "Click 'Show Details' for a list.")

        if DEBUG:
            self.log.info("ITUNES.upload_books()")
            self._dump_files(files, header='upload_books()',indent=2)
            self._dump_update_list(header='upload_books()',indent=2)
            #self.log.info("  self.settings().format_map: %s" % self.settings().format_map)

        if isosx:
            for (i,file) in enumerate(files):
                format = file.rpartition('.')[2].lower()
                path = self.path_template % (metadata[i].title, metadata[i].author[0])
                self._remove_existing_copy(path, metadata[i])
                fpath = self._get_fpath(file, metadata[i], format, update_md=True)
                db_added, lb_added = self._add_new_copy(fpath, metadata[i])
                thumb = self._cover_to_thumb(path, metadata[i], db_added, lb_added, format)
                this_book = self._create_new_book(fpath, metadata[i], path, db_added, lb_added, thumb, format)
                new_booklist.append(this_book)
                self._update_iTunes_metadata(metadata[i], db_added, lb_added, this_book)

                # Add new_book to self.cached_paths
                self.cached_books[this_book.path] = {
                   'author': metadata[i].author,
                 'dev_book': db_added,
                   'format': format,
                 'lib_book': lb_added,
                    'title': metadata[i].title,
                     'uuid': metadata[i].uuid }


                # Report progress
                if self.report_progress is not None:
                    self.report_progress(i+1/file_count, _('%d of %d') % (i+1, file_count))

        elif iswindows:
            try:
                pythoncom.CoInitialize()
                self.iTunes = win32com.client.Dispatch("iTunes.Application")

                for (i,file) in enumerate(files):
                    format = file.rpartition('.')[2].lower()
                    path = self.path_template % (metadata[i].title, metadata[i].author[0])
                    self._remove_existing_copy(path, metadata[i])
                    fpath = self._get_fpath(file, metadata[i],format, update_md=True)
                    db_added, lb_added = self._add_new_copy(fpath, metadata[i])

                    if self.manual_sync_mode and not db_added:
                        # Problem finding added book, probably title/author change needing to be written to metadata
                        self.problem_msg = ("Title and/or author metadata mismatch with uploaded books.\n"
                                            "Click 'Show Details...' for affected books.")
                        self.problem_titles.append("'%s' by %s" % (metadata[i].title, metadata[i].author[0]))

                    thumb = self._cover_to_thumb(path, metadata[i], db_added, lb_added, format)
                    this_book = self._create_new_book(fpath, metadata[i], path, db_added, lb_added, thumb, format)
                    new_booklist.append(this_book)
                    self._update_iTunes_metadata(metadata[i], db_added, lb_added, this_book)

                    # Add new_book to self.cached_paths
                    self.cached_books[this_book.path] = {
                       'author': metadata[i].author[0],
                     'dev_book': db_added,
                       'format': format,
                     'lib_book': lb_added,
                        'title': metadata[i].title,
                         'uuid': metadata[i].uuid}

                    # Report progress
                    if self.report_progress is not None:
                        self.report_progress(i+1/file_count, _('%d of %d') % (i+1, file_count))
            finally:
                pythoncom.CoUninitialize()

        if self.report_progress is not None:
            self.report_progress(1.0, _('finished'))

        # Tell sync_booklists we need a re-sync
        if not self.manual_sync_mode:
            self.update_needed = True
            self.update_msg = "Added books to device"

        if False:
            self._dump_booklist(new_booklist,header="after upload_books()",indent=2)
            self._dump_cached_books(header="after upload_books()",indent=2)
        return (new_booklist, [], [])


    # Private methods
    def _add_device_book(self,fpath, metadata):
        '''
        assumes pythoncom wrapper for windows
        '''
        self.log.info(" ITUNES._add_device_book()")
        if isosx:
            if 'iPod' in self.sources:
                connected_device = self.sources['iPod']
                device = self.iTunes.sources[connected_device]
                for pl in device.playlists():
                    if pl.special_kind() == appscript.k.Books:
                        break
                else:
                    if DEBUG:
                        self.log.error("  Device|Books playlist not found")

                # Add the passed book to the Device|Books playlist
                added = pl.add(appscript.mactypes.File(fpath),to=pl)
                if False:
                    self.log.info("  '%s' added to Device|Books" % metadata.title)
                return added

        elif iswindows:
            if 'iPod' in self.sources:
                connected_device = self.sources['iPod']
                device = self.iTunes.sources.ItemByName(connected_device)

                db_added = None
                for pl in device.Playlists:
                    if pl.Kind == self.PlaylistKind.index('User') and \
                       pl.SpecialKind == self.PlaylistSpecialKind.index('Books'):
                        break
                else:
                    if DEBUG:
                        self.log.info("  no Books playlist found")

                # Add the passed book to the Device|Books playlist
                if pl:
                    file_s = ctypes.c_char_p(fpath)
                    FileArray = ctypes.c_char_p * 1
                    fa = FileArray(file_s)
                    op_status = pl.AddFiles(fa)

                    if DEBUG:
                        sys.stdout.write("  uploading '%s' to Device|Books ..." % metadata.title)
                        sys.stdout.flush()

                    while op_status.InProgress:
                        time.sleep(0.5)
                        if DEBUG:
                            sys.stdout.write('.')
                            sys.stdout.flush()
                    if DEBUG:
                        sys.stdout.write("\n")
                        sys.stdout.flush()

                    # This doesn't seem to work with Device, just Library
                    if False:
                        if DEBUG:
                            sys.stdout.write("  waiting for handle to added '%s' ..." % metadata.title)
                            sys.stdout.flush()
                        while not op_status.Tracks:
                            time.sleep(0.5)
                            if DEBUG:
                                sys.stdout.write('.')
                                sys.stdout.flush()

                        if DEBUG:
                            print
                        added = op_status.Tracks[0]
                    else:
                        # This approach simply scans Library|Books for the book we just added

                        # Try the calibre metadata first
                        db_added = self._find_device_book(
                                     {'title': metadata.title,
                                     'author': metadata.authors[0],
                                       'uuid': metadata.uuid,
                                     'format': fpath.rpartition('.')[2].lower()})

                    return db_added

    def _add_library_book(self,file, metadata):
        '''
        windows assumes pythoncom wrapper
        '''
        self.log.info(" ITUNES._add_library_book()")
        if isosx:
            added = self.iTunes.add(appscript.mactypes.File(file))

        elif iswindows:
            lib = self.iTunes.LibraryPlaylist
            file_s = ctypes.c_char_p(file)
            FileArray = ctypes.c_char_p * 1
            fa = FileArray(file_s)
            op_status = lib.AddFiles(fa)
            if DEBUG:
                self.log.info("  file added to Library|Books")

            self.log.info("  iTunes adding '%s'" % file)

            if DEBUG:
                sys.stdout.write("  iTunes copying '%s' ..." % metadata.title)
                sys.stdout.flush()

            while op_status.InProgress:
                time.sleep(0.5)
                if DEBUG:
                    sys.stdout.write('.')
                    sys.stdout.flush()
            if DEBUG:
                sys.stdout.write("\n")
                sys.stdout.flush()

            if False:
                if DEBUG:
                    sys.stdout.write("  waiting for handle to added '%s' ..." % metadata.title)
                    sys.stdout.flush()
                while op_status.Tracks is None:
                    time.sleep(0.5)
                    if DEBUG:
                        sys.stdout.write('.')
                        sys.stdout.flush()
                if DEBUG:
                    print
                added = op_status.Tracks[0]
            else:
                # This approach simply scans Library|Books for the book we just added
                added = self._find_library_book(
                    { 'title': metadata.title,
                     'author': metadata.author[0],
                       'uuid': metadata.uuid,
                     'format': file.rpartition('.')[2].lower()})
        return added

    def _add_new_copy(self, fpath, metadata):
        '''
        '''
        if DEBUG:
            self.log.info(" ITUNES._add_new_copy()")

        db_added = None
        lb_added = None

        if self.manual_sync_mode:
            db_added = self._add_device_book(fpath, metadata)
            if not getattr(fpath, 'deleted_after_upload', False):
                lb_added = self._add_library_book(fpath, metadata)
                if lb_added:
                    if DEBUG:
                        self.log.info("  file added to Library|Books for iTunes<->iBooks tracking")
        else:
            lb_added = self._add_library_book(fpath, metadata)
            if DEBUG:
                self.log.info("  file added to Library|Books for pending sync")

        return db_added, lb_added

    def _cover_to_thumb(self, path, metadata, db_added, lb_added, format):
        '''
        assumes pythoncom wrapper for db_added
        as of iTunes 9.2, iBooks 1.1, can't set artwork for PDF files via automation
        '''
        self.log.info(" ITUNES._cover_to_thumb()")

        thumb = None
        if metadata.cover:

            if (format == 'epub'):
                # Pre-shrink cover
                # self.MAX_COVER_WIDTH, self.MAX_COVER_HEIGHT
                try:
                    img = PILImage.open(metadata.cover)
                    width = img.size[0]
                    height = img.size[1]
                    scaled, nwidth, nheight = fit_image(width, height, self.MAX_COVER_WIDTH, self.MAX_COVER_HEIGHT)
                    if scaled:
                        if DEBUG:
                            self.log.info("   '%s' scaled from %sx%s to %sx%s" %
                                          (metadata.cover,width,height,nwidth,nheight))
                        img = img.resize((nwidth, nheight), PILImage.ANTIALIAS)
                        cd = cStringIO.StringIO()
                        img.convert('RGB').save(cd, 'JPEG')
                        cover_data = cd.getvalue()
                        cd.close()
                    else:
                        with open(metadata.cover,'r+b') as cd:
                            cover_data = cd.read()
                except:
                    self.problem_titles.append("'%s' by %s" % (metadata.title, metadata.author[0]))
                    self.log.error("  error scaling '%s' for '%s'" % (metadata.cover,metadata.title))
                    return thumb

                if isosx:
                    if lb_added:
                        lb_added.artworks[1].data_.set(cover_data)

                    if db_added:
                        # The following command generates an error, but the artwork does in fact
                        # get sent to the device.  Seems like a bug in Apple's automation interface
                        try:
                            db_added.artworks[1].data_.set(cover_data)
                        except:
                            if DEBUG:
                                self.log.warning("  iTunes automation interface reported an error"
                                                 " when adding artwork to '%s' on the iDevice" % metadata.title)
                            #import traceback
                            #traceback.print_exc()
                            #from calibre import ipython
                            #ipython(user_ns=locals())
                            pass


                elif iswindows:
                    # Write the data to a real file for Windows iTunes
                    tc = os.path.join(tempfile.gettempdir(), "cover.jpg")
                    with open(tc,'wb') as tmp_cover:
                        tmp_cover.write(cover_data)

                    if lb_added:
                        if lb_added.Artwork.Count:
                            lb_added.Artwork.Item(1).SetArtworkFromFile(tc)
                        else:
                            lb_added.AddArtworkFromFile(tc)

                    if db_added:
                        if db_added.Artwork.Count:
                            db_added.Artwork.Item(1).SetArtworkFromFile(tc)
                        else:
                            db_added.AddArtworkFromFile(tc)

            elif format == 'pdf':
                if DEBUG:
                    self.log.info("   unable to set PDF cover via automation interface")

            try:
                # Resize for thumb
                width = metadata.thumbnail[0]
                height = metadata.thumbnail[1]
                im = PILImage.open(metadata.cover)
                im = im.resize((width, height), PILImage.ANTIALIAS)
                of = cStringIO.StringIO()
                im.convert('RGB').save(of, 'JPEG')
                thumb = of.getvalue()
                of.close()

                # Refresh the thumbnail cache
                if DEBUG:
                    self.log.info( "  refreshing cached thumb for '%s'" % metadata.title)
                archive_path = os.path.join(self.cache_dir, "thumbs.zip")
                zfw = ZipFile(archive_path, mode='a')
                thumb_path = path.rpartition('.')[0] + '.jpg'
                zfw.writestr(thumb_path, thumb)
            except:
                self.problem_titles.append("'%s' by %s" % (metadata.title, metadata.author[0]))
                self.log.error("  error converting '%s' to thumb for '%s'" % (metadata.cover,metadata.title))
            finally:
                zfw.close()

        return thumb

    def _create_new_book(self,fpath, metadata, path, db_added, lb_added, thumb, format):
        '''
        '''
        if DEBUG:
            self.log.info(" ITUNES._create_new_book()")

        this_book = Book(metadata.title, metadata.author[0])

        this_book.db_id = None
        this_book.device_collections = []
        this_book.format = format
        this_book.library_id = lb_added
        this_book.path = path
        this_book.thumbnail = thumb
        this_book.iTunes_id = lb_added
        this_book.uuid = metadata.uuid

        if isosx:
            if lb_added:
                this_book.size = self._get_device_book_size(fpath, lb_added.size())
                try:
                    this_book.datetime = parse_date(str(lb_added.date_added())).timetuple()
                except:
                    this_book.datetime = time.gmtime()
            elif db_added:
                this_book.size = self._get_device_book_size(fpath, db_added.size())
                try:
                    this_book.datetime = parse_date(str(db_added.date_added())).timetuple()
                except:
                    this_book.datetime = time.gmtime()

        elif iswindows:
            if lb_added:
                this_book.size = self._get_device_book_size(fpath, lb_added.Size)
                try:
                    this_book.datetime = parse_date(str(lb_added.DateAdded)).timetuple()
                except:
                    this_book.datetime = time.gmtime()
            elif db_added:
                this_book.size = self._get_device_book_size(fpath, db_added.Size)
                try:
                    this_book.datetime = parse_date(str(db_added.DateAdded)).timetuple()
                except:
                    this_book.datetime = time.gmtime()

        return this_book

    def _delete_iTunesMetadata_plist(self,fpath):
        '''
        Delete the plist file from the file to force recache
        '''
        zf = ZipFile(fpath,'a')
        fnames = zf.namelist()
        pl_name = 'iTunesMetadata.plist'
        try:
            plist = [x for x in fnames if pl_name in x][0]
        except:
            plist = None
        if plist:
            if DEBUG:
                self.log.info("   deleting %s from %s" % (pl_name,fpath))
                zf.delete(pl_name)
        zf.close()

    def _discover_manual_sync_mode(self, wait=0):
        '''
        Assumes pythoncom for windows
        wait is passed when launching iTunes, as it seems to need a moment to come to its senses
        '''
        if DEBUG:
            self.log.info(" ITUNES._discover_manual_sync_mode()")
        if wait:
            time.sleep(wait)
        if isosx:
            connected_device = self.sources['iPod']
            dev_books = None
            device = self.iTunes.sources[connected_device]
            for pl in device.playlists():
                if pl.special_kind() == appscript.k.Books:
                    dev_books = pl.file_tracks()
                    break
            else:
                self.log.error("   book_playlist not found")

            if len(dev_books):
                first_book = dev_books[0]
                if False:
                    self.log.info("  determing manual mode by modifying '%s' by %s" % (first_book.name(), first_book.artist()))
                try:
                    first_book.bpm.set(0)
                    self.manual_sync_mode = True
                except:
                    self.manual_sync_mode = False
            else:
                if DEBUG:
                    self.log.info("   adding tracer to empty Books|Playlist")
                try:
                    added = pl.add(appscript.mactypes.File(P('tracer.epub')),to=pl)
                    time.sleep(0.5)
                    added.delete()
                    self.manual_sync_mode = True
                except:
                    self.manual_sync_mode = False

        elif iswindows:
            connected_device = self.sources['iPod']
            device = self.iTunes.sources.ItemByName(connected_device)

            dev_books = None
            for pl in device.Playlists:
                if pl.Kind == self.PlaylistKind.index('User') and \
                   pl.SpecialKind == self.PlaylistSpecialKind.index('Books'):
                    dev_books = pl.Tracks
                    break

            if dev_books.Count:
                first_book = dev_books.Item(1)
                #if DEBUG:
                    #self.log.info(" determing manual mode by modifying '%s' by %s" % (first_book.Name, first_book.Artist))
                try:
                    first_book.BPM = 0
                    self.manual_sync_mode = True
                except:
                    self.manual_sync_mode = False
            else:
                if DEBUG:
                    self.log.info("   sending tracer to empty Books|Playlist")
                fpath = P('tracer.epub')
                mi = MetaInformation('Tracer',['calibre'])
                try:
                    added = self._add_device_book(fpath,mi)
                    time.sleep(0.5)
                    added.Delete()
                    self.manual_sync_mode = True
                except:
                    self.manual_sync_mode = False

        self.log.info("   iTunes.manual_sync_mode: %s" % self.manual_sync_mode)

    def _dump_booklist(self, booklist, header=None,indent=0):
        '''
        '''
        if header:
            msg = '\n%sbooklist %s:' % (' '*indent,header)
            self.log.info(msg)
            self.log.info('%s%s' % (' '*indent,'-' * len(msg)))

        for book in booklist:
            if isosx:
                self.log.info("%s%-40.40s %-30.30s %-10.10s" %
                 (' '*indent,book.title, book.author, str(book.library_id)[-9:]))
            elif iswindows:
                self.log.info("%s%-40.40s %-30.30s" %
                 (' '*indent,book.title, book.author))
        self.log.info()

    def _dump_cached_book(self, cached_book, header=None,indent=0):
        '''
        '''
        if isosx:
            if header:
                msg = '%s%s' % (' '*indent,header)
                self.log.info(msg)
                self.log.info( "%s%s" % (' '*indent, '-' * len(msg)))
                self.log.info("%s%-40.40s %-30.30s %-10.10s %-10.10s %s" %
                 (' '*indent,
                  'title',
                  'author',
                  'lib_book',
                  'dev_book',
                  'uuid'))
            self.log.info("%s%-40.40s %-30.30s %-10.10s %-10.10s %s" %
             (' '*indent,
              cached_book['title'],
              cached_book['author'],
              str(cached_book['lib_book'])[-9:],
              str(cached_book['dev_book'])[-9:],
              cached_book['uuid']))
        elif iswindows:
            if header:
                msg = '%s%s' % (' '*indent,header)
                self.log.info(msg)
                self.log.info( "%s%s" % (' '*indent, '-' * len(msg)))

            self.log.info("%s%-40.40s %-30.30s %s" %
             (' '*indent,
              cached_book['title'],
              cached_book['author'],
              cached_book['uuid']))

    def _dump_cached_books(self, header=None, indent=0):
        '''
        '''
        if header:
            msg = '\n%sself.cached_books %s:' % (' '*indent,header)
            self.log.info(msg)
            self.log.info( "%s%s" % (' '*indent,'-' * len(msg)))
        if isosx:
            for cb in self.cached_books.keys():
                self.log.info("%s%-40.40s %-30.30s %-10.10s %-10.10s %s" %
                 (' '*indent,
                  self.cached_books[cb]['title'],
                  self.cached_books[cb]['author'],
                  str(self.cached_books[cb]['lib_book'])[-9:],
                  str(self.cached_books[cb]['dev_book'])[-9:],
                  self.cached_books[cb]['uuid']))
        elif iswindows:
            for cb in self.cached_books.keys():
                self.log.info("%s%-40.40s %-30.30s %-4.4s %s" %
                 (' '*indent,
                  self.cached_books[cb]['title'],
                  self.cached_books[cb]['author'],
                  self.cached_books[cb]['format'],
                  self.cached_books[cb]['uuid']))

        self.log.info()

    def _dump_epub_metadata(self, fpath):
        '''
        '''
        self.log.info(" ITUNES.__get_epub_metadata()")
        title = None
        author = None
        timestamp = None
        zf = ZipFile(fpath,'r')
        fnames = zf.namelist()
        opf = [x for x in fnames if '.opf' in x][0]
        if opf:
            opf_raw = cStringIO.StringIO(zf.read(opf))
            soup = BeautifulSoup(opf_raw.getvalue())
            opf_raw.close()
            title = soup.find('dc:title').renderContents()
            author = soup.find('dc:creator').renderContents()
            ts = soup.find('meta',attrs={'name':'calibre:timestamp'})
            if ts:
                # Touch existing calibre timestamp
                timestamp = ts['content']

            if not title or not author:
                if DEBUG:
                    self.log.error("   couldn't extract title/author from %s in %s" % (opf,fpath))
                    self.log.error("   title: %s  author: %s timestamp: %s" % (title, author, timestamp))
        else:
            if DEBUG:
                self.log.error("   can't find .opf in %s" % fpath)
        zf.close()
        return (title, author, timestamp)

    def _dump_files(self, files, header=None,indent=0):
        if header:
            msg = '\n%sfiles passed to %s:' % (' '*indent,header)
            self.log.info(msg)
            self.log.info( "%s%s" % (' '*indent,'-' * len(msg)))
        for file in files:
            if getattr(file, 'orig_file_path', None) is not None:
                self.log.info(" %s%s" % (' '*indent,file.orig_file_path))
            elif getattr(file, 'name', None) is not None:
                self.log.info(" %s%s" % (' '*indent,file.name))
        self.log.info()

    def _dump_hex(self, src, length=16):
        '''
        '''
        FILTER=''.join([(len(repr(chr(x)))==3) and chr(x) or '.' for x in range(256)])
        N=0; result=''
        while src:
           s,src = src[:length],src[length:]
           hexa = ' '.join(["%02X"%ord(x) for x in s])
           s = s.translate(FILTER)
           result += "%04X   %-*s   %s\n" % (N, length*3, hexa, s)
           N+=length
        print result

    def _dump_library_books(self, library_books):
        '''
        '''
        if DEBUG:
            self.log.info("\n library_books:")
        for book in library_books:
            self.log.info("   %s" % book)
        self.log.info()

    def _dump_update_list(self,header=None,indent=0):
        if header:
            msg = '\n%sself.update_list %s' % (' '*indent,header)
            self.log.info(msg)
            self.log.info( "%s%s" % (' '*indent,'-' * len(msg)))

        if isosx:
            for ub in self.update_list:
                self.log.info("%s%-40.40s %-30.30s %-10.10s" %
                 (' '*indent,
                  ub['title'],
                  ub['author'],
                  str(ub['lib_book'])[-9:]))
        elif iswindows:
            for ub in self.update_list:
                self.log.info("%s%-40.40s %-30.30s" %
                 (' '*indent,
                  ub['title'],
                  ub['author']))
        self.log.info()

    def _find_device_book(self, search):
        '''
        Windows-only method to get a handle to device book in the current pythoncom session
        '''
        if iswindows:
            dev_books = self._get_device_books_playlist()
            if DEBUG:
                self.log.info(" ITUNES._find_device_book(uuid)")
                self.log.info("  searching for %s ('%s' by %s)" %
                              (search['uuid'], search['title'], search['author']))
            attempts = 9
            while attempts:
                # Try by uuid - only one hit
                hits = dev_books.Search(search['uuid'],self.SearchField.index('All'))
                if hits:
                    hit = hits[0]
                    self.log.info("   found '%s' by %s (%s)" % (hit.Name, hit.Artist, hit.Composer))
                    return hit

                # Try by author - there could be multiple hits
                hits = dev_books.Search(search['author'],self.SearchField.index('Artists'))
                if hits:
                    for hit in hits:
                        if hit.Name == search['title']:
                            if DEBUG:
                                self.log.info("   found '%s' by %s (%s)" % (hit.Name, hit.Artist, hit.Composer))
                            return hit

                # PDF metadata was rewritten at export as 'safe(title) - safe(author)'
                if search['format'] == 'pdf':
                    title = re.sub(r'[^0-9a-zA-Z ]', '_', search['title'])
                    author = re.sub(r'[^0-9a-zA-Z ]', '_', search['author'])
                    if DEBUG:
                        self.log.info("   searching by name: '%s - %s'" % (title,author))
                    hits = dev_books.Search('%s - %s' % (title,author),
                                             self.SearchField.index('All'))
                    if hits:
                        hit = hits[0]
                        self.log.info("   found '%s' by %s (%s)" % (hit.Name, hit.Artist, hit.Composer))
                        return hit
                    else:
                        if DEBUG:
                            self.log.info("   no PDF hits")

                attempts -= 1
                time.sleep(0.5)
                if DEBUG:
                    self.log.warning("  attempt #%d" % (10 - attempts))

            if DEBUG:
                self.log.error("  no hits")
            return None

    def _find_library_book(self, search):
        '''
        Windows-only method to get a handle to a library book in the current pythoncom session
        '''
        if iswindows:
            if DEBUG:
                self.log.info(" ITUNES._find_library_book()")
                if 'uuid' in search:
                    self.log.info("  looking for '%s' by %s (%s)" %
                                (search['title'], search['author'], search['uuid']))
                else:
                    self.log.info("  looking for '%s' by %s" %
                                (search['title'], search['author']))

            for source in self.iTunes.sources:
                if source.Kind == self.Sources.index('Library'):
                    lib = source
                    if DEBUG:
                        self.log.info("  Library source: '%s'  kind: %s" % (lib.Name, self.Sources[lib.Kind]))
                    break
            else:
                if DEBUG:
                    self.log.info("  Library source not found")

            if lib is not None:
                lib_books = None
                for pl in lib.Playlists:
                    if pl.Kind == self.PlaylistKind.index('User') and \
                       pl.SpecialKind == self.PlaylistSpecialKind.index('Books'):
                        if DEBUG:
                            self.log.info("  Books playlist: '%s'" % (pl.Name))
                        lib_books = pl
                        break
                else:
                    if DEBUG:
                        self.log.error("  no Books playlist found")

            attempts = 9
            while attempts:
                # Find book whose Album field = search['uuid']
                if 'uuid' in search:
                    if DEBUG:
                        self.log.info("   searching by uuid '%s' ..." % search['uuid'])
                    hits = lib_books.Search(search['uuid'],self.SearchField.index('All'))
                    if hits:
                        hit = hits[0]
                        if DEBUG:
                            self.log.info("   found '%s' by %s (%s)" % (hit.Name, hit.Artist, hit.Composer))
                        return hit

                if DEBUG:
                    self.log.info("   searching by author '%s' ..." % search['author'])
                hits = lib_books.Search(search['author'],self.SearchField.index('Artists'))
                if hits:
                    for hit in hits:
                        if hit.Name == search['title']:
                            if DEBUG:
                                self.log.info("   found '%s' by %s (%s)" % (hit.Name, hit.Artist, hit.Composer))
                            return hit

                # PDF metadata was rewritten at export as 'safe(title) - safe(author)'
                if search['format'] == 'pdf':
                    title = re.sub(r'[^0-9a-zA-Z ]', '_', search['title'])
                    author = re.sub(r'[^0-9a-zA-Z ]', '_', search['author'])
                    if DEBUG:
                        self.log.info("   searching by name: %s - %s" % (title,author))
                    hits = lib_books.Search('%s - %s' % (title,author),
                                             self.SearchField.index('All'))
                    if hits:
                        hit = hits[0]
                        self.log.info("   found '%s' by %s (%s)" % (hit.Name, hit.Artist, hit.Composer))
                        return hit
                    else:
                        if DEBUG:
                            self.log.info("   no PDF hits")

                attempts -= 1
                time.sleep(0.5)
                if DEBUG:
                    self.log.warning("   attempt #%d" % (10 - attempts))

            if DEBUG:
                self.log.error("  search for '%s' yielded no hits" % search['title'])
            return None

    def _generate_thumbnail(self, book_path, book):
        '''
        Convert iTunes artwork to thumbnail
        Cache generated thumbnails
        cache_dir = os.path.join(config_dir, 'caches', 'itunes')
        as of iTunes 9.2, iBooks 1.1, can't set artwork for PDF files via automation
        '''

        archive_path = os.path.join(self.cache_dir, "thumbs.zip")
        thumb_path = book_path.rpartition('.')[0] + '.jpg'
        format = book_path.rpartition('.')[2].lower()

        try:
            zfr = ZipFile(archive_path)
            thumb_data = zfr.read(thumb_path)
            zfr.close()
        except:
            zfw = ZipFile(archive_path, mode='a')
        else:
            return thumb_data

        self.log.info(" ITUNES._generate_thumbnail()")
        if isosx:
            if format == 'epub':
                try:
                    if False:
                        self.log.info("   fetching artwork from %s\n   %s" % (book_path,book))
                    # Resize the cover
                    data = book.artworks[1].raw_data().data
                    #self._dump_hex(data[:256])
                    img_data = cStringIO.StringIO(data)
                    im = PILImage.open(img_data)
                    scaled, width, height = fit_image(im.size[0],im.size[1], 60, 80)
                    im = im.resize((int(width),int(height)), PILImage.ANTIALIAS)
                    img_data.close()

                    thumb = cStringIO.StringIO()
                    im.convert('RGB').save(thumb,'JPEG')
                    thumb_data = thumb.getvalue()
                    thumb.close()

                    # Cache the tagged thumb
                    if DEBUG:
                        self.log.info("  generated thumb for '%s', caching" % book.name())
                    zfw.writestr(thumb_path, thumb_data)
                    zfw.close()
                    return thumb_data
                except:
                    self.log.error("  error generating thumb for '%s'" % book.name())
                    try:
                        zfw.close()
                    except:
                        pass
                    return None
            else:
                if DEBUG:
                    self.log.info("  unable to generate PDF thumbs")
                return None

        elif iswindows:

            if not book.Artwork.Count:
                if DEBUG:
                    self.log.info("  no artwork available for '%s'" % book.Name)
                return None

            if format == 'epub':
                # Save the cover from iTunes
                try:
                    tmp_thumb = os.path.join(tempfile.gettempdir(), "thumb.%s" % self.ArtworkFormat[book.Artwork.Item(1).Format])
                    book.Artwork.Item(1).SaveArtworkToFile(tmp_thumb)
                    # Resize the cover
                    im = PILImage.open(tmp_thumb)
                    scaled, width, height = fit_image(im.size[0],im.size[1], 60, 80)
                    im = im.resize((int(width),int(height)), PILImage.ANTIALIAS)
                    thumb = cStringIO.StringIO()
                    im.convert('RGB').save(thumb,'JPEG')
                    thumb_data = thumb.getvalue()
                    os.remove(tmp_thumb)
                    thumb.close()

                    # Cache the tagged thumb
                    if DEBUG:
                        self.log.info("  generated thumb for '%s', caching" % book.Name)
                    zfw.writestr(thumb_path, thumb_data)
                    zfw.close()
                    return thumb_data
                except:
                    self.log.error("  error generating thumb for '%s'" % book.Name)
                    try:
                        zfw.close()
                    except:
                        pass
                    return None
            else:
                if DEBUG:
                    self.log.info("  unable to generate PDF thumbs")
                return None

    def _get_device_book_size(self, file, compressed_size):
        '''
        Calculate the exploded size of file
        '''
        exploded_file_size = compressed_size
        format = file.rpartition('.')[2].lower()
        if format == 'epub':
            myZip = ZipFile(file,'r')
            myZipList = myZip.infolist()
            exploded_file_size = 0
            for file in myZipList:
                exploded_file_size += file.file_size
            if False:
                self.log.info(" ITUNES._get_device_book_size()")
                self.log.info("  %d items in archive" % len(myZipList))
                self.log.info("  compressed: %d  exploded: %d" % (compressed_size, exploded_file_size))
            myZip.close()
        return exploded_file_size

    def _get_device_books(self):
        '''
        Assumes pythoncom wrapper for Windows
        '''
        if DEBUG:
            self.log.info("\n ITUNES._get_device_books()")

        device_books = []
        if isosx:
            if 'iPod' in self.sources:
                connected_device = self.sources['iPod']
                device = self.iTunes.sources[connected_device]
                for pl in device.playlists():
                    if pl.special_kind() == appscript.k.Books:
                        if DEBUG:
                            self.log.info("  Book playlist: '%s'" % (pl.name()))
                        books = pl.file_tracks()
                        break
                else:
                    self.log.error("  book_playlist not found")

                for book in books:
                    # This may need additional entries for international iTunes users
                    if book.kind() in ['MPEG audio file']:
                        if DEBUG:
                            self.log.info("   ignoring '%s' of type '%s'" % (book.name(), book.kind()))
                    else:
                        if DEBUG:
                            self.log.info("   %-30.30s %-30.30s %-40.40s [%s]" %
                                          (book.name(), book.artist(), book.album(), book.kind()))
                        device_books.append(book)
                if DEBUG:
                    self.log.info()

        elif iswindows:
            if 'iPod' in self.sources:
                try:
                    pythoncom.CoInitialize()
                    connected_device = self.sources['iPod']
                    device = self.iTunes.sources.ItemByName(connected_device)

                    dev_books = None
                    for pl in device.Playlists:
                        if pl.Kind == self.PlaylistKind.index('User') and \
                           pl.SpecialKind == self.PlaylistSpecialKind.index('Books'):
                            if DEBUG:
                                self.log.info("  Books playlist: '%s'" % (pl.Name))
                            dev_books = pl.Tracks
                            break
                    else:
                        if DEBUG:
                            self.log.info("  no Books playlist found")

                    for book in dev_books:
                        # This may need additional entries for international iTunes users
                        if book.KindAsString in ['MPEG audio file']:
                            if DEBUG:
                                self.log.info("   ignoring '%s' of type '%s'" % (book.Name, book.KindAsString))
                        else:
                            if DEBUG:
                                self.log.info("   %-30.30s %-30.30s %-40.40s [%s]" % (book.Name, book.Artist, book.Album, book.KindAsString))
                            device_books.append(book)
                    if DEBUG:
                        self.log.info()

                finally:
                    pythoncom.CoUninitialize()

        return device_books

    def _get_device_books_playlist(self):
        '''
        assumes pythoncom wrapper
        '''
        if iswindows:
            if 'iPod' in self.sources:
                pl = None
                connected_device = self.sources['iPod']
                device = self.iTunes.sources.ItemByName(connected_device)

                for pl in device.Playlists:
                    if pl.Kind == self.PlaylistKind.index('User') and \
                       pl.SpecialKind == self.PlaylistSpecialKind.index('Books'):
                        break
                else:
                    if DEBUG:
                        self.log.error("  no iPad|Books playlist found")
                return pl

    def _get_fpath(self,file, metadata, format, update_md=False):
        '''
        If the database copy will be deleted after upload, we have to
        use file (the PersistentTemporaryFile), which will be around until
        calibre exits.
        If we're using the database copy, delete the plist
        '''
        if DEBUG:
            self.log.info(" ITUNES._get_fpath()")

        fpath = file
        if not getattr(fpath, 'deleted_after_upload', False):
            if getattr(file, 'orig_file_path', None) is not None:
                # Database copy
                fpath = file.orig_file_path
                self._delete_iTunesMetadata_plist(fpath)
            elif getattr(file, 'name', None) is not None:
                # PTF
                fpath = file.name
        else:
            # Recipe - PTF
            if DEBUG:
                self.log.info("   file will be deleted after upload")

        if format == 'epub' and update_md:
            self._update_epub_metadata(fpath, metadata)

        return fpath

    def _get_library_books(self):
        '''
        Populate a dict of paths from iTunes Library|Books
        Windows assumes pythoncom wrapper
        '''
        if DEBUG:
            self.log.info("\n ITUNES._get_library_books()")

        library_books = {}
        library_orphans = {}
        lib = None

        if isosx:
            for source in self.iTunes.sources():
                if source.kind() == appscript.k.library:
                    lib = source
                    if DEBUG:
                        self.log.info("  Library source: '%s'" % (lib.name()))
                    break
            else:
                if DEBUG:
                    self.log.error('  Library source not found')

            if lib is not None:
                lib_books = None
                if lib.playlists():
                    for pl in lib.playlists():
                        if pl.special_kind() == appscript.k.Books:
                            if DEBUG:
                                self.log.info("  Books playlist: '%s'" % (pl.name()))
                            break
                    else:
                        if DEBUG:
                            self.log.info("  no Library|Books playlist found")

                    lib_books = pl.file_tracks()
                    for book in lib_books:
                        # This may need additional entries for international iTunes users
                        if book.kind() in ['MPEG audio file']:
                            if DEBUG:
                                self.log.info("   ignoring '%s' of type '%s'" % (book.name(), book.kind()))
                        else:
                            # Collect calibre orphans - remnants of recipe uploads
                            path = self.path_template % (book.name(), book.artist())
                            if str(book.description()).startswith(self.description_prefix):
                                if book.location() == appscript.k.missing_value:
                                    library_orphans[path] = book
                                    if False:
                                        self.log.info("   found iTunes PTF '%s' in Library|Books" % book.name())

                            library_books[path] = book
                            if DEBUG:
                                self.log.info("   %-30.30s %-30.30s %-40.40s [%s]" % (book.name(), book.artist(), book.album(), book.kind()))
                else:
                    if DEBUG:
                        self.log.info('  no Library playlists')
            else:
                if DEBUG:
                    self.log.info('  no Library found')

        elif iswindows:
            lib = None
            for source in self.iTunes.sources:
                if source.Kind == self.Sources.index('Library'):
                    lib = source
                    self.log.info("  Library source: '%s' kind: %s" % (lib.Name, self.Sources[lib.Kind]))
                    break
            else:
                self.log.error("  Library source not found")

            if lib is not None:
                lib_books = None
                if lib.Playlists is not None:
                    for pl in lib.Playlists:
                        if pl.Kind == self.PlaylistKind.index('User') and \
                           pl.SpecialKind == self.PlaylistSpecialKind.index('Books'):
                            if DEBUG:
                                self.log.info("  Books playlist: '%s'" % (pl.Name))
                            lib_books = pl.Tracks
                            break
                    else:
                        if DEBUG:
                            self.log.error("  no Library|Books playlist found")
                else:
                    if DEBUG:
                        self.log.error("  no Library playlists found")

                try:
                    for book in lib_books:
                        # This may need additional entries for international iTunes users
                        if book.KindAsString in ['MPEG audio file']:
                            if DEBUG:
                                self.log.info("   ignoring %-30.30s of type '%s'" % (book.Name, book.KindAsString))
                        else:
                            path = self.path_template % (book.Name, book.Artist)

                            # Collect calibre orphans
                            if book.Description.startswith(self.description_prefix):
                                if not book.Location:
                                    library_orphans[path] = book
                                    if False:
                                        self.log.info("   found iTunes PTF '%s' in Library|Books" % book.Name)

                            library_books[path] = book
                            if DEBUG:
                                self.log.info("   %-30.30s %-30.30s %-40.40s [%s]" % (book.Name, book.Artist, book.Album, book.KindAsString))
                except:
                    if DEBUG:
                        self.log.info(" no books in library")
        self.library_orphans = library_orphans
        return library_books

    def _get_purchased_book_ids(self):
        '''
        Return Device|Purchased
        '''
        if 'iPod' in self.sources:
            connected_device = self.sources['iPod']
            if isosx:
                if 'Purchased' in self.iTunes.sources[connected_device].playlists.name():
                    return [pb.database_ID() for pb in self.iTunes.sources[connected_device].playlists['Purchased'].file_tracks()]
                else:
                    return []
            elif iswindows:
                dev = self.iTunes.sources.ItemByName(connected_device)
                if dev.Playlists is not None:
                    dev_playlists = [pl.Name for pl in dev.Playlists]
                    if 'Purchased' in dev_playlists:
                        return self.iTunes.sources.ItemByName(connected_device).Playlists.ItemByName('Purchased').Tracks
                else:
                    return []

    def _get_sources(self):
        '''
        Return a dict of sources
        Check for >1 iPod device connected to iTunes
        '''
        if isosx:
            try:
                names = [s.name() for s in self.iTunes.sources()]
                kinds = [str(s.kind()).rpartition('.')[2] for s in self.iTunes.sources()]
            except:
                # User probably quit iTunes
                return {}
        elif iswindows:
            # Assumes a pythoncom wrapper
            it_sources = ['Unknown','Library','iPod','AudioCD','MP3CD','Device','RadioTuner','SharedLibrary']
            names = [s.name for s in self.iTunes.sources]
            kinds = [it_sources[s.kind] for s in self.iTunes.sources]

        # If more than one connected iDevice, remove all from list to prevent driver initialization
        if kinds.count('iPod') > 1:
            if DEBUG:
                self.log.error("  %d connected iPod devices detected, calibre supports a single connected iDevice" % kinds.count('iPod'))
            while kinds.count('iPod'):
                index = kinds.index('iPod')
                kinds.pop(index)
                names.pop(index)

        return dict(zip(kinds,names))

    def _is_alpha(self,char):
        '''
        '''
        if not re.search('[a-zA-Z]',char):
            return False
        else:
            return True

    def _launch_iTunes(self):
        '''
        '''
        if DEBUG:
            self.log.info(" ITUNES:_launch_iTunes():\n  Instantiating iTunes")

        if isosx:
            '''
            Launch iTunes if not already running
            '''
            # Instantiate iTunes
            running_apps = appscript.app('System Events')
            if not 'iTunes' in running_apps.processes.name():
                if DEBUG:
                    self.log.info( "ITUNES:open(): Launching iTunes" )
                self.iTunes = iTunes= appscript.app('iTunes', hide=True)
                iTunes.run()
                self.initial_status = 'launched'
            else:
                self.iTunes = appscript.app('iTunes')
                self.initial_status = 'already running'

            # Read the current storage path for iTunes media
            cmd = "defaults read com.apple.itunes NSNavLastRootDirectory"
            proc = subprocess.Popen( cmd, shell=True, cwd=os.curdir, stdout=subprocess.PIPE)
            proc.wait()
            media_dir = os.path.expanduser(proc.communicate()[0].strip())
            if os.path.exists(media_dir):
                self.iTunes_media = media_dir
            else:
                self.log.error("  could not confirm valid iTunes.media_dir from %s" % 'com.apple.itunes')
                self.log.error("  media_dir: %s" % media_dir)
            if DEBUG:
                self.log.info("  %s %s" % (__appname__, __version__))
                self.log.info("  [OSX %s - %s (%s), driver version %d.%d.%d]" %
                 (self.iTunes.name(), self.iTunes.version(), self.initial_status,
                  self.version[0],self.version[1],self.version[2]))
                self.log.info("  iTunes_media: %s" % self.iTunes_media)

        if iswindows:
            '''
            Launch iTunes if not already running
            Assumes pythoncom wrapper
            '''
            # Instantiate iTunes
            self.iTunes = win32com.client.Dispatch("iTunes.Application")
            if not DEBUG:
                self.iTunes.Windows[0].Minimized = True
            self.initial_status = 'launched'

            # Read the current storage path for iTunes media from the XML file
            with open(self.iTunes.LibraryXMLPath, 'r') as xml:
                for line in xml:
                    if line.strip().startswith('<key>Music Folder'):
                        soup = BeautifulSoup(line)
                        string = soup.find('string').renderContents()
                        media_dir = os.path.abspath(string[len('file://localhost/'):].replace('%20',' '))
                        break
                if os.path.exists(media_dir):
                    self.iTunes_media = media_dir
                else:
                    self.log.error("  could not extract valid iTunes.media_dir from %s" % self.iTunes.LibraryXMLPath)
                    self.log.error("  %s" % string.parent.prettify())
                    self.log.error("  '%s' not found" % media_dir)

            if DEBUG:
                self.log.info("  %s %s" % (__appname__, __version__))
                self.log.info("  [Windows %s - %s (%s), driver version %d.%d.%d]" %
                 (self.iTunes.Windows[0].name, self.iTunes.Version, self.initial_status,
                  self.version[0],self.version[1],self.version[2]))
                self.log.info("  iTunes_media: %s" % self.iTunes_media)

    def _purge_orphans(self,library_books, cached_books):
        '''
        Scan library_books for any paths not on device
        Remove any iTunes orphans originally added by calibre
        This occurs when the user deletes a book in iBooks while disconnected
        '''
        if DEBUG:
            self.log.info(" ITUNES._purge_orphans()")
            #self._dump_library_books(library_books)
            #self.log.info("  cached_books:\n   %s" % "\n   ".join(cached_books.keys()))

        for book in library_books:
            if isosx:
                if book not in cached_books and \
                   str(library_books[book].description()).startswith(self.description_prefix):
                    if DEBUG:
                        self.log.info("  '%s' not found on iDevice, removing from iTunes" % book)
                    btr = {   'title':library_books[book].name(),
                             'author':library_books[book].artist(),
                           'lib_book':library_books[book]}
                    self._remove_from_iTunes(btr)
            elif iswindows:
                if book not in cached_books and \
                   library_books[book].Description.startswith(self.description_prefix):
                    if DEBUG:
                        self.log.info("  '%s' not found on iDevice, removing from iTunes" % book)
                    btr = {   'title':library_books[book].Name,
                             'author':library_books[book].Artist,
                           'lib_book':library_books[book]}
                    self._remove_from_iTunes(btr)
        if DEBUG:
            self.log.info()

    def _remove_existing_copy(self, path, metadata):
        '''
        '''
        if DEBUG:
            self.log.info(" ITUNES._remove_existing_copy()")

        if self.manual_sync_mode:
            # Delete existing from Device|Books, add to self.update_list
            # for deletion from booklist[0] during add_books_to_metadata
            for book in self.cached_books:
                if self.cached_books[book]['uuid'] == metadata.uuid:
                    self.update_list.append(self.cached_books[book])
                    self._remove_from_device(self.cached_books[book])
                    if DEBUG:
                        self.log.info( "  deleting device book '%s'" % (metadata.title))
                    if not getattr(file, 'deleted_after_upload', False):
                        self._remove_from_iTunes(self.cached_books[book])
                        if DEBUG:
                            self.log.info("  deleting library book '%s'" % metadata.title)
                    break
            else:
                if DEBUG:
                    self.log.info("  '%s' not in cached_books" % metadata.title)
        else:
            # Delete existing from Library|Books, add to self.update_list
            # for deletion from booklist[0] during add_books_to_metadata
            for book in self.cached_books:
                if (self.cached_books[book]['uuid'] == metadata.uuid) or \
                   (self.cached_books[book]['title'] == metadata.title and \
                    self.cached_books[book]['author'] == metadata.authors[0]):
                    self.update_list.append(self.cached_books[book])
                    self._remove_from_iTunes(self.cached_books[book])
                    if DEBUG:
                        self.log.info( "  deleting library book '%s'" %  metadata.title)
                    break
                else:
                    if DEBUG:
                        self.log.info("  '%s' not found in cached_books" % metadata.title)

    def _remove_from_device(self, cached_book):
        '''
        Windows assumes pythoncom wrapper
        '''
        self.log.info(" ITUNES._remove_from_device()")
        if isosx:
            if False:
                self.log.info("  deleting %s" % cached_book['dev_book'])
            cached_book['dev_book'].delete()

        elif iswindows:
            dev_pl = self._get_device_books_playlist()
            hits = dev_pl.Search(cached_book['uuid'],self.SearchField.index('All'))
            if hits:
                hit = hits[0]
                if False:
                    self.log.info("  deleting '%s' by %s (%s)" % (hit.Name, hit.Artist, hit.Album))
                hit.Delete()

    def _remove_from_iTunes(self, cached_book):
        '''
        iTunes does not delete books from storage when removing from database
        We only want to delete stored copies if the file is stored in iTunes
        We don't want to delete files stored outside of iTunes
        '''
        if DEBUG:
            self.log.info(" ITUNES._remove_from_iTunes():")

        if isosx:
            try:
                storage_path = os.path.split(cached_book['lib_book'].location().path)
                if cached_book['lib_book'].location().path.startswith(self.iTunes_media):
                    title_storage_path = storage_path[0]
                    if DEBUG:
                        self.log.info("  removing title_storage_path: %s" % title_storage_path)
                    try:
                        shutil.rmtree(title_storage_path)
                    except:
                        self.log.info("  '%s' not empty" % title_storage_path)

                    # Clean up title/author directories
                    author_storage_path = os.path.split(title_storage_path)[0]
                    self.log.info("  author_storage_path: %s" % author_storage_path)
                    author_files = os.listdir(author_storage_path)
                    if '.DS_Store' in author_files:
                        author_files.pop(author_files.index('.DS_Store'))
                    if not author_files:
                        shutil.rmtree(author_storage_path)
                        if DEBUG:
                            self.log.info("  removing empty author_storage_path")
                    else:
                        if DEBUG:
                            self.log.info("  author_storage_path not empty (%d objects):" % len(author_files))
                            self.log.info("  %s" % '\n'.join(author_files))
                else:
                    self.log.info("  '%s' (stored external to iTunes, no files deleted)" % cached_book['title'])

            except:
                # We get here if there was an error with .location().path
                if DEBUG:
                    self.log.info("   '%s' not found in iTunes" % cached_book['title'])

            try:
                self.iTunes.delete(cached_book['lib_book'])
            except:
                if DEBUG:
                    self.log.info("   unable to remove '%s' from iTunes" % cached_book['title'])

        elif iswindows:
            '''
            Assume we're wrapped in a pythoncom
            Windows stores the book under a common author directory, so we just delete the .epub
            '''
            try:
                book = cached_book['lib_book']
                path = book.Location
            except:
                book = self._find_library_book(cached_book)
                path = book.Location

            if book:
                storage_path = os.path.split(path)
                if path.startswith(self.iTunes_media):
                    if DEBUG:
                        self.log.info("   removing '%s' at %s" %
                            (cached_book['title'], path))
                    try:
                        os.remove(path)
                    except:
                        self.log.warning("   could not find '%s' in iTunes storage" % path)
                    try:
                        os.rmdir(storage_path[0])
                        self.log.info("   removed folder '%s'" % storage_path[0])
                    except:
                        self.log.info("   folder '%s' not found or not empty" % storage_path[0])

                    # Delete from iTunes database
                else:
                    self.log.info("   '%s' (stored external to iTunes, no files deleted)" % cached_book['title'])
            else:
                if DEBUG:
                    self.log.info("   '%s' not found in iTunes" % cached_book['title'])
            try:
                book.Delete()
            except:
                if DEBUG:
                    self.log.info("   unable to remove '%s' from iTunes" % cached_book['title'])

    def _update_epub_metadata(self, fpath, metadata):
        '''
        '''
        self.log.info(" ITUNES._update_epub_metadata()")

        # Refresh epub metadata
        with open(fpath,'r+b') as zfo:
            # Touch the OPF timestamp
            zf_opf = ZipFile(fpath,'r')
            fnames = zf_opf.namelist()
            opf = [x for x in fnames if '.opf' in x][0]
            if opf:
                opf_raw = cStringIO.StringIO(zf_opf.read(opf))
                soup = BeautifulSoup(opf_raw.getvalue())
                opf_raw.close()

                # Touch existing calibre timestamp
                md = soup.find('metadata')
                ts = md.find('meta',attrs={'name':'calibre:timestamp'})
                if ts:
                    timestamp = ts['content']
                    old_ts = parse_date(timestamp)
                    metadata.timestamp = datetime.datetime(old_ts.year, old_ts.month, old_ts.day, old_ts.hour,
                                               old_ts.minute, old_ts.second, old_ts.microsecond+1, old_ts.tzinfo)
                else:
                    metadata.timestamp = isoformat(now())
                    if DEBUG:
                        self.log.info("   add timestamp: %s" % metadata.timestamp)

                # Fix the language declaration for iBooks 1.1
                patched_language = get_lang()
                language = md.find('dc:language')
                metadata.language = patched_language
                if DEBUG:
                    self.log.info("   updating <dc:language>%s</dc:language> from localization settings" % patched_language)

            zf_opf.close()

            # If 'News' in tags, tweak the title/author for friendlier display in iBooks
            if _('News') in metadata.tags:
                if metadata.title.find('[') > 0:
                    metadata.title = metadata.title[:metadata.title.find('[')-1]
                date_as_author = '%s, %s %s, %s' % (strftime('%A'), strftime('%B'), strftime('%d').lstrip('0'), strftime('%Y'))
                metadata.author = metadata.authors = [date_as_author]
                sort_author =  re.sub('^\s*A\s+|^\s*The\s+|^\s*An\s+', '', metadata.title).rstrip()
                metadata.author_sort = '%s %s' % (sort_author, strftime('%Y-%m-%d'))

            # Remove any non-alpha category tags
            for tag in metadata.tags:
                if not self._is_alpha(tag[0]):
                    metadata.tags.remove(tag)

            # If windows & series, nuke tags so series used as Category during _update_iTunes_metadata()
            if iswindows and metadata.series:
                metadata.tags = None

            set_metadata(zfo, metadata, update_timestamp=True)

    def _update_device(self, msg='', wait=True):
        '''
        Trigger a sync, wait for completion
        '''
        if DEBUG:
            self.log.info(" ITUNES:_update_device():\n %s" % msg)

        if isosx:
            self.iTunes.update()

            if wait:
                # This works if iTunes has books not yet synced to iPad.
                if DEBUG:
                    sys.stdout.write("  waiting for iPad sync to complete ...")
                    sys.stdout.flush()
                while len(self._get_device_books()) != (len(self._get_library_books()) + len(self._get_purchased_book_ids())):
                    if DEBUG:
                        sys.stdout.write('.')
                        sys.stdout.flush()
                    time.sleep(2)
                print
        elif iswindows:
            try:
                pythoncom.CoInitialize()
                self.iTunes = win32com.client.Dispatch("iTunes.Application")
                self.iTunes.UpdateIPod()
                if wait:
                    if DEBUG:
                        sys.stdout.write("  waiting for iPad sync to complete ...")
                        sys.stdout.flush()
                    while True:
                        db_count = len(self._get_device_books())
                        lb_count = len(self._get_library_books())
                        pb_count = len(self._get_purchased_book_ids())
                        if db_count != lb_count + pb_count:
                            if DEBUG:
                                #sys.stdout.write(' %d != %d + %d\n' % (db_count,lb_count,pb_count))
                                sys.stdout.write('.')
                                sys.stdout.flush()
                            time.sleep(2)
                        else:
                            sys.stdout.write('\n')
                            sys.stdout.flush()
                            break
            finally:
                pythoncom.CoUninitialize()

    def _update_iTunes_metadata(self, metadata, db_added, lb_added, this_book):
        '''
        '''
        if DEBUG:
            self.log.info(" ITUNES._update_iTunes_metadata()")

        strip_tags = re.compile(r'<[^<]*?/?>')

        if isosx:
            if lb_added:
                lb_added.album.set(metadata.title)
                lb_added.composer.set(metadata.uuid)
                lb_added.description.set("%s %s" % (self.description_prefix,strftime('%Y-%m-%d %H:%M:%S')))
                lb_added.enabled.set(True)
                lb_added.sort_artist.set(metadata.author_sort.title())
                lb_added.sort_name.set(this_book.title_sorter)
                if this_book.format == 'pdf':
                    lb_added.artist.set(metadata.authors[0])
                    lb_added.name.set(metadata.title)

            if db_added:
                db_added.album.set(metadata.title)
                db_added.composer.set(metadata.uuid)
                db_added.description.set("%s %s" % (self.description_prefix,strftime('%Y-%m-%d %H:%M:%S')))
                db_added.enabled.set(True)
                db_added.sort_artist.set(metadata.author_sort.title())
                db_added.sort_name.set(this_book.title_sorter)
                if this_book.format == 'pdf':
                    db_added.artist.set(metadata.authors[0])
                    db_added.name.set(metadata.title)

            if metadata.comments:
                if lb_added:
                    lb_added.comment.set(strip_tags.sub('',metadata.comments))
                if db_added:
                    db_added.comment.set(strip_tags.sub('',metadata.comments))

            if metadata.rating:
                if lb_added:
                    lb_added.rating.set(metadata.rating*10)
                # iBooks currently doesn't allow setting rating ... ?
                try:
                    if db_added:
                        db_added.rating.set(metadata.rating*10)
                except:
                    pass

            # Set genre from series if available, else first alpha tag
            # Otherwise iTunes grabs the first dc:subject from the opf metadata
            if metadata.series and self.settings().read_metadata:
                if DEBUG:
                    self.log.info("   using Series name as Genre")
                if lb_added:
                    lb_added.sort_name.set("%s %03d" % (metadata.series, metadata.series_index))
                    lb_added.genre.set(metadata.series)
                    lb_added.episode_ID.set(metadata.series)
                    lb_added.episode_number.set(metadata.series_index)

                if db_added:
                    db_added.sort_name.set("%s %03d" % (metadata.series, metadata.series_index))
                    db_added.genre.set(metadata.series)
                    db_added.episode_ID.set(metadata.series)
                    db_added.episode_number.set(metadata.series_index)

            elif metadata.tags:
                if DEBUG:
                    self.log.info("   %susing Tag as Genre" %
                                  "no Series name available, " if self.settings().read_metadata else '')
                for tag in metadata.tags:
                    if self._is_alpha(tag[0]):
                        if lb_added:
                            lb_added.genre.set(tag)
                        if db_added:
                            db_added.genre.set(tag)
                        break

        elif iswindows:
            if lb_added:
                lb_added.Album = metadata.title
                lb_added.Composer = metadata.uuid
                lb_added.Description = ("%s %s" % (self.description_prefix,strftime('%Y-%m-%d %H:%M:%S')))
                lb_added.Enabled = True
                lb_added.SortArtist = (metadata.author_sort.title())
                lb_added.SortName = (this_book.title_sorter)
                if this_book.format == 'pdf':
                    lb_added.Artist = metadata.authors[0]
                    lb_added.Name = metadata.title

            if db_added:
                db_added.Album = metadata.title
                db_added.Composer = metadata.uuid
                db_added.Description = ("%s %s" % (self.description_prefix,strftime('%Y-%m-%d %H:%M:%S')))
                db_added.Enabled = True
                db_added.SortArtist = (metadata.author_sort.title())
                db_added.SortName = (this_book.title_sorter)
                if this_book.format == 'pdf':
                    db_added.Artist = metadata.authors[0]
                    db_added.Name = metadata.title

            if metadata.comments:
                if lb_added:
                    lb_added.Comment = (strip_tags.sub('',metadata.comments))
                if db_added:
                    db_added.Comment = (strip_tags.sub('',metadata.comments))

            if metadata.rating:
                if lb_added:
                    lb_added.AlbumRating = (metadata.rating*10)
                # iBooks currently doesn't allow setting rating ... ?
                try:
                    if db_added:
                        db_added.AlbumRating = (metadata.rating*10)
                except:
                    if DEBUG:
                        self.log.warning("  iTunes automation interface reported an error"
                                         " setting AlbumRating on iDevice")

            # Set Genre from first alpha tag, overwrite with series if available
            # Otherwise iBooks uses first <dc:subject> from opf
            # iTunes balks on setting EpisodeNumber, but it sticks (9.1.1.12)

            if metadata.series and self.settings().read_metadata:
                if DEBUG:
                    self.log.info("   using Series name as Genre")
                if lb_added:
                    lb_added.SortName = "%s %03d" % (metadata.series, metadata.series_index)
                    lb_added.Genre = metadata.series
                    lb_added.EpisodeID = metadata.series
                    try:
                        lb_added.EpisodeNumber = metadata.series_index
                    except:
                        pass
                if db_added:
                    db_added.SortName = "%s %03d" % (metadata.series, metadata.series_index)
                    db_added.Genre = metadata.series
                    db_added.EpisodeID = metadata.series
                    try:
                        db_added.EpisodeNumber = metadata.series_index
                    except:
                        if DEBUG:
                            self.log.warning("  iTunes automation interface reported an error"
                                             " setting EpisodeNumber on iDevice")
            elif metadata.tags:
                if DEBUG:
                    self.log.info("   using Tag as Genre")
                for tag in metadata.tags:
                    if self._is_alpha(tag[0]):
                        if lb_added:
                            lb_added.Genre = tag
                        if db_added:
                            db_added.Genre = tag
                        break


class BookList(list):
    '''
    A list of books. Each Book object must have the fields:
      1. title
      2. authors
      3. size (file size of the book)
      4. datetime (a UTC time tuple)
      5. path (path on the device to the book)
      6. thumbnail (can be None) thumbnail is either a str/bytes object with the
         image data or it should have an attribute image_path that stores an
         absolute (platform native) path to the image
      7. tags (a list of strings, can be empty).
    '''

    __getslice__ = None
    __setslice__ = None
    log = None

    def __init__(self, log):
        self.log = log

    def supports_collections(self):
        ''' Return True if the the device supports collections for this book list. '''
        return False

    def add_book(self, book, replace_metadata):
        '''
        Add the book to the booklist. Intent is to maintain any device-internal
        metadata. Return True if booklists must be sync'ed
        '''
        self.append(book)

    def remove_book(self, book):
        '''
        Remove a book from the booklist. Correct any device metadata at the
        same time
        '''
        raise NotImplementedError()

    def get_collections(self, collection_attributes):
        '''
        Return a dictionary of collections created from collection_attributes.
        Each entry in the dictionary is of the form collection name:[list of
        books]

        The list of books is sorted by book title, except for collections
        created from series, in which case series_index is used.

        :param collection_attributes: A list of attributes of the Book object
        '''
        return {}

class Book(MetaInformation):
    '''
    A simple class describing a book in the iTunes Books Library.
    - See ebooks.metadata.__init__ for all fields
    '''
    def __init__(self,title,author):

        MetaInformation.__init__(self, title, authors=[author])

    @dynamic_property
    def title_sorter(self):
        doc = '''String to sort the title. If absent, title is returned'''
        def fget(self):
            return re.sub('^\s*A\s+|^\s*The\s+|^\s*An\s+', '', self.title).rstrip()
        return property(doc=doc, fget=fget)
