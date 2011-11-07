#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os, dbus

def node_mountpoint(node):

    def de_mangle(raw):
        return raw.replace('\\040', ' ').replace('\\011', '\t').replace('\\012',
                '\n').replace('\\0134', '\\')

    for line in open('/proc/mounts').readlines():
        line = line.split()
        if line[0] == node:
            return de_mangle(line[1])
    return None


class UDisks(object):

    def __init__(self):
        self.bus = dbus.SystemBus()
        self.main = dbus.Interface(self.bus.get_object('org.freedesktop.UDisks',
                        '/org/freedesktop/UDisks'), 'org.freedesktop.UDisks')

    def device(self, device_node_path):
        devpath = self.main.FindDeviceByDeviceFile(device_node_path)
        return dbus.Interface(self.bus.get_object('org.freedesktop.UDisks',
                        devpath), 'org.freedesktop.UDisks.Device')

    def mount(self, device_node_path):
        d = self.device(device_node_path)
        try:
            return unicode(d.FilesystemMount('',
                ['auth_no_user_interaction', 'rw', 'noexec', 'nosuid',
                'sync', 'nodev', 'uid=%d'%os.geteuid(), 'gid=%d'%os.getegid()]))
        except:
            # May be already mounted, check
            mp = node_mountpoint(str(device_node_path))
            if mp is None:
                raise
            return mp

    def unmount(self, device_node_path):
        d = self.device(device_node_path)
        d.FilesystemUnmount(['force'])

    def eject(self, device_node_path):
        parent = device_node_path
        while parent[-1] in '0123456789':
            parent = parent[:-1]
        d = self.device(parent)
        d.DriveEject([])

def mount(node_path):
    u = UDisks()
    u.mount(node_path)

def eject(node_path):
    u = UDisks()
    u.eject(node_path)

def umount(node_path):
    u = UDisks()
    u.unmount(node_path)

if __name__ == '__main__':
    import sys
    dev = sys.argv[1]
    print 'Testing with node', dev
    u = UDisks()
    print 'Mounted at:', u.mount(dev)
    print 'Unmounting'
    u.unmount(dev)
    print 'Ejecting:'
    u.eject(dev)


