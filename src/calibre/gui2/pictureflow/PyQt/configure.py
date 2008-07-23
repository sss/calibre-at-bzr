import os, sys
import sipconfig
if os.environ.get('PYQT4PATH', None):
    print os.environ['PYQT4PATH']
    sys.path.insert(0, os.environ['PYQT4PATH'])
from PyQt4 import pyqtconfig

# The name of the SIP build file generated by SIP and used by the build
# system.
build_file = "pictureflow.sbf"

# Get the PyQt configuration information.
config = pyqtconfig.Configuration()

# Run SIP to generate the code.  Note that we tell SIP where to find the qt
# module's specification files using the -I flag.
sip = [config.sip_bin, "-c", ".", "-b", build_file, "-I",
       config.pyqt_sip_dir, config.pyqt_sip_flags, "../pictureflow.sip"]
os.system(" ".join(sip))



installs=[]

# Create the Makefile.  The QtModuleMakefile class provided by the
# pyqtconfig module takes care of all the extra preprocessor, compiler and
# linker flags needed by the Qt library.
makefile = pyqtconfig.QtGuiModuleMakefile (
    configuration=config,
    build_file=build_file,
    installs=installs,
    qt=1,
)

# Add the library we are wrapping.  The name doesn't include any platform
# specific prefixes or extensions (e.g. the "lib" prefix on UNIX, or the
# ".dll" extension on Windows).
d = os.path.dirname
makefile.extra_lib_dirs += [os.path.abspath(os.path.join(d(d(d(d(os.getcwd())))), 'plugins')).replace(os.sep, '/')]
makefile.extra_libs += ['pictureflow1' if 'win32' in sys.platform else 'pictureflow']
makefile.extra_cflags = ['-arch i386', '-arch ppc'] if 'darwin' in sys.platform else []
makefile.extra_lflags = ['-arch i386', '-arch ppc'] if 'darwin' in sys.platform else []
makefile.extra_cxxflags = makefile.extra_cflags
if 'win32' in sys.platform:
    makefile.extra_lib_dirs += ['C:/Python25/libs']

# Generate the Makefile itself.
makefile.generate()

# Now we create the configuration module.  This is done by merging a Python
# dictionary (whose values are normally determined dynamically) with a
# (static) template.
content = {
    # Publish where the SIP specifications for this module will be
    # installed.
    "pictureflow_sip_dir":    config.default_sip_dir,
}

# This creates the helloconfig.py module from the helloconfig.py.in
# template and the dictionary.
sipconfig.create_config_module("pictureflowconfig.py", '..'+os.sep+'pictureflowconfig.py.in', content)


