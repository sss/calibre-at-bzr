##    Copyright (C) 2006 Kovid Goyal kovid@kovidgoyal.net
##    This program is free software; you can redistribute it and/or modify
##    it under the terms of the GNU General Public License as published by
##    the Free Software Foundation; either version 2 of the License, or
##    (at your option) any later version.
##
##    This program is distributed in the hope that it will be useful,
##    but WITHOUT ANY WARRANTY; without even the implied warranty of
##    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
##    GNU General Public License for more details.
##
##    You should have received a copy of the GNU General Public License along
##    with this program; if not, write to the Free Software Foundation, Inc.,
##    51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
"""
Define the minimum interface that a device backend must satisfy to be used in
the GUI. A device backend must subclass the L{Device} class. See prs500.py for
a backend that implement the Device interface for the SONY PRS500 Reader.
"""


class Device(object):
    """ 
    Defines the interface that should be implemented by backends that 
    communicate with an ebook reader. 
    
    The C{end_session} variables are used for USB session management. Sometimes
    the front-end needs to call several methods one after another, in which case 
    the USB session should not be closed after each method call.
    """
    # Ordered list of supported formats
    FORMATS     = ["lrf", "rtf", "pdf", "txt"]
    VENDOR_ID   = 0x0000
    PRODUCT_ID  = 0x0000
    THUMBNAIL_HEIGHT = 68 # Height for thumbnails on device
    
    def __init__(self, key='-1', log_packets=False, report_progress=None) :
        """ 
        @param key: The key to unlock the device
        @param log_packets: If true the packet stream to/from the device is logged 
        @param report_progress: Function that is called with a % progress 
                                (number between 0 and 100) for various tasks
                                If it is called with -1 that means that the 
                                task does not have any progress information
        """
        raise NotImplementedError()
    
    @classmethod
    def is_connected(cls):
        '''Return True iff the device is physically connected to the computer'''
        raise NotImplementedError()
    
    def set_progress_reporter(self, report_progress):
        '''
        @param report_progress: Function that is called with a % progress 
                                (number between 0 and 100) for various tasks
                                If it is called with -1 that means that the 
                                task does not have any progress information
        '''
        raise NotImplementedError()
    
    def get_device_information(self, end_session=True):
        """ 
        Ask device for device information. See L{DeviceInfoQuery}. 
        @return: (device name, device version, software version on device, mime type)
        """
        raise NotImplementedError()
    
    def card_prefix(self, end_session=True):
        '''
        Return prefix to paths on the card or None if no cards present.
        '''
        raise NotImplementedError()
    
    def total_space(self, end_session=True):
        """ 
        Get total space available on the mountpoints:
          1. Main memory
          2. Memory Stick
          3. SD Card

        @return: A 3 element list with total space in bytes of (1, 2, 3). If a
        particular device doesn't have any of these locations it should return 0.
        """
        raise NotImplementedError()
    
    def free_space(self, end_session=True):
        """ 
        Get free space available on the mountpoints:
          1. Main memory
          2. Card A
          3. Card B

        @return: A 3 element list with free space in bytes of (1, 2, 3). If a
        particular device doesn't have any of these locations it should return -1.
        """    
        raise NotImplementedError()
    
    def books(self, oncard=False, end_session=True):
        """ 
        Return a list of ebooks on the device.
        @param oncard: If True return a list of ebooks on the storage card, 
                       otherwise return list of ebooks in main memory of device.
                       If True and no books on card return empty list. 
        @return: A BookList. 
        """    
        raise NotImplementedError()
    
    def upload_books(self, files, names, on_card=False, end_session=True):
        '''
        Upload a list of books to the device. If a file already
        exists on the device, it should be replaced.
        This method should raise a L{FreeSpaceError} if there is not enough
        free space on the device. The text of the FreeSpaceError must contain the
        word "card" if C{on_card} is True otherwise it must contain the word "memory".
        @param files: A list of paths and/or file-like objects.
        @param names: A list of file names that the books should have 
        once uploaded to the device. len(names) == len(files)
        @return: A list of 3-element tuples. The list is meant to be passed 
        to L{add_books_to_metadata}.
        '''
        raise NotImplementedError()
    
    @classmethod
    def add_books_to_metadata(cls, locations, metadata, booklists):
        '''
        Add locations to the booklists. This function must not communicate with 
        the device. 
        @param locations: Result of a call to L{upload_books}
        @param metadata: List of dictionaries. Each dictionary must have the
        keys C{title}, C{authors}, C{cover}, C{tags}. The value of the C{cover} 
        element can be None or a three element tuple (width, height, data)
        where data is the image data in JPEG format as a string. C{tags} must be
        a possibly empty list of strings. C{authors} must be a string.
        @param booklists: A tuple containing the result of calls to 
                                (L{books}(oncard=False), L{books}(oncard=True)).
        '''
        raise NotImplementedError
    
    def delete_books(self, paths, end_session=True):
        '''
        Delete books at paths on device.
        '''
        raise NotImplementedError()
    
    @classmethod
    def remove_books_from_metadata(cls, paths, booklists):
        '''
        Remove books from the metadata list. This function must not communicate 
        with the device.
        @param paths: paths to books on the device.
        @param booklists:  A tuple containing the result of calls to 
                                (L{books}(oncard=False), L{books}(oncard=True)).
        '''
        raise NotImplementedError()
        
    def sync_booklists(self, booklists, end_session=True):
        '''
        Update metadata on device.
        @param booklists: A tuple containing the result of calls to 
                                (L{books}(oncard=False), L{books}(oncard=True)).
        '''
        raise NotImplementedError()
    
    def get_file(self, path, outfile, end_session=True): 
        '''
        Read the file at C{path} on the device and write it to outfile.
        @param outfile: file object like C{sys.stdout} or the result of an C{open} call
        '''
        raise NotImplementedError()         


    
class BookList(list):
    '''
    A list of books. Each Book object must have the fields:
      1. title
      2. authors
      3. size (file size of the book)
      4. datetime (a UTC time tuple)
      5. path (path on the device to the book)
      6. thumbnail (can be None)
      7. tags (a list of strings, can be empty). 
    '''
    
    def __init__(self):
        list.__init__(self)
    
    def supports_tags(self):
        ''' Return True if the the device supports tags (collections) for this book list. '''
        raise NotImplementedError()
    
    def set_tags(self, book, tags):
        '''
        Set the tags for C{book} to C{tags}. 
        @param tags: A list of strings. Can be empty.
        @param book: A book object that is in this BookList. 
        '''
        raise NotImplementedError()

