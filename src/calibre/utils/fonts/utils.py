#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=marker:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import struct
from io import BytesIO
from collections import defaultdict

class UnsupportedFont(ValueError):
    pass

def get_printable_characters(text):
    import unicodedata
    return u''.join(x for x in unicodedata.normalize('NFC', text)
            if unicodedata.category(x)[0] not in {'C', 'Z', 'M'})

def is_truetype_font(raw):
    sfnt_version = raw[:4]
    return (sfnt_version in {b'\x00\x01\x00\x00', b'OTTO'}, sfnt_version)

def get_tables(raw):
    num_tables = struct.unpack_from(b'>H', raw, 4)[0]
    offset = 4*3 # start of the table record entries
    for i in xrange(num_tables):
        table_tag, table_checksum, table_offset, table_length = struct.unpack_from(
                    b'>4s3L', raw, offset)
        yield (table_tag, raw[table_offset:table_offset+table_length], offset,
                table_offset, table_checksum)
        offset += 4*4

def get_table(raw, name):
    ''' Get the raw table bytes for the specified table in the font '''
    name = bytes(name.lower())
    for table_tag, table, table_index, table_offset, table_checksum in get_tables(raw):
        if table_tag.lower() == name:
            return table, table_index, table_offset, table_checksum
    return None, None, None, None

def get_font_characteristics(raw, raw_is_table=False, return_all=False):
    '''
    Return (weight, is_italic, is_bold, is_regular, fs_type, panose, width,
    is_oblique, is_wws). These
    values are taken from the OS/2 table of the font. See
    http://www.microsoft.com/typography/otspec/os2.htm for details
    '''
    if raw_is_table:
        os2_table = raw
    else:
        os2_table = get_table(raw, 'os/2')[0]
        if os2_table is None:
            raise UnsupportedFont('Not a supported font, has no OS/2 table')

    common_fields = b'>Hh3H11h'
    (version, char_width, weight, width, fs_type, subscript_x_size,
            subscript_y_size, subscript_x_offset, subscript_y_offset,
            superscript_x_size, superscript_y_size, superscript_x_offset,
            superscript_y_offset, strikeout_size, strikeout_position,
            family_class) = struct.unpack_from(common_fields, os2_table)
    offset = struct.calcsize(common_fields)
    panose = struct.unpack_from(b'>10B', os2_table, offset)
    offset += 10
    (range1,) = struct.unpack_from(b'>L', os2_table, offset)
    offset += struct.calcsize(b'>L')
    if version > 0:
        range2, range3, range4 = struct.unpack_from(b'>3L', os2_table, offset)
        offset += struct.calcsize(b'>3L')
    vendor_id = os2_table[offset:offset+4]
    vendor_id
    offset += 4
    selection, = struct.unpack_from(b'>H', os2_table, offset)

    is_italic = (selection & (1 << 0)) != 0
    is_bold = (selection & (1 << 5)) != 0
    is_regular = (selection & (1 << 6)) != 0
    is_wws = (selection & (1 << 8)) != 0
    is_oblique = (selection & (1 << 9)) != 0
    if return_all:
        return (version, char_width, weight, width, fs_type, subscript_x_size,
            subscript_y_size, subscript_x_offset, subscript_y_offset,
            superscript_x_size, superscript_y_size, superscript_x_offset,
            superscript_y_offset, strikeout_size, strikeout_position,
            family_class, panose, selection, is_italic, is_bold, is_regular)

    return weight, is_italic, is_bold, is_regular, fs_type, panose, width, is_oblique, is_wws, version

def panose_to_css_generic_family(panose):
    proportion = panose[3]
    if proportion == 9:
        return 'monospace'
    family_type = panose[0]
    if family_type == 3:
        return 'cursive'
    if family_type == 4:
        return 'fantasy'
    serif_style = panose[1]
    if serif_style in (11, 12, 13):
        return 'sans-serif'
    return 'serif'

def decode_name_record(recs):
    '''
    Get the English names of this font. See
    http://www.microsoft.com/typography/otspec/name.htm for details.
    '''
    if not recs: return None
    unicode_names = {}
    windows_names = {}
    mac_names = {}
    for platform_id, encoding_id, language_id, src in recs:
        if language_id > 0x8000: continue
        if platform_id == 0:
            if encoding_id < 4:
                try:
                    unicode_names[language_id] = src.decode('utf-16-be')
                except ValueError:
                    continue
        elif platform_id == 1:
            try:
                mac_names[language_id] = src.decode('utf-8')
            except ValueError:
                continue
        elif platform_id == 2:
            codec = {0:'ascii', 1:'utf-16-be', 2:'iso-8859-1'}.get(encoding_id,
                    None)
            if codec is None: continue
            try:
                unicode_names[language_id] = src.decode(codec)
            except ValueError:
                continue
        elif platform_id == 3:
            codec = {1:16, 10:32}.get(encoding_id, None)
            if codec is None: continue
            try:
                windows_names[language_id] = src.decode('utf-%d-be'%codec)
            except ValueError:
                continue

    # First try the windows names
    # First look for the US English name
    if 1033 in windows_names:
        return windows_names[1033]
    # Look for some other english name variant
    for lang in (3081, 10249, 4105, 9225, 16393, 6153, 8201, 17417, 5129,
            13321, 18441, 7177, 11273, 2057, 12297):
        if lang in windows_names:
            return windows_names[lang]

    # Look for Mac name
    if 0 in mac_names:
        return mac_names[0]

    # Use unicode names
    for val in unicode_names.itervalues():
        return val

    return None

def _get_font_names(raw, raw_is_table=False):
    if raw_is_table:
        table = raw
    else:
        table = get_table(raw, 'name')[0]
        if table is None:
            raise UnsupportedFont('Not a supported font, has no name table')
    table_type, count, string_offset = struct.unpack_from(b'>3H', table)

    records = defaultdict(list)

    for i in xrange(count):
        try:
            platform_id, encoding_id, language_id, name_id, length, offset = \
                    struct.unpack_from(b'>6H', table, 6+i*12)
        except struct.error:
            break
        offset += string_offset
        src = table[offset:offset+length]
        records[name_id].append((platform_id, encoding_id, language_id,
            src))

    return records

def get_font_names(raw, raw_is_table=False):
    records = _get_font_names(raw, raw_is_table)
    family_name = decode_name_record(records[1])
    subfamily_name = decode_name_record(records[2])
    full_name = decode_name_record(records[4])

    return family_name, subfamily_name, full_name

def get_font_names2(raw, raw_is_table=False):
    records = _get_font_names(raw, raw_is_table)

    family_name = decode_name_record(records[1])
    subfamily_name = decode_name_record(records[2])
    full_name = decode_name_record(records[4])

    preferred_family_name = decode_name_record(records[16])
    preferred_subfamily_name = decode_name_record(records[17])

    wws_family_name = decode_name_record(records[21])
    wws_subfamily_name = decode_name_record(records[22])

    return (family_name, subfamily_name, full_name, preferred_family_name,
            preferred_subfamily_name, wws_family_name, wws_subfamily_name)

def get_all_font_names(raw, raw_is_table=False):
    records = _get_font_names(raw, raw_is_table)
    ans = {}

    for name, num in {'family_name':1, 'subfamily_name':2, 'full_name':4,
            'preferred_family_name':16, 'preferred_subfamily_name':17,
            'wws_family_name':21, 'wws_subfamily_name':22}.iteritems():
        try:
            ans[name] = decode_name_record(records[num])
        except (IndexError, KeyError, ValueError):
            continue
        if not ans[name]:
            del ans[name]

    for platform_id, encoding_id, language_id, src in records[6]:
        if (platform_id, encoding_id, language_id) == (1, 0, 0):
            try:
                ans['postscript_name'] = src.decode('utf-8')
                break
            except ValueError:
                continue
        elif (platform_id, encoding_id, language_id) == (3, 1, 1033):
            try:
                ans['postscript_name'] = src.decode('utf-16-be')
                break
            except ValueError:
                continue

    return ans

def checksum_of_block(raw):
    extra = 4 - len(raw)%4
    raw += b'\0'*extra
    num = len(raw)//4
    return sum(struct.unpack(b'>%dI'%num, raw)) % (1<<32)

def verify_checksums(raw):
    head_table = None
    for table_tag, table, table_index, table_offset, table_checksum in get_tables(raw):
        if table_tag.lower() == b'head':
            version, fontrev, checksum_adj = struct.unpack_from(b'>ffL', table)
            head_table = table
            offset = table_offset
            checksum = table_checksum
        elif checksum_of_block(table) != table_checksum:
            raise ValueError('The %r table has an incorrect checksum'%table_tag)

    if head_table is not None:
        table = head_table
        table = table[:8] + struct.pack(b'>I', 0) + table[12:]
        raw = raw[:offset] + table + raw[offset+len(table):]
        # Check the checksum of the head table
        if checksum_of_block(table) != checksum:
            raise ValueError('Checksum of head table not correct')
        # Check the checksum of the entire font
        checksum = checksum_of_block(raw)
        q = (0xB1B0AFBA - checksum) & 0xffffffff
        if q != checksum_adj:
            raise ValueError('Checksum of entire font incorrect')

def set_checksum_adjustment(f):
    offset = get_table(f.getvalue(), 'head')[2]
    offset += 8
    f.seek(offset)
    f.write(struct.pack(b'>I', 0))
    checksum = checksum_of_block(f.getvalue())
    q = (0xB1B0AFBA - checksum) & 0xffffffff
    f.seek(offset)
    f.write(struct.pack(b'>I', q))

def set_table_checksum(f, name):
    table, table_index, table_offset, table_checksum = get_table(f.getvalue(), name)
    checksum = checksum_of_block(table)
    if checksum != table_checksum:
        f.seek(table_index + 4)
        f.write(struct.pack(b'>I', checksum))

def remove_embed_restriction(raw):
    ok, sig = is_truetype_font(raw)
    if not ok:
        raise UnsupportedFont('Not a supported font, sfnt_version: %r'%sig)

    table, table_index, table_offset = get_table(raw, 'os/2')[:3]
    if table is None:
        raise UnsupportedFont('Not a supported font, has no OS/2 table')

    fs_type_offset = struct.calcsize(b'>HhHH')
    fs_type = struct.unpack_from(b'>H', table, fs_type_offset)[0]
    if fs_type == 0:
        return raw

    f = BytesIO(raw)
    f.seek(fs_type_offset + table_offset)
    f.write(struct.pack(b'>H', 0))

    set_table_checksum(f, 'os/2')
    set_checksum_adjustment(f)
    raw = f.getvalue()
    verify_checksums(raw)
    return raw

def get_bmp_glyph_ids(table, bmp, codes):
    length, language, segcount = struct.unpack_from(b'>3H', table, bmp+2)
    array_len = segcount //2
    offset = bmp + 7*2
    array_sz = 2*array_len
    array = b'>%dH'%array_len
    end_count = struct.unpack_from(array, table, offset)
    offset += array_sz + 2
    start_count = struct.unpack_from(array, table, offset)
    offset += array_sz
    id_delta = struct.unpack_from(array.replace(b'H', b'h'), table, offset)
    offset += array_sz
    range_offset = struct.unpack_from(array, table, offset)
    if length + bmp < offset + array_sz:
        raise ValueError('cmap subtable length is too small')
    glyph_id_len = (length + bmp - (offset + array_sz))//2
    glyph_id_map = struct.unpack_from(b'>%dH'%glyph_id_len, table, offset +
            array_sz)

    for code in codes:
        found = False
        for i, ec in enumerate(end_count):
            if ec >= code:
                sc = start_count[i]
                if sc <= code:
                    found = True
                    ro = range_offset[i]
                    if ro == 0:
                        glyph_id = id_delta[i] + code
                    else:
                        idx = ro//2 + (code - sc) + i - array_len
                        glyph_id = glyph_id_map[idx]
                        if glyph_id != 0:
                            glyph_id += id_delta[i]
                    yield glyph_id % 0x1000
                    break
        if not found:
            yield 0

def get_glyph_ids(raw, text, raw_is_table=False):
    if not isinstance(text, unicode):
        raise TypeError('%r is not a unicode object'%text)
    if raw_is_table:
        table = raw
    else:
        table = get_table(raw, 'cmap')[0]
        if table is None:
            raise UnsupportedFont('Not a supported font, has no cmap table')
    version, num_tables = struct.unpack_from(b'>HH', table)
    bmp_table = None
    for i in xrange(num_tables):
        platform_id, encoding_id, offset = struct.unpack_from(b'>HHL', table,
                4 + (i*8))
        if platform_id == 3 and encoding_id == 1:
            table_format = struct.unpack_from(b'>H', table, offset)[0]
            if table_format == 4:
                bmp_table = offset
                break
    if bmp_table is None:
        raise UnsupportedFont('Not a supported font, has no format 4 cmap table')

    for glyph_id in get_bmp_glyph_ids(table, bmp_table, map(ord, text)):
        yield glyph_id

def supports_text(raw, text, has_only_printable_chars=False):
    if not isinstance(text, unicode):
        raise TypeError('%r is not a unicode object'%text)
    if not has_only_printable_chars:
        text = get_printable_characters(text)
    try:
        for glyph_id in get_glyph_ids(raw, text):
            if glyph_id == 0:
                return False
    except:
        return False
    return True

def get_font_for_text(text, candidate_font_data=None):
    ok = False
    if candidate_font_data is not None:
        ok = supports_text(candidate_font_data, text)
    if not ok:
        from calibre.utils.fonts.scanner import font_scanner
        family, faces = font_scanner.find_font_for_text(text)
        if faces:
            with lopen(faces[0]['path'], 'rb') as f:
                candidate_font_data = f.read()
    return candidate_font_data

def test_glyph_ids():
    from calibre.utils.fonts.free_type import FreeType
    data = P('fonts/liberation/LiberationSerif-Regular.ttf', data=True)
    ft = FreeType()
    font = ft.load_font(data)
    text = u'诶йab'
    ft_glyphs = tuple(font.glyph_ids(text))
    glyphs = tuple(get_glyph_ids(data, text))
    if ft_glyphs != glyphs:
        raise Exception('My code and FreeType differ on the glyph ids')

def test_supports_text():
    data = P('fonts/calibreSymbols.otf', data=True)
    if not supports_text(data, '.\u2605★'):
        raise RuntimeError('Incorrectly returning that text is not supported')
    if supports_text(data, 'abc'):
        raise RuntimeError('Incorrectly claiming that text is supported')

def test_find_font():
    from calibre.utils.fonts.scanner import font_scanner
    abcd = '诶比西迪'
    family = font_scanner.find_font_for_text(abcd)[0]
    print ('Family for Chinese text:', family)
    family = font_scanner.find_font_for_text(abcd)[0]
    abcd = 'لوحة المفاتيح العربية'
    print ('Family for Arabic text:', family)


def test():
    test_glyph_ids()
    test_supports_text()
    test_find_font()

def main():
    import sys, os
    for f in sys.argv[1:]:
        print (os.path.basename(f))
        raw = open(f, 'rb').read()
        print (get_font_names(raw))
        characs = get_font_characteristics(raw)
        print (characs)
        print (panose_to_css_generic_family(characs[5]))
        verify_checksums(raw)
        remove_embed_restriction(raw)


if __name__ == '__main__':
    main()

