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
__docformat__ = "epytext"
__author__       = "Kovid Goyal <kovid@kovidgoyal.net>"
APP_TITLE         = "libprs500"

import pkg_resources, sys, os, re, StringIO, traceback
from PyQt4 import QtCore, QtGui                    # Needed for classes imported with import_ui
from PyQt4.uic.Compiler import compiler

error_dialog = None

def extension(path):
  return os.path.splitext(path)[1][1:].lower()

def installErrorHandler(dialog):
  global error_dialog
  error_dialog = dialog
  error_dialog.resize(600, 400)
  error_dialog.setWindowTitle(APP_TITLE + " - Error")
  error_dialog.setModal(True)
    

def Warning(msg, e):
  print >> sys.stderr, msg
  traceback.print_exc(e)

def Error(msg, e):  
  if error_dialog:
    if e: msg += "<br>" + traceback.format_exc(e)
    msg = re.sub("Traceback", "<b>Traceback</b>", msg)
    msg = re.sub(r"\n", "<br>", msg)
    error_dialog.showMessage(msg)
    error_dialog.show()

def import_ui(name):
  uifile = pkg_resources.resource_stream(__name__, name)
  code_string = StringIO.StringIO()
  winfo = compiler.UICompiler().compileUi(uifile, code_string)
  ui = pkg_resources.resource_filename(__name__, name)
  exec code_string.getvalue()  
  return locals()[winfo["uiclass"]]

from libprs500.gui.widgets import LibraryBooksView, DeviceBooksView, CoverDisplay, DeviceView   # Needed for import_ui
