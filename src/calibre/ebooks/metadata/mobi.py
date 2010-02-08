'''
Retrieve and modify in-place Mobipocket book metadata.
'''

from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal kovid@kovidgoyal.net and ' \
    'Marshall T. Vandegrift <llasram@gmail.com>'
__docformat__ = 'restructuredtext en'

from struct import pack, unpack
from cStringIO import StringIO
from datetime import datetime

from calibre.ebooks.mobi import MobiError
from calibre.ebooks.mobi.writer import rescale_image, MAX_THUMB_DIMEN
from calibre.ebooks.mobi.langcodes import iana2mobi

import struct

class StreamSlicer(object):

    def __init__(self, stream, start=0, stop=None):
        self._stream = stream
        self.start = start
        if stop is None:
            stream.seek(0, 2)
            stop = stream.tell()
        self.stop = stop
        self._len = stop - start

    def __len__(self):
        return self._len

    def __getitem__(self, key):
        stream = self._stream
        base = self.start
        if isinstance(key, (int, long)):
            stream.seek(base + key)
            return stream.read(1)
        if isinstance(key, slice):
            start, stop, stride = key.indices(self._len)
            if stride < 0:
                start, stop = stop, start
            size = stop - start
            if size <= 0:
                return ""
            stream.seek(base + start)
            data = stream.read(size)
            if stride != 1:
                data = data[::stride]
            return data
        raise TypeError("stream indices must be integers")

    def __setitem__(self, key, value):
        stream = self._stream
        base = self.start
        if isinstance(key, (int, long)):
            if len(value) != 1:
                raise ValueError("key and value lengths must match")
            stream.seek(base + key)
            return stream.write(value)
        if isinstance(key, slice):
            start, stop, stride = key.indices(self._len)
            if stride < 0:
                start, stop = stop, start
            size = stop - start
            if stride != 1:
                value = value[::stride]
            if len(value) != size:
                raise ValueError("key and value lengths must match")
            stream.seek(base + start)
            return stream.write(value)
        raise TypeError("stream indices must be integers")

    def update(self, data_blocks):
        # Rewrite the stream
        stream = self._stream
        base = self.start
        stream.seek(base)
        self._stream.truncate(base)
        for block in data_blocks:
            stream.write(block)

    def truncate(self, value):
        self._stream.truncate(value)

class MetadataUpdater(object):
    def __init__(self, stream):
        self.stream = stream
        data = self.data = StreamSlicer(stream)
        self.type = data[60:68]

        if self.type != "BOOKMOBI":
            return

        self.nrecs, = unpack('>H', data[76:78])
        record0 = self.record0 = self.record(0)
        self.encryption_type, = unpack('>H', record0[12:14])
        codepage, = unpack('>I', record0[28:32])
        self.codec = 'utf-8' if codepage == 65001 else 'cp1252'
        image_base, = unpack('>I', record0[108:112])
        flags, = self.flags, = unpack('>I', record0[128:132])
        have_exth = self.have_exth = (flags & 0x40) != 0
        self.cover_record = self.thumbnail_record = None
        self.timestamp = None

        self.pdbrecords = self.get_pdbrecords()
        if not have_exth:
            self.create_exth()

        # Fetch timestamp, cover_record, thumbnail_record
        self.fetchEXTHFields()

    def fetchEXTHFields(self):
        stream = self.stream
        record0 = self.record0

        # 20:24 = mobiHeaderLength, 16=PDBHeader size
        exth_off = unpack('>I', record0[20:24])[0] + 16 + record0.start
        image_base, = unpack('>I', record0[108:112])

        # Fetch EXTH block
        exth = self.exth = StreamSlicer(stream, exth_off, record0.stop)
        nitems, = unpack('>I', exth[8:12])
        pos = 12
        # Store any EXTH fields not specifiable in GUI
        for i in xrange(nitems):
            id, size = unpack('>II', exth[pos:pos + 8])
            content = exth[pos + 8: pos + size]
            pos += size

            if id == 106:
                self.timestamp = content
            elif id == 201:
                rindex, = self.cover_rindex, = unpack('>I', content)
                self.cover_record = self.record(rindex + image_base)
            elif id == 202:
                rindex, = self.thumbnail_rindex, = unpack('>I', content)
                self.thumbnail_record = self.record(rindex + image_base)

    def patch(self, off, new_record0):
        # Save the current size of each record
        record_sizes = [len(new_record0)]
        for i in range(1,self.nrecs-1):
            record_sizes.append(self.pdbrecords[i+1][0]-self.pdbrecords[i][0])
        # And the last one
        record_sizes.append(self.data.stop - self.pdbrecords[self.nrecs-1][0])

        # pdbrecord[0] is the offset of record0.  It will not change
        # record1 offset will be offset of record0 + len(new_record0)
        updated_pdbrecords = [self.pdbrecords[0][0]]
        record0_offset = self.pdbrecords[0][0]
        updated_offset = record0_offset + len(new_record0)

        for i in range(1,self.nrecs-1):
            updated_pdbrecords.append(updated_offset)
            updated_offset += record_sizes[i]
        # Update the last pdbrecord
        updated_pdbrecords.append(updated_offset)

        # Read in current records 1 to last
        data_blocks = [new_record0]
        for i in range(1,self.nrecs):
            data_blocks.append(self.data[self.pdbrecords[i][0]:self.pdbrecords[i][0] + record_sizes[i]])

        # Rewrite the stream
        self.record0.update(data_blocks)

        # Rewrite the pdbrecords
        self.update_pdbrecords(updated_pdbrecords)

        # Truncate if necessary
        if (updated_pdbrecords[-1] + record_sizes[-1]) < self.data.stop:
            self.data.truncate(updated_pdbrecords[-1] + record_sizes[-1])
        else:
            self.data.stop = updated_pdbrecords[-1] + record_sizes[-1]

    def patchSection(self, section, new):
        off = self.pdbrecords[section][0]
        self.patch(off, new)

    def create_exth(self, exth=None):
        # Add an EXTH block to record 0, rewrite the stream
        # self.hexdump(self.record0)

        # Fetch the title
        title_offset, = struct.unpack('>L', self.record0[0x54:0x58])
        title_length, = struct.unpack('>L', self.record0[0x58:0x5c])
        title_in_file, = struct.unpack('%ds' % (title_length), self.record0[title_offset:title_offset + title_length])

        # Adjust length to accommodate PrimaryINDX if necessary
        mobi_header_length, = unpack('>L', self.record0[0x14:0x18])
        if mobi_header_length == 0xe4:
            # Patch mobi_header_length to 0xE8
            self.record0[0x17] = "\xe8"
            self.record0[0xf4:0xf8] = pack('>L', 0xFFFFFFFF)
            mobi_header_length = 0xe8

        # Set EXTH flag (0x40)
        self.record0[0x80:0x84] = pack('>L', self.flags|0x40)

        if not exth:
            # Construct an empty EXTH block
            pad = '\0' * 4
            exth = ['EXTH', pack('>II', 12, 0), pad]
            exth = ''.join(exth)

        # Update title_offset
        self.record0[0x54:0x58] = pack('>L', 0x10 + mobi_header_length + len(exth))

        # Create an updated Record0
        new_record0 = StringIO()
        new_record0.write(self.record0[:0x10 + mobi_header_length])
        new_record0.write(exth)
        new_record0.write(title_in_file)

        # Pad to a 4-byte boundary
        trail = len(new_record0.getvalue()) % 4
        pad = '\0' * (4 - trail) # Always pad w/ at least 1 byte
        new_record0.write(pad)

        #self.hexdump(new_record0.getvalue())

        # Rebuild the stream, update the pdbrecords pointers
        self.patchSection(0,new_record0.getvalue())

        # Update record0
        self.record0 = self.record(0)

    def hexdump(self, src, length=16):
        # Diagnostic
        FILTER=''.join([(len(repr(chr(x)))==3) and chr(x) or '.' for x in range(256)])
        N=0; result=''
        while src:
           s,src = src[:length],src[length:]
           hexa = ' '.join(["%02X"%ord(x) for x in s])
           s = s.translate(FILTER)
           result += "%04X   %-*s   %s\n" % (N, length*3, hexa, s)
           N+=length
        print result

    def get_pdbrecords(self):
        pdbrecords = []
        for i in xrange(self.nrecs):
            offset, a1,a2,a3,a4 = struct.unpack('>LBBBB', self.data[78+i*8:78+i*8+8])
            flags, val = a1, a2<<16|a3<<8|a4
            pdbrecords.append( [offset, flags, val] )
        return pdbrecords

    def update_pdbrecords(self, updated_pdbrecords):
        for (i, pdbrecord) in enumerate(updated_pdbrecords):
            self.data[78+i*8:78+i*8 + 4] = pack('>L',pdbrecord)

        # Refresh local copy
        self.pdbrecords = self.get_pdbrecords()

    def dump_pdbrecords(self):
        # Diagnostic
        print "MetadataUpdater.dump_pdbrecords()"
        print "%10s %10s %10s" % ("offset","flags","val")
        for i in xrange(len(self.pdbrecords)):
            pdbrecord = self.pdbrecords[i]
            print "%10X %10X %10X" % (pdbrecord[0], pdbrecord[1], pdbrecord[2])

    def record(self, n):
        if n >= self.nrecs:
            raise ValueError('non-existent record %r' % n)
        offoff = 78 + (8 * n)
        start, = unpack('>I', self.data[offoff + 0:offoff + 4])
        stop = None
        if n < (self.nrecs - 1):
            stop, = unpack('>I', self.data[offoff + 8:offoff + 12])
        return StreamSlicer(self.stream, start, stop)

    def update(self, mi):
        if self.type != "BOOKMOBI":
                raise MobiError("Setting metadata only supported for MOBI files of type 'BOOK'.\n"
                                "\tThis is a '%s' file of type '%s'" % (self.type[0:4], self.type[4:8]))

        recs = []
        try:
             from calibre.ebooks.conversion.config import load_defaults
             prefs = load_defaults('mobi_output')
             pas = prefs.get('prefer_author_sort', False)
        except:
            pas = False
        if mi.author_sort and pas:
            authors = mi.author_sort
            recs.append((100, authors.encode(self.codec, 'replace')))
        elif mi.authors:
            authors = '; '.join(mi.authors)
            recs.append((100, authors.encode(self.codec, 'replace')))
        if mi.publisher:
            recs.append((101, mi.publisher.encode(self.codec, 'replace')))
        if mi.comments:
            recs.append((103, mi.comments.encode(self.codec, 'replace')))
        if mi.isbn:
            recs.append((104, mi.isbn.encode(self.codec, 'replace')))
        if mi.tags:
            subjects = '; '.join(mi.tags)
            recs.append((105, subjects.encode(self.codec, 'replace')))
        if mi.pubdate:
            recs.append((106, str(mi.pubdate).encode(self.codec, 'replace')))
        elif mi.timestamp:
            recs.append((106, str(mi.timestamp).encode(self.codec, 'replace')))
        elif self.timestamp:
            recs.append((106, self.timestamp))
        else:
            recs.append((106, str(datetime.now()).encode(self.codec, 'replace')))
        if self.cover_record is not None:
            recs.append((201, pack('>I', self.cover_rindex)))
            recs.append((203, pack('>I', 0)))
        if self.thumbnail_record is not None:
            recs.append((202, pack('>I', self.thumbnail_rindex)))

        if getattr(self, 'encryption_type', -1) != 0:
            raise MobiError('Setting metadata in DRMed MOBI files is not supported.')

        exth = StringIO()
        for code, data in recs:
            exth.write(pack('>II', code, len(data) + 8))
            exth.write(data)
        exth = exth.getvalue()
        trail = len(exth) % 4
        pad = '\0' * (4 - trail) # Always pad w/ at least 1 byte
        exth = ['EXTH', pack('>II', len(exth) + 12, len(recs)), exth, pad]
        exth = ''.join(exth)

        if getattr(self, 'exth', None) is None:
            raise MobiError('No existing EXTH record. Cannot update metadata.')

        self.record0[92:96] = iana2mobi(mi.language)
        self.create_exth(exth)

        # Fetch updated timestamp, cover_record, thumbnail_record
        self.fetchEXTHFields()

        if mi.cover_data[1] or mi.cover:
            try:
                data =  mi.cover_data[1] if mi.cover_data[1] else open(mi.cover, 'rb').read()
            except:
                pass
            else:
                if self.cover_record is not None:
                    size = len(self.cover_record)
                    cover = rescale_image(data, size)
                    cover += '\0' * (size - len(cover))
                    self.cover_record[:] = cover
                if self.thumbnail_record is not None:
                    size = len(self.thumbnail_record)
                    thumbnail = rescale_image(data, size, dimen=MAX_THUMB_DIMEN)
                    thumbnail += '\0' * (size - len(thumbnail))
                    self.thumbnail_record[:] = thumbnail
        return

def set_metadata(stream, mi):
    mu = MetadataUpdater(stream)
    mu.update(mi)
    return
