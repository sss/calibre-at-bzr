#########################################################################
#                                                                       #
#                                                                       #
#   copyright 2002 Paul Henry Tremblay                                  #
#                                                                       #
#   This program is distributed in the hope that it will be useful,     #
#   but WITHOUT ANY WARRANTY; without even the implied warranty of      #
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU    #
#   General Public License for more details.                            #
#                                                                       #
#                                                                       #
#########################################################################
import os, tempfile

from calibre.ebooks.rtf2xml import copy
from calibre.utils.cleantext import clean_ascii_chars

class ReplaceIllegals:
    """
    reaplace illegal lower ascii characters
    """
    def __init__(self,
            in_file,
            copy = None,
            run_level = 1,
            ):
        self.__file = in_file
        self.__copy = copy
        self.__run_level = run_level
        self.__write_to = tempfile.mktemp()

    def replace_illegals(self):
        """
        """
        with open(self.__file, 'r') as read_obj:
            with open(self.__write_to, 'w') as write_obj:
                for line in read_obj:
                    write_obj.write(clean_ascii_chars(line))
        copy_obj = copy.Copy()
        if self.__copy:
            copy_obj.copy_file(self.__write_to, "replace_illegals.data")
        copy_obj.rename(self.__write_to, self.__file)
        os.remove(self.__write_to)
