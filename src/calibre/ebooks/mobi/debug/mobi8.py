#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)
from future_builtins import map

__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import sys, os, imghdr, struct, textwrap
from itertools import izip

from calibre import CurrentDir
from calibre.ebooks.mobi.debug.headers import TextRecord
from calibre.ebooks.mobi.debug.index import (SKELIndex, SECTIndex, NCXIndex,
        GuideIndex)
from calibre.ebooks.mobi.utils import read_font_record, decode_tbs, RECORD_SIZE
from calibre.ebooks.mobi.debug import format_bytes
from calibre.ebooks.mobi.reader.headers import NULL_INDEX

class FDST(object):

    def __init__(self, raw):
        if raw[:4] != b'FDST':
            raise ValueError('KF8 does not have a valid FDST record')
        self.sec_off, self.num_sections = struct.unpack_from(b'>LL', raw, 4)
        if self.sec_off != 12:
            raise ValueError('FDST record has unknown extra fields')
        secf = b'>%dL' % (self.num_sections*2)
        secs = struct.unpack_from(secf, raw, self.sec_off)
        rest = raw[self.sec_off+struct.calcsize(secf):]
        if rest:
            raise ValueError('FDST record has trailing data: '
                    '%s'%format_bytes(rest))
        self.sections = tuple(izip(secs[::2], secs[1::2]))

    def __str__(self):
        ans = ['FDST record']
        a = lambda k, v:ans.append('%s: %s'%(k, v))
        a('Offset to sections', self.sec_off)
        a('Number of section records', self.num_sections)
        ans.append('**** %d Sections ****'% len(self.sections))
        for sec in self.sections:
            ans.append('Start: %20d End: %d'%sec)

        return '\n'.join(ans)

class File(object):

    def __init__(self, skel, skeleton, text, first_aid, sections):
        self.name = 'part%04d'%skel.file_number
        self.skeleton, self.text, self.first_aid = skeleton, text, first_aid
        self.sections = sections

    def dump(self, ddir):
        with open(os.path.join(ddir, self.name + '.html'), 'wb') as f:
            f.write(self.text)
        base = os.path.join(ddir, self.name + '-parts')
        os.mkdir(base)
        with CurrentDir(base):
            with open('skeleton.html', 'wb') as f:
                f.write(self.skeleton)
            for i, text in enumerate(self.sections):
                with open('sect-%04d.html'%i, 'wb') as f:
                    f.write(text)

class MOBIFile(object):

    def __init__(self, mf):
        self.mf = mf
        h, h8 = mf.mobi_header, mf.mobi8_header
        first_text_record = 1
        offset = 0
        res_end = len(mf.records)
        if mf.kf8_type == 'joint':
            offset = h.exth.kf8_header_index
            res_end = offset - 1

        self.resource_records = mf.records[h.first_non_book_record:res_end]
        self.text_records = [TextRecord(i, r, h8.extra_data_flags,
            mf.decompress8) for i, r in
            enumerate(mf.records[first_text_record+offset:
                first_text_record+offset+h8.number_of_text_records])]

        self.raw_text = b''.join(r.raw for r in self.text_records)
        self.header = self.mf.mobi8_header
        self.extract_resources()
        self.read_fdst()
        self.read_indices()
        self.build_files()
        self.read_tbs()

    def print_header(self, f=sys.stdout):
        print (str(self.mf.palmdb).encode('utf-8'), file=f)
        print (file=f)
        print ('Record headers:', file=f)
        for i, r in enumerate(self.mf.records):
            print ('%6d. %s'%(i, r.header), file=f)

        print (file=f)
        print (str(self.mf.mobi8_header).encode('utf-8'), file=f)

    def read_fdst(self):
        self.fdst = None

        if self.header.fdst_idx != NULL_INDEX:
            idx = self.header.fdst_idx
            self.fdst = FDST(self.mf.records[idx].raw)
            if self.fdst.num_sections != self.header.fdst_count:
                raise ValueError('KF8 Header contains invalid FDST count')

    def read_indices(self):
        self.skel_index = SKELIndex(self.header.skel_idx, self.mf.records,
                self.header.encoding)
        self.sect_index = SECTIndex(self.header.sect_idx, self.mf.records,
                self.header.encoding)
        self.ncx_index = NCXIndex(self.header.primary_index_record,
                self.mf.records, self.header.encoding)
        self.guide_index = GuideIndex(self.header.oth_idx, self.mf.records,
                self.header.encoding)

    def build_files(self):
        text = self.raw_text
        self.files = []
        for skel in self.skel_index.records:
            sects = [x for x in self.sect_index.records if x.file_number
                    == skel.file_number]
            skeleton = text[skel.start_position:skel.start_position+skel.length]
            ftext = skeleton
            first_aid = sects[0].toc_text
            sections = []

            for sect in sects:
                start_pos = skel.start_position + skel.length + sect.start_pos
                sect_text = text[start_pos:start_pos+sect.length]
                insert_pos = sect.insert_pos - skel.start_position
                ftext = ftext[:insert_pos] + sect_text + ftext[insert_pos:]
                sections.append(sect_text)

            self.files.append(File(skel, skeleton, ftext, first_aid, sections))

    def dump_flows(self, ddir):
        boundaries = [(0, len(self.raw_text))]
        if self.fdst is not None:
            boundaries = self.fdst.sections
        for i, x in enumerate(boundaries):
            start, end = x
            raw = self.raw_text[start:end]
            with open(os.path.join(ddir, 'flow%04d.txt'%i), 'wb') as f:
                f.write(raw)

    def extract_resources(self):
        self.resource_map = []
        known_types = {b'FLIS', b'FCIS', b'SRCS',
                    b'\xe9\x8e\r\n', b'RESC', b'BOUN', b'FDST', b'DATP',
                    b'AUDI', b'VIDE'}

        for i, rec in enumerate(self.resource_records):
            sig = rec.raw[:4]
            payload = rec.raw
            ext = 'dat'
            prefix = 'binary'
            suffix = ''
            if sig in {b'HUFF', b'CDIC', b'INDX'}: continue
            # TODO: Ignore CNCX records as well
            if sig == b'FONT':
                font = read_font_record(rec.raw)
                if font['err']:
                    raise ValueError('Failed to read font record: %s Headers: %s'%(
                        font['err'], font['headers']))
                payload = (font['font_data'] if font['font_data'] else
                        font['raw_data'])
                prefix, ext = 'fonts', font['ext']
            elif sig not in known_types:
                q = imghdr.what(None, rec.raw)
                if q:
                    prefix, ext = 'images', q

            if prefix == 'binary':
                if sig == b'\xe9\x8e\r\n':
                    suffix = '-EOF'
                elif sig in known_types:
                    suffix = '-' + sig.decode('ascii')

            self.resource_map.append(('%s/%06d%s.%s'%(prefix, i, suffix, ext),
                payload))

    def read_tbs(self):
        from calibre.ebooks.mobi.writer8.tbs import (Entry, DOC,
                collect_indexing_data, encode_strands_as_sequences,
                sequences_to_bytes)
        entry_map = []
        for index in self.ncx_index:
            vals = list(index)[:-1] + [None, None, None, None]
            entry_map.append(Entry(*vals))


        indexing_data = collect_indexing_data(entry_map, list(map(len,
            self.text_records)))
        self.indexing_data = [DOC + '\n' +textwrap.dedent('''\
                Index Entry lines are of the form:
                depth:index_number [action] parent (index_num-parent) Geometry

                Where Geometry is the start and end of the index entry w.r.t
                the start of the text record.

                ''')]
        for i, strands in enumerate(indexing_data):
            rec = self.text_records[i]
            tbs_bytes = rec.trailing_data.get('indexing', b'')
            desc = ['Record #%d'%i]
            for s, strand in enumerate(strands):
                desc.append('Strand %d'%s)
                for entries in strand.itervalues():
                    for e in entries:
                        desc.append(
                        ' %s%d [%-9s] parent: %s (%d) Geometry: (%d, %d)'%(
                            e.depth * ('  ') + '- ', e.index, e.action, e.parent,
                            e.index-(e.parent or 0), e.start-i*RECORD_SIZE,
                            e.start+e.length-i*RECORD_SIZE))
            desc.append('TBS Bytes: ' + format_bytes(tbs_bytes))
            flag_sz = 3
            sequences = []
            otbs = tbs_bytes
            while tbs_bytes:
                try:
                    val, extra, consumed = decode_tbs(tbs_bytes, flag_size=flag_sz)
                except:
                    break
                flag_sz = 4
                tbs_bytes = tbs_bytes[consumed:]
                extra = {bin(k):v for k, v in extra.iteritems()}
                sequences.append((val, extra))
            for j, seq in enumerate(sequences):
                desc.append('Sequence #%d: %r %r'%(j, seq[0], seq[1]))
            if tbs_bytes:
                desc.append('Remaining bytes: %s'%format_bytes(tbs_bytes))
            calculated_sequences = encode_strands_as_sequences(strands)
            calculated_bytes = sequences_to_bytes(calculated_sequences)
            if calculated_bytes != otbs:
                print ('WARNING: TBS mismatch for record %d'%i)
                desc.append('WARNING: TBS mismatch!')
                desc.append('Calculated sequences: %r'%calculated_sequences)
            desc.append('')
            self.indexing_data.append('\n'.join(desc))

def inspect_mobi(mobi_file, ddir):
    f = MOBIFile(mobi_file)
    with open(os.path.join(ddir, 'header.txt'), 'wb') as out:
        f.print_header(f=out)

    alltext = os.path.join(ddir, 'raw_text.html')
    with open(alltext, 'wb') as of:
        of.write(f.raw_text)

    for x in ('text_records', 'images', 'fonts', 'binary', 'files', 'flows'):
        os.mkdir(os.path.join(ddir, x))

    for rec in f.text_records:
        rec.dump(os.path.join(ddir, 'text_records'))

    for href, payload in f.resource_map:
        with open(os.path.join(ddir, href), 'wb') as fo:
            fo.write(payload)

    if f.fdst:
        with open(os.path.join(ddir, 'fdst.record'), 'wb') as fo:
            fo.write(str(f.fdst).encode('utf-8'))

    with open(os.path.join(ddir, 'skel.record'), 'wb') as fo:
        fo.write(str(f.skel_index).encode('utf-8'))

    with open(os.path.join(ddir, 'chunks.record'), 'wb') as fo:
        fo.write(str(f.sect_index).encode('utf-8'))

    with open(os.path.join(ddir, 'ncx.record'), 'wb') as fo:
        fo.write(str(f.ncx_index).encode('utf-8'))

    with open(os.path.join(ddir, 'guide.record'), 'wb') as fo:
        fo.write(str(f.guide_index).encode('utf-8'))

    with open(os.path.join(ddir, 'tbs.txt'), 'wb') as fo:
        fo.write(('\n'.join(f.indexing_data)).encode('utf-8'))

    for part in f.files:
        part.dump(os.path.join(ddir, 'files'))

    f.dump_flows(os.path.join(ddir, 'flows'))


