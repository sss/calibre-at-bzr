'''
Make strings safe for use as ASCII filenames, while trying to preserve as much
meaning as possible.
'''

import os, errno
from math import ceil

from calibre import sanitize_file_name, isbytestring, force_unicode
from calibre.constants import (preferred_encoding, iswindows,
        filesystem_encoding)
from calibre.utils.localization import get_udc

def ascii_text(orig):
    udc = get_udc()
    try:
        ascii = udc.decode(orig)
    except:
        if isinstance(orig, unicode):
            orig = orig.encode('ascii', 'replace')
        ascii = orig.decode(preferred_encoding,
                'replace').encode('ascii', 'replace')
    return ascii


def ascii_filename(orig, substitute='_'):
    ans = []
    orig = ascii_text(orig).replace('?', '_')
    for x in orig:
        if ord(x) < 32:
            x = substitute
        ans.append(x)
    return sanitize_file_name(''.join(ans), substitute=substitute)

def supports_long_names(path):
    t = ('a'*300)+'.txt'
    try:
        p = os.path.join(path, t)
        open(p, 'wb').close()
        os.remove(p)
    except:
        return False
    else:
        return True

def shorten_component(s, by_what):
    l = len(s)
    if l < by_what:
        return s
    l = (l - by_what)//2
    if l <= 0:
        return s
    return s[:l] + s[-l:]

def shorten_components_to(length, components, more_to_take=0):
    filepath = os.sep.join(components)
    extra = len(filepath) - (length - more_to_take)
    if extra < 1:
        return components
    deltas = []
    for x in components:
        pct = len(x)/float(len(filepath))
        deltas.append(int(ceil(pct*extra)))
    ans = []

    for i, x in enumerate(components):
        delta = deltas[i]
        if delta > len(x):
            r = x[0] if x is components[-1] else ''
        else:
            if x is components[-1]:
                b, e = os.path.splitext(x)
                if e == '.': e = ''
                r = shorten_component(b, delta)+e
                if r.startswith('.'): r = x[0]+r
            else:
                r = shorten_component(x, delta)
            r = r.strip()
            if not r:
                r = x.strip()[0] if x.strip() else 'x'
        ans.append(r)
    if len(os.sep.join(ans)) > length:
        return shorten_components_to(length, components, more_to_take+2)
    return ans

def find_executable_in_path(name, path=None):
    if path is None:
        path = os.environ.get('PATH', '')
    sep = ';' if iswindows else ':'
    if iswindows and not name.endswith('.exe'):
        name += '.exe'
    path = path.split(sep)
    for x in path:
        q = os.path.abspath(os.path.join(x, name))
        if os.access(q, os.X_OK):
            return q

def is_case_sensitive(path):
    '''
    Return True if the filesystem is case sensitive.

    path must be the path to an existing directory. You must have permission
    to create and delete files in this directory. The results of this test
    apply to the filesystem containing the directory in path.
    '''
    is_case_sensitive = False
    if not iswindows:
        name1, name2 = ('calibre_test_case_sensitivity.txt',
                        'calibre_TesT_CaSe_sensitiVitY.Txt')
        f1, f2 = os.path.join(path, name1), os.path.join(path, name2)
        if os.path.exists(f1):
            os.remove(f1)
        open(f1, 'w').close()
        is_case_sensitive = not os.path.exists(f2)
        os.remove(f1)
    return is_case_sensitive

def case_preserving_open_file(path, mode='wb', mkdir_mode=0777):
    '''
    Open the file pointed to by path with the specified mode. If any
    directories in path do not exist, they are created. Returns the
    opened file object and the path to the opened file object. This path is
    guaranteed to have the same case as the on disk path. For case insensitive
    filesystems, the returned path may be different from the passed in path.
    The returned path is always unicode and always an absolute path.

    If mode is None, then this function assumes that path points to a directory
    and return the path to the directory as the file object.

    mkdir_mode specifies the mode with which any missing directories in path
    are created.
    '''
    if isbytestring(path):
        path = path.decode(filesystem_encoding)

    path = os.path.abspath(path)

    sep = force_unicode(os.sep, 'ascii')

    if path.endswith(sep):
        path = path[:-1]
    if not path:
        raise ValueError('Path must not point to root')

    components = path.split(sep)
    if not components:
        raise ValueError('Invalid path: %r'%path)

    cpath = sep
    if iswindows:
        # Always upper case the drive letter and add a trailing slash so that
        # the first os.listdir works correctly
        cpath = components[0].upper() + sep

    bdir = path if mode is None else os.path.dirname(path)
    if not os.path.exists(bdir):
        os.makedirs(bdir, mkdir_mode)

    # Walk all the directories in path, putting the on disk case version of
    # the directory into cpath
    dirs = components[1:] if mode is None else components[1:-1]
    for comp in dirs:
        cdir = os.path.join(cpath, comp)
        cl = comp.lower()
        try:
            candidates = [c for c in os.listdir(cpath) if c.lower() == cl]
        except:
            # Dont have permission to do the listdir, assume the case is
            # correct as we have no way to check it.
            pass
        else:
            if len(candidates) == 1:
                cdir = os.path.join(cpath, candidates[0])
            # else: We are on a case sensitive file system so cdir must already
            # be correct
        cpath = cdir

    if mode is None:
        ans = fpath = cpath
    else:
        fname = components[-1]
        ans = open(os.path.join(cpath, fname), mode)
        # Ensure file and all its metadata is written to disk so that subsequent
        # listdir() has file name in it. I don't know if this is actually
        # necessary, but given the diversity of platforms, best to be safe.
        ans.flush()
        os.fsync(ans.fileno())

        cl = fname.lower()
        try:
            candidates = [c for c in os.listdir(cpath) if c.lower() == cl]
        except EnvironmentError:
            # The containing directory, somehow disappeared?
            candidates = []
        if len(candidates) == 1:
            fpath = os.path.join(cpath, candidates[0])
        else:
            # We are on a case sensitive filesystem
            fpath = os.path.join(cpath, fname)
    return ans, fpath

def samefile_windows(src, dst):
    import win32file
    from pywintypes import error

    samestring = (os.path.normcase(os.path.abspath(src)) ==
            os.path.normcase(os.path.abspath(dst)))
    if samestring:
        return True

    handles = []

    def get_fileid(x):
        if isbytestring(x): x = x.decode(filesystem_encoding)
        try:
            h = win32file.CreateFile(x, 0, 0, None, win32file.OPEN_EXISTING,
                    win32file.FILE_FLAG_BACKUP_SEMANTICS, 0)
            handles.append(h)
            data = win32file.GetFileInformationByHandle(h)
        except (error, EnvironmentError):
            return None
        return (data[4], data[8], data[9])

    a, b = get_fileid(src), get_fileid(dst)
    for h in handles:
        win32file.CloseHandle(h)
    if a is None and b is None:
        return False
    return a == b

def samefile(src, dst):
    '''
    Check if two paths point to the same actual file on the filesystem. Handles
    symlinks, case insensitivity, mapped drives, etc.

    Returns True iff both paths exist and point to the same file on disk.

    Note: On windows will return True if the two string are identical (upto
    case) even if the file does not exist. This is because I have no way of
    knowing how reliable the GetFileInformationByHandle method is.
    '''
    if iswindows:
        return samefile_windows(src, dst)

    if hasattr(os.path, 'samefile'):
        # Unix
        try:
            return os.path.samefile(src, dst)
        except EnvironmentError:
            return False

    # All other platforms: check for same pathname.
    samestring = (os.path.normcase(os.path.abspath(src)) ==
            os.path.normcase(os.path.abspath(dst)))
    return samestring

class WindowsAtomicFolderMove(object):

    '''
    Move all the files inside a specified folder in an atomic fashion,
    preventing any other process from locking a file while the operation is
    incomplete. Raises an IOError if another process has locked a file before
    the operation starts. Note that this only operates on the files in the
    folder, not any sub-folders.
    '''

    def __init__(self, path):
        self.handle_map = {}

        import win32file, winerror
        from pywintypes import error

        if isbytestring(path): path = path.decode(filesystem_encoding)

        if not os.path.exists(path):
            return

        for x in os.listdir(path):
            f = os.path.normcase(os.path.abspath(os.path.join(path, x)))
            if not os.path.isfile(f): continue
            try:
                # Ensure the file is not read-only
                win32file.SetFileAttributes(f, win32file.FILE_ATTRIBUTE_NORMAL)
            except:
                pass

            try:
                h = win32file.CreateFile(f, win32file.GENERIC_READ,
                        win32file.FILE_SHARE_DELETE, None,
                        win32file.OPEN_EXISTING, win32file.FILE_FLAG_SEQUENTIAL_SCAN, 0)
            except error as e:
                self.close_handles()
                if getattr(e, 'winerror', 0) == winerror.ERROR_SHARING_VIOLATION:
                    err = IOError(errno.EACCES,
                            _('File is open in another process'))
                    err.filename = f
                    raise err
                raise
            except:
                self.close_handles()
                raise
            self.handle_map[f] = h

    def copy_path_to(self, path, dest):
        import win32file
        handle = None
        for p, h in self.handle_map.iteritems():
            if samefile_windows(path, p):
                handle = h
                break
        if handle is None:
            if os.path.exists(path):
                raise ValueError(u'The file %r did not exist when this move'
                        ' operation was started'%path)
            else:
                raise ValueError(u'The file %r does not exist'%path)
        try:
            win32file.CreateHardLink(dest, path)
            if os.path.getsize(dest) != os.path.getsize(path):
                raise Exception('This apparently can happen on network shares. Sigh.')
            return
        except:
            pass
        with lopen(dest, 'wb') as f:
            while True:
                hr, raw = win32file.ReadFile(handle, 1024*1024)
                if hr != 0:
                    raise IOError(hr, u'Error while reading from %r'%path)
                if not raw:
                    break
                f.write(raw)

    def release_file(self, path):
        key = None
        for p, h in self.handle_map.iteritems():
            if samefile_windows(path, p):
                key = (p, h)
                break
        if key is not None:
            import win32file
            win32file.CloseHandle(key[1])
            self.handle_map.pop(key[0])

    def close_handles(self):
        import win32file
        for h in self.handle_map.itervalues():
            win32file.CloseHandle(h)
        self.handle_map = {}

    def delete_originals(self):
        import win32file
        for path in self.handle_map.iterkeys():
            win32file.DeleteFile(path)
        self.close_handles()

def hardlink_file(src, dest):
    if iswindows:
        import win32file
        win32file.CreateHardLink(dest, src)
        if os.path.getsize(dest) != os.path.getsize(src):
            raise Exception('This apparently can happen on network shares. Sigh.')
        return
    os.link(src, dest)

