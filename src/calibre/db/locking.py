#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2011, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from threading import Lock, Condition, current_thread

class LockingError(RuntimeError):
    pass

def create_locks():
    '''
    Return a pair of locks: (read_lock, write_lock)

    The read_lock can be acquired by multiple threads simultaneously, it can
    also be acquired multiple times by the same thread.

    Only one thread can hold write_lock at a time, and only if there are no
    current read_locks. While the write_lock is held no
    other threads can acquire read locks. The write_lock can also be acquired
    multiple times by the same thread.

    Both read_lock and write_lock are meant to be used in with statements (they
    operate on a single underlying lock.

    WARNING: Be very careful to not try to acquire a read lock while the same
    thread holds a write lock and vice versa. That is, a given thread should
    always release *all* locks of type A before trying to acquire a lock of type
    B. Bad things will happen if you violate this rule, the most benign of
    which is the raising of a LockingError (I haven't been able to eliminate
    the possibility of deadlocking in this scenario).
    '''
    l = SHLock()
    return RWLockWrapper(l), RWLockWrapper(l, is_shared=False)

class SHLock(object):
    '''
    Shareable lock class. Used to implement the Multiple readers-single writer
    paradigm. As best as I can tell, neither writer nor reader starvation
    should be possible.

    Based on code from: https://github.com/rfk/threading2
    '''

    def __init__(self):
        self._lock = Lock()
        #  When a shared lock is held, is_shared will give the cumulative
        #  number of locks and _shared_owners maps each owning thread to
        #  the number of locks is holds.
        self.is_shared = 0
        self._shared_owners = {}
        #  When an exclusive lock is held, is_exclusive will give the number
        #  of locks held and _exclusive_owner will give the owning thread
        self.is_exclusive = 0
        self._exclusive_owner = None
        #  When someone is forced to wait for a lock, they add themselves
        #  to one of these queues along with a "waiter" condition that
        #  is used to wake them up.
        self._shared_queue = []
        self._exclusive_queue = []
        #  This is for recycling waiter objects.
        self._free_waiters = []

    def acquire(self, blocking=True, shared=False):
        '''
        Acquire the lock in shared or exclusive mode.

        If blocking is False this method will return False if acquiring the
        lock failed.
        '''
        with self._lock:
            if shared:
                return self._acquire_shared(blocking)
            else:
                return self._acquire_exclusive(blocking)
            assert not (self.is_shared and self.is_exclusive)

    def release(self):
        ''' Release the lock. '''
        #  This decrements the appropriate lock counters, and if the lock
        #  becomes free, it looks for a queued thread to hand it off to.
        #  By doing the handoff here we ensure fairness.
        me = current_thread()
        with self._lock:
            if self.is_exclusive:
                if self._exclusive_owner is not me:
                    raise LockingError("release() called on unheld lock")
                self.is_exclusive -= 1
                if not self.is_exclusive:
                    self._exclusive_owner = None
                    #  If there are waiting shared locks, issue them
                    #  all and them wake everyone up.
                    if self._shared_queue:
                        for (thread, waiter) in self._shared_queue:
                            self.is_shared += 1
                            self._shared_owners[thread] = 1
                            waiter.notify()
                        del self._shared_queue[:]
                    #  Otherwise, if there are waiting exclusive locks,
                    #  they get first dibbs on the lock.
                    elif self._exclusive_queue:
                        (thread, waiter) = self._exclusive_queue.pop(0)
                        self._exclusive_owner = thread
                        self.is_exclusive += 1
                        waiter.notify()
            elif self.is_shared:
                try:
                    self._shared_owners[me] -= 1
                    if self._shared_owners[me] == 0:
                        del self._shared_owners[me]
                except KeyError:
                    raise LockingError("release() called on unheld lock")
                self.is_shared -= 1
                if not self.is_shared:
                    #  If there are waiting exclusive locks,
                    #  they get first dibbs on the lock.
                    if self._exclusive_queue:
                        (thread, waiter) = self._exclusive_queue.pop(0)
                        self._exclusive_owner = thread
                        self.is_exclusive += 1
                        waiter.notify()
                    else:
                        assert not self._shared_queue
            else:
                raise LockingError("release() called on unheld lock")

    def _acquire_shared(self, blocking=True):
        me = current_thread()
        #  Each case: acquiring a lock we already hold.
        if self.is_shared and me in self._shared_owners:
            self.is_shared += 1
            self._shared_owners[me] += 1
            return True
        #  If the lock is already spoken for by an exclusive, add us
        #  to the shared queue and it will give us the lock eventually.
        if self.is_exclusive or self._exclusive_queue:
            if self._exclusive_owner is me:
                raise LockingError("can't downgrade SHLock object")
            if not blocking:
                return False
            waiter = self._take_waiter()
            try:
                self._shared_queue.append((me, waiter))
                waiter.wait()
                assert not self.is_exclusive
            finally:
                self._return_waiter(waiter)
        else:
            self.is_shared += 1
            self._shared_owners[me] = 1
        return True

    def _acquire_exclusive(self, blocking=True):
        me = current_thread()
        #  Each case: acquiring a lock we already hold.
        if self._exclusive_owner is me:
            assert self.is_exclusive
            self.is_exclusive += 1
            return True
        # Do not allow upgrade of lock
        if self.is_shared and me in self._shared_owners:
            raise LockingError("can't upgrade SHLock object")
        #  If the lock is already spoken for, add us to the exclusive queue.
        #  This will eventually give us the lock when it's our turn.
        if self.is_shared or self.is_exclusive:
            if not blocking:
                return False
            waiter = self._take_waiter()
            try:
                self._exclusive_queue.append((me, waiter))
                waiter.wait()
            finally:
                self._return_waiter(waiter)
        else:
            self._exclusive_owner = me
            self.is_exclusive += 1
        return True

    def _take_waiter(self):
        try:
            return self._free_waiters.pop()
        except IndexError:
            return Condition(self._lock)#, verbose=True)

    def _return_waiter(self, waiter):
        self._free_waiters.append(waiter)

class RWLockWrapper(object):

    def __init__(self, shlock, is_shared=True):
        self._shlock = shlock
        self._is_shared = is_shared

    def __enter__(self):
        self._shlock.acquire(shared=self._is_shared)
        return self

    def __exit__(self, *args):
        self._shlock.release()


# Tests {{{
if __name__ == '__main__':
    import time, random, unittest
    from threading import Thread

    class TestSHLock(unittest.TestCase):
        """Testcases for SHLock class."""

        def test_multithread_deadlock(self):
            lock = SHLock()
            def two_shared():
                lock.acquire(shared=True)
                time.sleep(0.2)
                lock.acquire(blocking=True, shared=True)
                lock.release()
                lock.release()
            def one_exclusive():
                time.sleep(0.1)
                lock.acquire(blocking=True, shared=False)
            threads = [Thread(target=two_shared), Thread(target=one_exclusive)]
            for t in threads:
                t.daemon = True
                t.start()
            for t in threads:
                t.join(5)
            live = [t for t in threads if t.is_alive()]
            self.assertListEqual(live, [], 'ShLock hung')

        def test_upgrade(self):
            lock = SHLock()
            lock.acquire(shared=True)
            self.assertRaises(LockingError, lock.acquire, shared=False)
            lock.release()

        def test_downgrade(self):
            lock = SHLock()
            lock.acquire(shared=False)
            self.assertRaises(LockingError, lock.acquire, shared=True)
            lock.release()

        def test_recursive(self):
            lock = SHLock()
            lock.acquire(shared=True)
            lock.acquire(shared=True)
            self.assertEqual(lock.is_shared, 2)
            lock.release()
            lock.release()
            self.assertFalse(lock.is_shared)
            lock.acquire(shared=False)
            lock.acquire(shared=False)
            self.assertEqual(lock.is_exclusive, 2)
            lock.release()
            lock.release()
            self.assertFalse(lock.is_exclusive)

        def test_release(self):
            lock = SHLock()
            self.assertRaises(LockingError, lock.release)

            def get_lock(shared):
                lock.acquire(shared=shared)
                time.sleep(1)
                lock.release()

            threads = [Thread(target=get_lock, args=(x,)) for x in (True,
                False)]
            for t in threads:
                t.daemon = True
                t.start()
                self.assertRaises(LockingError, lock.release)
                t.join(2)
                self.assertFalse(t.is_alive())
            self.assertFalse(lock.is_shared)
            self.assertFalse(lock.is_exclusive)

        def test_acquire(self):
            lock = SHLock()

            def get_lock(shared):
                lock.acquire(shared=shared)
                time.sleep(1)
                lock.release()

            shared = Thread(target=get_lock, args=(True,))
            shared.daemon = True
            shared.start()
            time.sleep(0.1)
            self.assertTrue(lock.acquire(shared=True, blocking=False))
            lock.release()
            self.assertFalse(lock.acquire(shared=False, blocking=False))
            lock.acquire(shared=False)
            self.assertFalse(shared.is_alive())
            lock.release()
            self.assertTrue(lock.acquire(shared=False, blocking=False))
            lock.release()

            exclusive = Thread(target=get_lock, args=(False,))
            exclusive.daemon = True
            exclusive.start()
            time.sleep(0.1)
            self.assertFalse(lock.acquire(shared=False, blocking=False))
            self.assertFalse(lock.acquire(shared=True, blocking=False))
            lock.acquire(shared=True)
            self.assertFalse(exclusive.is_alive())
            lock.release()
            lock.acquire(shared=False)
            lock.release()
            lock.acquire(shared=True)
            lock.release()
            self.assertFalse(lock.is_shared)
            self.assertFalse(lock.is_exclusive)

        def test_contention(self):
            lock = SHLock()
            done = []
            def lots_of_acquires():
                for _ in xrange(1000):
                    shared = random.choice([True,False])
                    lock.acquire(shared=shared)
                    lock.acquire(shared=shared)
                    time.sleep(random.random() * 0.0001)
                    lock.release()
                    time.sleep(random.random() * 0.0001)
                    lock.acquire(shared=shared)
                    time.sleep(random.random() * 0.0001)
                    lock.release()
                    lock.release()
                done.append(True)
            threads = [Thread(target=lots_of_acquires) for _ in xrange(10)]
            for t in threads:
                t.daemon = True
                t.start()
            for t in threads:
                t.join(20)
            live = [t for t in threads if t.is_alive()]
            self.assertListEqual(live, [], 'ShLock hung')
            self.assertEqual(len(done), len(threads), 'SHLock locking failed')
            self.assertFalse(lock.is_shared)
            self.assertFalse(lock.is_exclusive)


    suite = unittest.TestLoader().loadTestsFromTestCase(TestSHLock)
    unittest.TextTestRunner(verbosity=2).run(suite)

# }}}

