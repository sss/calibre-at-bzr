##    Copyright (C) 2008 Kovid Goyal kovid@kovidgoyal.net
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
'''
Used to run jobs in parallel in separate processes.
'''
import re, sys, tempfile, os, subprocess, cPickle, cStringIO, traceback, atexit, time, binascii
from functools import partial
from libprs500.ebooks.lrf.any.convert_from import main as any2lrf
from libprs500.ebooks.lrf.web.convert_from import main as web2lrf
from libprs500.gui2.lrf_renderer.main import main as lrfviewer
from libprs500 import iswindows, __appname__

PARALLEL_FUNCS = {
                  'any2lrf'   : partial(any2lrf, gui_mode=True),
                  'web2lrf'   : web2lrf,
                  'lrfviewer' : lrfviewer,
                  }
Popen = subprocess.Popen

python = sys.executable
if iswindows:
    import win32con
    Popen = partial(Popen, creationflags=win32con.CREATE_NO_WINDOW)
    if hasattr(sys, 'frozen'):
        python = os.path.join(os.path.dirname(python), 'parallel.exe')
    else:
        python = os.path.join(os.path.dirname(python), 'Scripts\\parallel.exe')

def cleanup(tdir):
    try:
        import shutil
        shutil.rmtree(tdir, True)
    except:
        pass

class Server(object):
    
    #: Interval in seconds at which child processes are polled for status information
    INTERVAL = 0.1
    KILL_RESULT = 'Server: job killed by user|||#@#$%&*)*(*$#$%#$@&'
    
    def __init__(self):
        self.tdir = tempfile.mkdtemp('', '%s_IPC_'%__appname__)
        atexit.register(cleanup, self.tdir)
        self.stdout = {}
        self.kill_jobs = []
        
    def kill(self, job_id):
        '''
        Kill the job identified by job_id.
        '''
        self.kill_jobs.append(str(job_id))
        
    def _terminate(self, pid):
        '''
        Kill process identified by C{pid}.
        @param pid: On unix a process number, on windows a process handle.
        '''
        if iswindows:
            import win32api
            try:
                win32api.TerminateProcess(int(pid), -1)
            except:
                pass
        else:
            import signal
            try:
                try:
                    os.kill(pid, signal.SIGTERM)
                finally:
                    time.sleep(2)
                    os.kill(pid, signal.SIGKILL)                    
            except:
                pass
    
    def run(self, job_id, func, args=[], kwdargs={}, monitor=True):
        '''
        Run a job in a separate process.
        @param job_id: A unique (per server) identifier
        @param func: One of C{PARALLEL_FUNCS.keys()}
        @param args: A list of arguments to pass of C{func}
        @param kwdargs: A dictionary of keyword arguments to pass to C{func}
        @param monitor: If False launch the child process and return. Do not monitor/communicate with it.
        @return: (result, exception, formatted_traceback, log) where log is the combined
        stdout + stderr of the child process; or None if monitor is True. If a job is killed
        by a call to L{kill()} then result will be L{KILL_RESULT}
        '''
        job_id = str(job_id)
        job_dir = os.path.join(self.tdir, job_id)
        if os.path.exists(job_dir):
            raise ValueError('Cannot run job. The job_id %s has already been used.'%job_id)
        os.mkdir(job_dir)
        self.stdout[job_id] = cStringIO.StringIO()
        
        job_data = os.path.join(job_dir, 'job_data.pickle')
        cPickle.dump((func, args, kwdargs), open(job_data, 'wb'), -1)
        prefix = ''
        if hasattr(sys, 'frameworks_dir'):
            fd = getattr(sys, 'frameworks_dir')
            prefix = 'import sys; sys.frameworks_dir = "%s"; sys.frozen = "macosx_app"; '%fd
            if fd not in os.environ['PATH']:
                os.environ['PATH'] += ':'+fd
        cmd = prefix + 'from libprs500.parallel import run_job; run_job(\'%s\')'%binascii.hexlify(job_data)
        
        if monitor:
            p = Popen((python, '-c', cmd), stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        else:
            Popen((python, '-c', cmd))
            return 
        while p.returncode is None:
            if job_id in self.kill_jobs:
                self._terminate(p._handle if iswindows else p.pid)
                return self.KILL_RESULT, None, None, _('Job killed by user') 
            p.poll()
            time.sleep(0.5) # Wait for half a second
        self.stdout[job_id].write(p.stdout.read())
        
        job_result = os.path.join(job_dir, 'job_result.pickle')
        if not os.path.exists(job_result):
            result, exception, traceback = None, ('ParallelRuntimeError', 
                                                  'The worker process died unexpectedly.'), ''
        else:              
            result, exception, traceback = cPickle.load(open(job_result, 'rb'))
        log = self.stdout[job_id].getvalue()
        self.stdout.pop(job_id)
        return result, exception, traceback, log
            
    
def run_job(job_data):
    job_data = binascii.unhexlify(job_data)
    job_result = os.path.join(os.path.dirname(job_data), 'job_result.pickle')
    func, args, kwdargs = cPickle.load(open(job_data, 'rb'))
    func = PARALLEL_FUNCS[func]
    exception, tb = None, None
    try:
        result = func(*args, **kwdargs)
    except (Exception, SystemExit), err:
        result = None
        exception = (err.__class__.__name__, unicode(str(err), 'utf-8', 'replace'))
        tb = traceback.format_exc()
    
    if os.path.exists(os.path.dirname(job_result)):
        cPickle.dump((result, exception, tb), open(job_result, 'wb'))
    
def main():
    src = sys.argv[2]
    job_data = re.search(r'run_job\(\'([a-f0-9A-F]+)\'\)', src).group(1)
    run_job(job_data)
    
    return 0
    
if __name__ == '__main__':
    sys.exit(main())