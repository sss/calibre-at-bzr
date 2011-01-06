# -*- coding: utf-8 -*-

__license__ = 'GPL 3'
__copyright__ = '2011, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

from calibre.gui2.convert.txt_input_ui import Ui_Form
from calibre.gui2.convert import Widget

class PluginWidget(Widget, Ui_Form):

    TITLE = _('PDB Input')
    HELP = _('Options specific to')+' PDB '+_('input')
    COMMIT_NAME = 'pdb_input'
    ICON = I('mimetypes/txt.png')

    def __init__(self, parent, get_option, get_help, db=None, book_id=None):
        Widget.__init__(self, parent,
            ['paragraph_type', 'formatting_type', 'markdown_disable_toc', 'preserve_spaces'])
        self.db, self.book_id = db, book_id
        for x in get_option('paragraph_type').option.choices:
            self.opt_paragraph_type.addItem(x)
        for x in get_option('formatting_type').option.choices:
            self.opt_formatting_type.addItem(x)
        self.initialize_options(get_option, get_help, db, book_id)
