#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from PyQt4.Qt import QDialog, SIGNAL

from calibre.gui2.convert.font_key_ui import Ui_Dialog

class FontKeyChooser(QDialog, Ui_Dialog):

    def __init__(self, parent=None, base_font_size=0.0, font_key=None):
        QDialog.__init__(self, parent)
        self.setupUi(self)

        self.default_font_key       = font_key
        self.default_base_font_size = base_font_size
        self.connect(self.buttonBox, SIGNAL('clicked(QAbstractButton*)'),
                self.button_clicked)
        self.connect(self.button_use_default, SIGNAL('clicked()'),
                self.use_default)

        for x in ('input_base_font_size', 'input_font_size',
                'output_base_font_size'):
            self.connect(getattr(self, x), SIGNAL('valueChanged(double)'),
                    self.calculate)
        self.connect(self.font_size_key, SIGNAL('textChanged(QString)'),
                    self.calculate)

        self.initialize()

    def initialize(self):
        self.input_base_font_size.setValue(12.0)
        self.input_font_size.setValue(12.0)
        self.input_mapped_font_size.setText('0.0 pt')
        self.output_base_font_size.setValue(self.default_base_font_size)
        if self.default_font_key:
            self.font_size_key.setText(self.default_font_key)
        else:
            self.font_size_key.setText('')
        self.calculate()

    def button_clicked(self, button):
        if button is self.buttonBox.button(self.buttonBox.RestoreDefaults):
            self.output_base_font_size.setValue(0.0)
            self.font_size_key.setText('')
        self.calculate()

    def get_profile_values(self):
        from calibre.ebooks.conversion.config import load_defaults
        recs = load_defaults('page_setup')
        pfname = recs.get('output_profile', 'default')
        from calibre.customize.ui import output_profiles
        for profile in output_profiles():
            if profile.short_name == pfname:
                break
        dbase = profile.fbase
        fsizes = profile.fkey
        return dbase, fsizes

    @property
    def fsizes(self):
        key = unicode(self.font_size_key.text()).strip()
        return [float(x.strip()) for x in key.split(',') if x.strip()]

    @property
    def dbase(self):
        return self.output_base_font_size.value()

    def calculate(self, *args):
        sbase = self.input_base_font_size.value()
        dbase = self.dbase
        fsize = self.input_font_size.value()
        try:
            fsizes = self.fsizes
        except:
            return

        if dbase == 0.0 or not fsizes:
            pd, pfs = self.get_profile_values()
            if dbase == 0.0:
                dbase = pd
            if not fsizes:
                fsizes = pfs

        from calibre.ebooks.oeb.transforms.flatcss import KeyMapper
        mapper = KeyMapper(sbase, dbase, fsizes)
        msize = mapper[fsize]
        self.input_mapped_font_size.setText('%.1f pt'%msize)

    def use_default(self):
        dbase, fsizes = self.get_profile_values()
        self.output_base_font_size.setValue(dbase)
        self.font_size_key.setText(', '.join(['%.1f'%x for x in fsizes]))


if __name__ == '__main__':
    from calibre.gui2 import is_ok_to_use_qt
    is_ok_to_use_qt()
    d = FontKeyChooser()
    d.exec_()
