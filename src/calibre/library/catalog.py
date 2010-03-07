__license__   = 'GPL v3'
__copyright__ = '2010, Greg Riker <griker at hotmail.com>'

import datetime, htmlentitydefs, os, re, shutil

from collections import namedtuple
from copy import deepcopy

from xml.sax.saxutils import escape

from calibre import filesystem_encoding, prints, prepare_string_for_xml, strftime
from calibre.customize import CatalogPlugin
from calibre.customize.conversion import OptionRecommendation, DummyReporter
from calibre.ebooks.BeautifulSoup import BeautifulSoup, BeautifulStoneSoup, Tag, NavigableString
from calibre.ptempfile import PersistentTemporaryDirectory
from calibre.utils.date import isoformat, now as nowf
from calibre.utils.logging import default_log as log

FIELDS = ['all', 'author_sort', 'authors', 'comments',
          'cover', 'formats', 'id', 'isbn', 'pubdate', 'publisher', 'rating',
          'series_index', 'series', 'size', 'tags', 'timestamp', 'title',
          'uuid']

class CSV_XML(CatalogPlugin):
    'CSV/XML catalog generator'

    Option = namedtuple('Option', 'option, default, dest, action, help')

    name = 'Catalog_CSV_XML'
    description = 'CSV/XML catalog generator'
    supported_platforms = ['windows', 'osx', 'linux']
    author = 'Greg Riker'
    version = (1, 0, 0)
    file_types = set(['csv','xml'])

    cli_options = [
            Option('--fields',
                default = 'all',
                dest = 'fields',
                action = None,
                help = _('The fields to output when cataloging books in the '
                    'database.  Should be a comma-separated list of fields.\n'
                    'Available fields: %s.\n'
                    "Default: '%%default'\n"
                    "Applies to: CSV, XML output formats")%', '.join(FIELDS)),

            Option('--sort-by',
                default = 'id',
                dest = 'sort_by',
                action = None,
                help = _('Output field to sort on.\n'
                'Available fields: author_sort, id, rating, size, timestamp, title.\n'
                "Default: '%default'\n"
                "Applies to: CSV, XML output formats"))]

    def run(self, path_to_output, opts, db, notification=DummyReporter()):
        self.fmt = path_to_output.rpartition('.')[2]
        self.notification = notification

        if opts.verbose:
            opts_dict = vars(opts)
            log("%s(): Generating %s" % (self.name,self.fmt))
            if opts_dict['search_text']:
                log(" --search='%s'" % opts_dict['search_text'])

            if opts_dict['ids']:
                log(" Book count: %d" % len(opts_dict['ids']))
                if opts_dict['search_text']:
                    log(" (--search ignored when a subset of the database is specified)")

            if opts_dict['fields']:
                if opts_dict['fields'] == 'all':
                    log(" Fields: %s" % ', '.join(FIELDS[1:]))
                else:
                    log(" Fields: %s" % opts_dict['fields'])


        # If a list of ids are provided, don't use search_text
        if opts.ids:
            opts.search_text = None

        data = self.search_sort_db(db, opts)

        if not len(data):
            log.error("\nNo matching database entries for search criteria '%s'" % opts.search_text)
            raise SystemExit(1)

        # Get the requested output fields as a list
        fields = self.get_output_fields(opts)

        if self.fmt == 'csv':
            outfile = open(path_to_output, 'w')

            # Output the field headers
            outfile.write(u'%s\n' % u','.join(fields))

            # Output the entry fields
            for entry in data:
                outstr = ''
                for (x, field) in enumerate(fields):
                    item = entry[field]
                    if field == 'formats':
                        fmt_list = []
                        for format in item:
                            fmt_list.append(format.partition('.')[2])
                        item = ', '.join(fmt_list)
                    elif field in ['authors','tags']:
                        item = ', '.join(item)
                    elif field == 'isbn':
                        # Could be 9, 10 or 13 digits
                        item = u'%s' % re.sub(r'[\D]', '', item)
                    elif field in ['pubdate', 'timestamp']:
                        item = isoformat(item)

                    if x < len(fields) - 1:
                        if item is not None:
                            outstr += u'"%s",' % unicode(item).replace('"','""')
                        else:
                            outstr += '"",'
                    else:
                        if item is not None:
                            outstr += u'"%s"\n' % unicode(item).replace('"','""')
                        else:
                            outstr += '""\n'
                outfile.write(outstr.encode('utf-8'))
            outfile.close()

        elif self.fmt == 'xml':
            from lxml import etree

            from calibre.utils.genshi.template import MarkupTemplate

            PY_NAMESPACE = "http://genshi.edgewall.org/"
            PY = "{%s}" % PY_NAMESPACE
            NSMAP = {'py' : PY_NAMESPACE}
            root = etree.Element('calibredb', nsmap=NSMAP)
            py_for = etree.SubElement(root, PY + 'for', each="record in data")
            record = etree.SubElement(py_for, 'record')

            if 'id' in fields:
                record_child = etree.SubElement(record, 'id')
                record_child.set(PY + "if", "record['id']")
                record_child.text = "${record['id']}"

            if 'uuid' in fields:
                record_child = etree.SubElement(record, 'uuid')
                record_child.set(PY + "if", "record['uuid']")
                record_child.text = "${record['uuid']}"

            if 'title' in fields:
                record_child = etree.SubElement(record, 'title')
                record_child.set(PY + "if", "record['title']")
                record_child.text = "${record['title']}"

            if 'authors' in fields:
                record_child = etree.SubElement(record, 'authors', sort="${record['author_sort']}")
                record_subchild = etree.SubElement(record_child, PY + 'for', each="author in record['authors']")
                record_subsubchild = etree.SubElement(record_subchild, 'author')
                record_subsubchild.text = '$author'

            if 'publisher' in fields:
                record_child = etree.SubElement(record, 'publisher')
                record_child.set(PY + "if", "record['publisher']")
                record_child.text = "${record['publisher']}"

            if 'rating' in fields:
                record_child = etree.SubElement(record, 'rating')
                record_child.set(PY + "if", "record['rating']")
                record_child.text = "${record['rating']}"

            if 'date' in fields:
                record_child = etree.SubElement(record, 'date')
                record_child.set(PY + "if", "record['date']")
                record_child.text = "${record['date'].isoformat()}"

            if 'pubdate' in fields:
                record_child = etree.SubElement(record, 'pubdate')
                record_child.set(PY + "if", "record['pubdate']")
                record_child.text = "${record['pubdate'].isoformat()}"

            if 'size' in fields:
                record_child = etree.SubElement(record, 'size')
                record_child.set(PY + "if", "record['size']")
                record_child.text = "${record['size']}"

            if 'tags' in fields:
                # <tags py:if="record['tags']">
                #  <py:for each="tag in record['tags']">
                #   <tag>$tag</tag>
                #  </py:for>
                # </tags>
                record_child = etree.SubElement(record, 'tags')
                record_child.set(PY + "if", "record['tags']")
                record_subchild = etree.SubElement(record_child, PY + 'for', each="tag in record['tags']")
                record_subsubchild = etree.SubElement(record_subchild, 'tag')
                record_subsubchild.text = '$tag'

            if 'comments' in fields:
                record_child = etree.SubElement(record, 'comments')
                record_child.set(PY + "if", "record['comments']")
                record_child.text = "${record['comments']}"

            if 'series' in fields:
                # <series py:if="record['series']" index="${record['series_index']}">
                #  ${record['series']}
                # </series>
                record_child = etree.SubElement(record, 'series')
                record_child.set(PY + "if", "record['series']")
                record_child.set('index', "${record['series_index']}")
                record_child.text = "${record['series']}"

            if 'isbn' in fields:
                record_child = etree.SubElement(record, 'isbn')
                record_child.set(PY + "if", "record['isbn']")
                record_child.text = "${record['isbn']}"

            if 'cover' in fields:
                # <cover py:if="record['cover']">
                #  ${record['cover'].replace(os.sep, '/')}
                # </cover>
                record_child = etree.SubElement(record, 'cover')
                record_child.set(PY + "if", "record['cover']")
                record_child.text = "${record['cover']}"

            if 'formats' in fields:
                # <formats py:if="record['formats']">
                #  <py:for each="path in record['formats']">
                #    <format>${path.replace(os.sep, '/')}</format>
                #  </py:for>
                # </formats>
                record_child = etree.SubElement(record, 'formats')
                record_child.set(PY + "if", "record['formats']")
                record_subchild = etree.SubElement(record_child, PY + 'for', each="path in record['formats']")
                record_subsubchild = etree.SubElement(record_subchild, 'format')
                record_subsubchild.text = "${path.replace(os.sep, '/')}"

            outfile = open(path_to_output, 'w')
            template = MarkupTemplate(etree.tostring(root, xml_declaration=True,
                                      encoding="UTF-8", pretty_print=True))
            outfile.write(template.generate(data=data, os=os).render('xml'))
            outfile.close()

        return None

class EPUB_MOBI(CatalogPlugin):
    'ePub catalog generator'

    Option = namedtuple('Option', 'option, default, dest, action, help')

    name = 'Catalog_EPUB_MOBI'
    description = 'EPUB/MOBI catalog generator'
    supported_platforms = ['windows', 'osx', 'linux']
    minimum_calibre_version = (0, 6, 34)
    author = 'Greg Riker'
    version = (0, 0, 1)
    file_types = set(['epub','mobi'])

    cli_options = [Option('--catalog-title',
                          default = 'My Books',
                          dest = 'catalog_title',
                          action = None,
                          help = _('Title of generated catalog used as title in metadata.\n'
                          "Default: '%default'\n"
                          "Applies to: ePub, MOBI output formats")),
                   Option('--debug-pipeline',
                           default=None,
                           dest='debug_pipeline',
                           action = None,
                           help=_("Save the output from different stages of the conversion "
                           "pipeline to the specified "
                           "directory. Useful if you are unsure at which stage "
                           "of the conversion process a bug is occurring.\n"
                           "Default: '%default'None\n"
                           "Applies to: ePub, MOBI output formats")),
                   Option('--exclude-genre',
                          default='\[[\w ]*\]',
                          dest='exclude_genre',
                          action = None,
                          help=_("Regex describing tags to exclude as genres.\n" "Default: '%default' excludes bracketed tags, e.g. '[<tag>]'\n"
                          "Applies to: ePub, MOBI output formats")),
                   Option('--exclude-tags',
                          default=('~,'+_('Catalog')),
                          dest='exclude_tags',
                          action = None,
                          help=_("Comma-separated list of tag words indicating book should be excluded from output.  Case-insensitive.\n"
                          "--exclude-tags=skip will match 'skip this book' and 'Skip will like this'.\n"
                          "Default: '%default'\n"
                          "Applies to: ePub, MOBI output formats")),
                   Option('--generate-titles',
                          default=False,
                          dest='generate_titles',
                          action = 'store_true',
                          help=_("Include 'Titles' section in catalog.\n"
                          "Default: '%default'\n"
                          "Applies to: ePub, MOBI output formats")),
                   Option('--generate-recently-added',
                          default=False,
                          dest='generate_recently_added',
                          action = 'store_true',
                          help=_("Include 'Recently Added' section in catalog.\n"
                          "Default: '%default'\n"
                          "Applies to: ePub, MOBI output formats")),
                   Option('--note-tag',
                          default='*',
                          dest='note_tag',
                          action = None,
                          help=_("Tag prefix for user notes, e.g. '*Jeff might enjoy reading this'.\n"
                          "Default: '%default'\n"
                          "Applies to: ePub, MOBI output formats")),
                   Option('--numbers-as-text',
                          default=False,
                          dest='numbers_as_text',
                          action = None,
                          help=_("Sort titles with leading numbers as text, e.g.,\n'2001: A Space Odyssey' sorts as \n'Two Thousand One: A Space Odyssey'.\n"
                          "Default: '%default'\n"
                          "Applies to: ePub, MOBI output formats")),
                   Option('--output-profile',
                          default=None,
                          dest='output_profile',
                          action = None,
                          help=_("Specifies the output profile.  In some cases, an output profile is required to optimize the catalog for the device.  For example, 'kindle' or 'kindle_dx' creates a structured Table of Contents with Sections and Articles.\n"
                          "Default: '%default'\n"
                          "Applies to: ePub, MOBI output formats")),
                   Option('--read-tag',
                          default='+',
                          dest='read_tag',
                          action = None,
                          help=_("Tag indicating book has been read.\n" "Default: '%default'\n"
                          "Applies to: ePub, MOBI output formats")),
                          ]

    class NumberToText(object):
        '''
        Converts numbers to text
        4.56    => four point fifty-six
        456     => four hundred fifty-six
        4:56    => four fifty-six
        '''
        ORDINALS = ['zeroth','first','second','third','fourth','fifth','sixth','seventh','eighth','ninth']
        lessThanTwenty = ["<zero>","one","two","three","four","five","six","seven","eight","nine",
                          "ten","eleven","twelve","thirteen","fourteen","fifteen","sixteen","seventeen",
                          "eighteen","nineteen"]
        tens = ["<zero>","<tens>","twenty","thirty","forty","fifty","sixty","seventy","eighty","ninety"]
        hundreds = ["<zero>","one","two","three","four","five","six","seven","eight","nine"]

        def __init__(self, number, verbose=False):
            self.number = number
            self.number_as_float = 0.0
            self.text = ''
            self.verbose = verbose
            self.log = log
            self.numberTranslate()

        def stringFromInt(self, intToTranslate):
            # Convert intToTranslate to string
            # intToTranslate is a three-digit number

            tensComponentString = ""
            hundredsComponent = intToTranslate - (intToTranslate % 100)
            tensComponent = intToTranslate % 100

            # Build the hundreds component
            if hundredsComponent:
                hundredsComponentString = "%s hundred" % self.hundreds[hundredsComponent/100]
            else:
                hundredsComponentString = ""

            # Build the tens component
            if tensComponent < 20:
                tensComponentString = self.lessThanTwenty[tensComponent]
            else:
                tensPart = ""
                onesPart = ""

                # Get the tens part
                tensPart = self.tens[tensComponent / 10]
                onesPart = self.lessThanTwenty[tensComponent % 10]

                if intToTranslate % 10:
                    tensComponentString = "%s-%s" % (tensPart, onesPart)
                else:
                    tensComponentString = "%s" % tensPart

            # Concatenate the results
            result = ''
            if hundredsComponent and not tensComponent:
                result = hundredsComponentString
            elif not hundredsComponent and tensComponent:
                result = tensComponentString
            elif hundredsComponent and tensComponent:
                result = hundredsComponentString + " " + tensComponentString
            else:
                prints(" NumberToText.stringFromInt(): empty result translating %d" % intToTranslate)
            return result

        def numberTranslate(self):
            hundredsNumber = 0
            thousandsNumber = 0
            hundredsString = ""
            thousandsString = ""
            resultString = ""
            self.suffix = ''

            if self.verbose: self.log("numberTranslate(): %s" % self.number)

            # Special case ordinals
            if re.search('[st|nd|rd|th]',self.number):
                self.number = re.sub(',','',self.number)
                ordinal_suffix = re.search('[\D]', self.number)
                ordinal_number = re.sub('\D','',re.sub(',','',self.number))
                if self.verbose: self.log("Ordinal: %s" % ordinal_number)
                self.number_as_float = ordinal_number
                self.suffix = self.number[ordinal_suffix.start():]
                if int(ordinal_number) > 9:
                    # Some typos (e.g., 'twentyth'), acceptable
                    self.text = '%s' % (EPUB_MOBI.NumberToText(ordinal_number).text)
                else:
                    self.text = '%s' % (self.ORDINALS[int(ordinal_number)])

            # Test for time
            elif re.search(':',self.number):
                if self.verbose: self.log("Time: %s" % self.number)
                self.number_as_float = re.sub(':','.',self.number)
                time_strings = self.number.split(":")
                hours = EPUB_MOBI.NumberToText(time_strings[0]).text
                minutes = EPUB_MOBI.NumberToText(time_strings[1]).text
                self.text = '%s-%s' % (hours.capitalize(), minutes)

            # Test for %
            elif re.search('%', self.number):
                if self.verbose: self.log("Percent: %s" % self.number)
                self.number_as_float = self.number.split('%')[0]
                self.text = EPUB_MOBI.NumberToText(self.number.replace('%',' percent')).text

            # Test for decimal
            elif re.search('\.',self.number):
                if self.verbose: self.log("Decimal: %s" % self.number)
                self.number_as_float = self.number
                decimal_strings = self.number.split(".")
                left = EPUB_MOBI.NumberToText(decimal_strings[0]).text
                right = EPUB_MOBI.NumberToText(decimal_strings[1]).text
                self.text = '%s point %s' % (left.capitalize(), right)

            # Test for hypenated
            elif re.search('-', self.number):
                if self.verbose: self.log("Hyphenated: %s" % self.number)
                self.number_as_float = self.number.split('-')[0]
                strings = self.number.split('-')
                if re.search('[0-9]+', strings[0]):
                    left = EPUB_MOBI.NumberToText(strings[0]).text
                    right = strings[1]
                else:
                    left = strings[0]
                    right = EPUB_MOBI.NumberToText(strings[1]).text
                self.text = '%s-%s' % (left, right)

            # Test for only commas and numbers
            elif re.search(',', self.number) and not re.search('[^0-9,]',self.number):
                if self.verbose: self.log("Comma(s): %s" % self.number)
                self.number_as_float = re.sub(',','',self.number)
                self.text = EPUB_MOBI.NumberToText(self.number_as_float).text

            # Test for hybrid e.g., 'K2, 2nd, 10@10'
            elif re.search('[\D]+', self.number):
                if self.verbose: self.log("Hybrid: %s" % self.number)
                # Split the token into number/text
                number_position = re.search('\d',self.number).start()
                text_position = re.search('\D',self.number).start()
                if number_position < text_position:
                    number = self.number[:text_position]
                    text = self.number[text_position:]
                    self.text = '%s%s' % (EPUB_MOBI.NumberToText(number).text,text)
                else:
                    text = self.number[:number_position]
                    number = self.number[number_position:]
                    self.text = '%s%s' % (text, EPUB_MOBI.NumberToText(number).text)

            else:
                if self.verbose: self.log("Clean: %s" % self.number)
                try:
                    self.float_as_number = float(self.number)
                    number = int(self.number)
                except:
                    return

                if number > 10**9:
                    self.text = "%d out of range" % number
                    return

                if number == 10**9:
                    self.text = "one billion"
                else :
                    # Isolate the three-digit number groups
                    millionsNumber  = number/10**6
                    thousandsNumber = (number - (millionsNumber * 10**6))/10**3
                    hundredsNumber  = number - (millionsNumber * 10**6) - (thousandsNumber * 10**3)
                    if self.verbose:
                        print "Converting %s %s %s" % (millionsNumber, thousandsNumber, hundredsNumber)

                    # Convert hundredsNumber
                    if hundredsNumber :
                        hundredsString = self.stringFromInt(hundredsNumber)

                    # Convert thousandsNumber
                    if thousandsNumber:
                        if number > 1099 and number < 2000:
                            resultString = '%s %s' % (self.lessThanTwenty[number/100],
                                                     self.stringFromInt(number % 100))
                            self.text = resultString.strip().capitalize()
                            return
                        else:
                            thousandsString = self.stringFromInt(thousandsNumber)

                    # Convert millionsNumber
                    if millionsNumber:
                        millionsString = self.stringFromInt(millionsNumber)

                    # Concatenate the strings
                    resultString = ''
                    if millionsNumber:
                        resultString += "%s million " % millionsString

                    if thousandsNumber:
                        resultString += "%s thousand " % thousandsString

                    if hundredsNumber:
                        resultString += "%s" % hundredsString

                    if not millionsNumber and not thousandsNumber and not hundredsNumber:
                        resultString = "zero"

                    if self.verbose:
                        self.log(u'resultString: %s' % resultString)
                    self.text = resultString.strip().capitalize()

    class CatalogBuilder(object):
        '''
        Generates catalog source files from calibre database

        Implementation notes
        - 'Marker tags' in a book's metadata are used to flag special conditions:
                    (Defaults)
                    '~' : Do not catalog this book
                    '+' : Mark this book as read (check mark) in lists
                    '*' : Display trailing text as 'Note: <text>' in top frame next to cover
            '[<source>] : Source of content (e.g., Amazon, Project Gutenberg).  Do not create genre

        - Program flow
            catalog = Catalog(notification=Reporter())
            catalog.createDirectoryStructure()
            catalog.copyResources()
            catalog.buildSources()
        '''
        # A single number creates 'Last x days' only.
        # Multiple numbers create 'Last x days', 'x to y days ago' ...
        # e.g, [7,15,30,60], [30]
        # [] = No date ranges added
        DATE_RANGE=[30]

        # basename              output file basename
        # creator               dc:creator in OPF metadata
        # descriptionClip       limits size of NCX descriptions (Kindle only)
        # includeSources        Used in processSpecialTags to skip tags like '[SPL]'
        # notification          Used to check for cancel, report progress
        # stylesheet            CSS stylesheet
        # title                 dc:title in OPF metadata, NCX periodical
        # verbosity             level of diagnostic printout

        def __init__(self, db, opts, plugin,
                     report_progress=DummyReporter(),
                     stylesheet="content/stylesheet.css"):
            self.__opts = opts
            self.__authorClip = opts.authorClip
            self.__authors = None
            self.__basename = opts.basename
            self.__bookmarked_books = None
            self.__booksByAuthor = None
            self.__booksByDateRead = None
            self.__booksByTitle = None
            self.__booksByTitle_noSeriesPrefix = None
            self.__catalogPath = PersistentTemporaryDirectory("_epub_mobi_catalog", prefix='')
            self.__contentDir = os.path.join(self.catalogPath, "content")
            self.__currentStep = 0.0
            self.__creator = opts.creator
            self.__db = db
            self.__descriptionClip = opts.descriptionClip
            self.__error = None
            self.__generateForKindle = True if (self.opts.fmt == 'mobi' and \
                                       self.opts.output_profile and \
                                       self.opts.output_profile.startswith("kindle")) else False
            self.__generateRecentlyRead = True if self.opts.generate_recently_added \
                                                  and self.opts.connected_kindle \
                                                  and self.generateForKindle \
                                                else False
            self.__genres = None
            self.__genre_tags_dict = None
            self.__htmlFileList = []
            self.__markerTags = self.getMarkerTags()
            self.__ncxSoup = None
            self.__playOrder = 1
            self.__plugin = plugin
            self.__progressInt = 0.0
            self.__progressString = ''
            self.__reporter = report_progress
            self.__stylesheet = stylesheet
            self.__thumbs = None
            self.__thumbWidth = 0
            self.__thumbHeight = 0
            self.__title = opts.catalog_title
            self.__totalSteps = 11.0
            self.__useSeriesPrefixInTitlesSection = False
            self.__verbose = opts.verbose

            # Tweak build steps based on optional sections:  1 call for HTML, 1 for NCX
            if self.opts.generate_titles:
                self.__totalSteps += 2
            if self.opts.generate_recently_added:
                self.__totalSteps += 2
                if self.generateRecentlyRead:
                    self.__totalSteps += 2

        # Accessors
        '''
        @dynamic_property
        def xxxx(self):
            def fget(self):
                return self.__
            def fset(self, val):
                self.__ = val
            return property(fget=fget, fset=fset)
        '''

        @dynamic_property
        def authorClip(self):
            def fget(self):
                return self.__authorClip
            def fset(self, val):
                self.__authorClip = val
            return property(fget=fget, fset=fset)
        @dynamic_property
        def authors(self):
            def fget(self):
                return self.__authors
            def fset(self, val):
                self.__authors = val
            return property(fget=fget, fset=fset)
        @dynamic_property
        def basename(self):
            def fget(self):
                return self.__basename
            def fset(self, val):
                self.__basename = val
            return property(fget=fget, fset=fset)
        @dynamic_property
        def bookmarked_books(self):
            def fget(self):
                return self.__bookmarked_books
            def fset(self, val):
                self.__bookmarked_books = val
            return property(fget=fget, fset=fset)
        @dynamic_property
        def booksByAuthor(self):
            def fget(self):
                return self.__booksByAuthor
            def fset(self, val):
                self.__booksByAuthor = val
            return property(fget=fget, fset=fset)
        @dynamic_property
        def booksByDateRead(self):
            def fget(self):
                return self.__booksByDateRead
            def fset(self, val):
                self.__booksByDateRead = val
            return property(fget=fget, fset=fset)
        @dynamic_property
        def booksByTitle(self):
            def fget(self):
                return self.__booksByTitle
            def fset(self, val):
                self.__booksByTitle = val
            return property(fget=fget, fset=fset)
        @dynamic_property
        def booksByTitle_noSeriesPrefix(self):
            def fget(self):
                return self.__booksByTitle_noSeriesPrefix
            def fset(self, val):
                self.__booksByTitle_noSeriesPrefix = val
            return property(fget=fget, fset=fset)
        @dynamic_property
        def catalogPath(self):
            def fget(self):
                return self.__catalogPath
            def fset(self, val):
                self.__catalogPath = val
            return property(fget=fget, fset=fset)
        @dynamic_property
        def contentDir(self):
            def fget(self):
                return self.__contentDir
            def fset(self, val):
                self.__contentDir = val
            return property(fget=fget, fset=fset)
        @dynamic_property
        def currentStep(self):
            def fget(self):
                return self.__currentStep
            def fset(self, val):
                self.__currentStep = val
            return property(fget=fget, fset=fset)
        @dynamic_property
        def creator(self):
            def fget(self):
                return self.__creator
            def fset(self, val):
                self.__creator = val
            return property(fget=fget, fset=fset)
        @dynamic_property
        def db(self):
            def fget(self):
                return self.__db
            return property(fget=fget)
        @dynamic_property
        def descriptionClip(self):
            def fget(self):
                return self.__descriptionClip
            def fset(self, val):
                self.__descriptionClip = val
            return property(fget=fget, fset=fset)
        @dynamic_property
        def error(self):
            def fget(self):
                return self.__error
            return property(fget=fget)
        @dynamic_property
        def generateForKindle(self):
            def fget(self):
                return self.__generateForKindle
            def fset(self, val):
                self.__generateForKindle = val
            return property(fget=fget, fset=fset)
        @dynamic_property
        def generateRecentlyRead(self):
            def fget(self):
                return self.__generateRecentlyRead
            def fset(self, val):
                self.__generateRecentlyRead = val
            return property(fget=fget, fset=fset)
        @dynamic_property
        def genres(self):
            def fget(self):
                return self.__genres
            def fset(self, val):
                self.__genres = val
            return property(fget=fget, fset=fset)
        @dynamic_property
        def genre_tags_dict(self):
            def fget(self):
                return self.__genre_tags_dict
            def fset(self, val):
                self.__genre_tags_dict = val
            return property(fget=fget, fset=fset)
        @dynamic_property
        def htmlFileList(self):
            def fget(self):
                return self.__htmlFileList
            def fset(self, val):
                self.__htmlFileList = val
            return property(fget=fget, fset=fset)
        @dynamic_property
        def libraryPath(self):
            def fget(self):
                return self.__libraryPath
            def fset(self, val):
                self.__libraryPath = val
            return property(fget=fget, fset=fset)
        @dynamic_property
        def markerTags(self):
            def fget(self):
                return self.__markerTags
            def fset(self, val):
                self.__markerTags = val
            return property(fget=fget, fset=fset)
        @dynamic_property
        def ncxSoup(self):
            def fget(self):
                return self.__ncxSoup
            def fset(self, val):
                self.__ncxSoup = val
            return property(fget=fget, fset=fset)
        @dynamic_property
        def opts(self):
            def fget(self):
                return self.__opts
            return property(fget=fget)
        @dynamic_property
        def playOrder(self):
            def fget(self):
                return self.__playOrder
            def fset(self,val):
                self.__playOrder = val
            return property(fget=fget, fset=fset)
        @dynamic_property
        def plugin(self):
            def fget(self):
                return self.__plugin
            return property(fget=fget)
        @dynamic_property
        def progressInt(self):
            def fget(self):
                return self.__progressInt
            def fset(self, val):
                self.__progressInt = val
            return property(fget=fget, fset=fset)
        @dynamic_property
        def progressString(self):
            def fget(self):
                return self.__progressString
            def fset(self, val):
                self.__progressString = val
            return property(fget=fget, fset=fset)
        @dynamic_property
        def reporter(self):
            def fget(self):
                return self.__reporter
            def fset(self, val):
                self.__reporter = val
            return property(fget=fget, fset=fset)
        @dynamic_property
        def stylesheet(self):
            def fget(self):
                return self.__stylesheet
            def fset(self, val):
                self.__stylesheet = val
            return property(fget=fget, fset=fset)
        @dynamic_property
        def thumbs(self):
            def fget(self):
                return self.__thumbs
            def fset(self, val):
                self.__thumbs = val
            return property(fget=fget, fset=fset)
        def thumbWidth(self):
            def fget(self):
                return self.__thumbWidth
            def fset(self, val):
                self.__thumbWidth = val
            return property(fget=fget, fset=fset)
        def thumbHeight(self):
            def fget(self):
                return self.__thumbHeight
            def fset(self, val):
                self.__thumbHeight = val
            return property(fget=fget, fset=fset)
        @dynamic_property
        def title(self):
            def fget(self):
                return self.__title
            def fset(self, val):
                self.__title = val
            return property(fget=fget, fset=fset)
        @dynamic_property
        def totalSteps(self):
            def fget(self):
                return self.__totalSteps
            return property(fget=fget)
        @dynamic_property
        def useSeriesPrefixInTitlesSection(self):
            def fget(self):
                return self.__useSeriesPrefixInTitlesSection
            def fset(self, val):
                self.__useSeriesPrefixInTitlesSection = val
            return property(fget=fget, fset=fset)
        @dynamic_property
        def verbose(self):
            def fget(self):
                return self.__verbose
            def fset(self, val):
                self.__verbose = val
            return property(fget=fget, fset=fset)

        @dynamic_property
        def NOT_READ_SYMBOL(self):
            def fget(self):
                return '<span style="color:white">&#x2713;</span>' if self.generateForKindle else \
                       '<span style="color:white">%s</span>' % self.opts.read_tag
            return property(fget=fget)
        @dynamic_property
        def READING_SYMBOL(self):
            def fget(self):
                return '<span style="color:black">&#x25b7;</span>' if self.generateForKindle else \
                       '<span style="color:white">%s</span>' % self.opts.read_tag
            return property(fget=fget)
        @dynamic_property
        def READ_SYMBOL(self):
            def fget(self):
                return '<span style="color:black">&#x2713;</span>' if self.generateForKindle else \
                       '<span style="color:black">%s</span>' % self.opts.read_tag
            return property(fget=fget)
        @dynamic_property
        def FULL_RATING_SYMBOL(self):
            def fget(self):
                return "&#9733;" if self.generateForKindle else "*"
            return property(fget=fget)
        @dynamic_property
        def EMPTY_RATING_SYMBOL(self):
            def fget(self):
                return "&#9734;" if self.generateForKindle else ' '
            return property(fget=fget)
        @dynamic_property
        def READ_PROGRESS_SYMBOL(self):
            def fget(self):
                return "&#9642;" if self.generateForKindle else '+'
            return property(fget=fget)
        @dynamic_property
        def UNREAD_PROGRESS_SYMBOL(self):
            def fget(self):
                return "&#9643;" if self.generateForKindle else '-'
            return property(fget=fget)

        # Methods
        def buildSources(self):
            if self.booksByTitle is None:
                if not self.fetchBooksByTitle():
                    return False
            self.fetchBooksByAuthor()
            self.fetchBookmarks()
            self.generateHTMLDescriptions()
            self.generateHTMLByAuthor()
            if self.opts.generate_titles:
                self.generateHTMLByTitle()
            if self.opts.generate_recently_added:
                self.generateHTMLByDateAdded()
                if self.generateRecentlyRead:
                    self.generateHTMLByDateRead()
            self.generateHTMLByTags()

            from calibre.utils.PythonMagickWand import ImageMagick
            with ImageMagick():
                self.generateThumbnails()

            self.generateOPF()
            self.generateNCXHeader()
            self.generateNCXDescriptions("Descriptions")
            self.generateNCXByAuthor("Authors")
            if self.opts.generate_titles:
                self.generateNCXByTitle("Titles")
            if self.opts.generate_recently_added:
                self.generateNCXByDateAdded("Recently Added")
                if self.generateRecentlyRead:
                    self.generateNCXByDateRead("Recently Read")
            self.generateNCXByGenre("Genres")
            self.writeNCX()
            return True

        def cleanUp(self):
            pass

        def copyResources(self):
            '''Move resource files to self.catalogPath'''
            catalog_resources = P("catalog")

            files_to_copy = [('','DefaultCover.jpg'),
                             ('content','stylesheet.css'),
                             ('images','mastheadImage.gif')]

            for file in files_to_copy:
                if file[0] == '':
                    shutil.copy(os.path.join(catalog_resources,file[1]),
                                    self.catalogPath)
                else:
                    shutil.copy(os.path.join(catalog_resources,file[1]),
                                    os.path.join(self.catalogPath, file[0]))

            # Create the custom masthead image overwriting default
            # If failure, default mastheadImage.gif should still be in place
            if self.generateForKindle:
                try:
                    self.generateMastheadImage(os.path.join(self.catalogPath,
                                                 'images/mastheadImage.gif'))
                except:
                    pass

        def fetchBooksByTitle(self):

            self.updateProgressFullStep("Fetching database")

            # Get the database as a dictionary
            # Sort by title
            # Search is a string like this:
            # not tag:<exclude_tag> author:"Riker"
            # So we need to merge opts.exclude_tag with opts.search_text
            # not tag:"~" author:"Riker"

            self.opts.sort_by = 'title'

            # Merge opts.exclude_tags with opts.search_text
            # Updated to use exact match syntax
            empty_exclude_tags = False if len(self.opts.exclude_tags) else True
            search_phrase = ''
            if not empty_exclude_tags:
                exclude_tags = self.opts.exclude_tags.split(',')
                search_terms = []
                for tag in exclude_tags:
                    search_terms.append("tag:=%s" % tag)
                search_phrase = "not (%s)" % " or ".join(search_terms)

            # If a list of ids are provided, don't use search_text
            if self.opts.ids:
                self.opts.search_text = search_phrase
            else:
                if self.opts.search_text:
                    self.opts.search_text += " " + search_phrase
                else:
                    self.opts.search_text = search_phrase

            #print "fetchBooksByTitle(): opts.search_text: %s" % self.opts.search_text
            # Fetch the database as a dictionary
            data = self.plugin.search_sort_db(self.db, self.opts)

            # Populate this_title{} from data[{},{}]
            titles = []
            for record in data:
                this_title = {}

                this_title['id'] = record['id']

                this_title['title'] = self.convertHTMLEntities(record['title'])
                if record['series']:
                    this_title['series'] = record['series']
                    this_title['series_index'] = record['series_index']
                    this_title['title'] = self.generateSeriesTitle(this_title)
                else:
                    this_title['series'] = None
                    this_title['series_index'] = 0.0

                this_title['title_sort'] = self.generateSortTitle(this_title['title'])
                if 'authors' in record:
                    this_title['authors'] = record['authors']
                    if record['authors']:
                        this_title['author'] = " &amp; ".join(record['authors'])
                    else:
                        this_title['author'] = 'Unknown'

                if 'author_sort' in record and record['author_sort'].strip():
                    this_title['author_sort'] = record['author_sort']
                else:
                    this_title['author_sort'] = self.author_to_author_sort(this_title['author'])

                if record['publisher']:
                    this_title['publisher'] = re.sub('&', '&amp;', record['publisher'])

                this_title['rating'] = record['rating'] if record['rating'] else 0
                this_title['date'] = strftime(u'%B %Y', record['pubdate'].timetuple())
                this_title['timestamp'] = record['timestamp']

                if record['comments']:
                    # Strip annotations
                    a_offset = record['comments'].find('<div class="user_annotations">')
                    ad_offset = record['comments'].find('<hr class="annotations_divider" />')
                    if a_offset >= 0:
                        record['comments'] = record['comments'][:a_offset]
                    if ad_offset >= 0:
                        record['comments'] = record['comments'][:ad_offset]

                    this_title['description'] = self.markdownComments(record['comments'])
                    paras = BeautifulSoup(this_title['description']).findAll('p')
                    tokens = []
                    for p in paras:
                        for token in p.contents:
                            if token.string is not None:
                                tokens.append(token.string)
                    this_title['short_description'] = self.generateShortDescription(' '.join(tokens), dest="description")
                else:
                    this_title['description'] = None
                    this_title['short_description'] = None

                if record['cover']:
                    this_title['cover'] = re.sub('&amp;', '&', record['cover'])

                # This may be updated in self.processSpecialTags()
                this_title['read'] = False

                if record['tags']:
                    this_title['tags'] = self.processSpecialTags(record['tags'],
                                            this_title, self.opts)
                if record['formats']:
                    formats = []
                    for format in record['formats']:
                        formats.append(self.convertHTMLEntities(format))
                    this_title['formats'] = formats

                titles.append(this_title)

            # Re-sort based on title_sort
            if len(titles):
                self.booksByTitle = sorted(titles,
                                     key=lambda x:(x['title_sort'].upper(), x['title_sort'].upper()))
                if False and self.verbose:
                    self.opts.log.info("fetchBooksByTitle(): %d books" % len(self.booksByTitle))
                    self.opts.log.info(" %-40s %-40s" % ('title', 'title_sort'))
                    for title in self.booksByTitle:
                        self.opts.log.info((u" %-40s %-40s" % (title['title'][0:40],
                                                               title['title_sort'][0:40])).encode('utf-8'))
                return True
            else:
                return False

        def fetchBooksByAuthor(self):
            # Generate a list of titles sorted by author from the database

            self.updateProgressFullStep("Sorting database")

            '''
            # Sort titles case-insensitive, by author
            self.booksByAuthor = sorted(self.booksByTitle,
                                 key=lambda x:(x['author_sort'].upper(), x['author_sort'].upper()))
            '''

            self.booksByAuthor = list(self.booksByTitle)
            self.booksByAuthor.sort(self.author_compare)

            if False and self.verbose:
                self.opts.log.info("fetchBooksByAuthor(): %d books" % len(self.booksByAuthor))
                self.opts.log.info(" %-30s %-20s %s" % ('title', 'series', 'series_index'))
                for title in self.booksByAuthor:
                    self.opts.log.info((u" %-30s %-20s%5s " % \
                                        (title['title'][:30],
                                         title['series'][:20] if title['series'] else '',
                                         title['series_index'],
                                         )).encode('utf-8'))
                raise SystemExit

            # Build the unique_authors set from existing data
            authors = [(record['author'], record['author_sort'].capitalize()) for record in self.booksByAuthor]

            # authors[] contains a list of all book authors, with multiple entries for multiple books by author
            #        authors[]: (([0]:friendly  [1]:sort))
            # unique_authors[]: (([0]:friendly  [1]:sort  [2]:book_count))
            books_by_current_author = 0
            current_author = authors[0]
            multiple_authors = False
            unique_authors = []
            for (i,author) in enumerate(authors):
                if author != current_author:
                    # Note that current_author and author are tuples: (friendly, sort)
                    multiple_authors = True

                if author != current_author and i:
                    # Warn if friendly matches previous, but sort doesn't
                    if author[0] == current_author[0]:
                        self.opts.log.warn("Warning: multiple entries for Author '%s' with differing Author Sort metadata:" % author[0])
                        self.opts.log.warn(" '%s' != '%s'" % (author[1], current_author[1]))

                    # New author, save the previous author/sort/count
                    unique_authors.append((current_author[0], current_author[1].title(),
                                           books_by_current_author))
                    current_author = author
                    books_by_current_author = 1
                elif i==0 and len(authors) == 1:
                    # Allow for single-book lists
                    unique_authors.append((current_author[0], current_author[1].title(),
                                           books_by_current_author))
                else:
                    books_by_current_author += 1
            else:
                # Add final author to list or single-author dataset
                if (current_author == author and len(authors) > 1) or not multiple_authors:
                    unique_authors.append((current_author[0], current_author[1].title(),
                                           books_by_current_author))

            if False and self.verbose:
                self.opts.log.info("\nfetchBooksByauthor(): %d unique authors" % len(unique_authors))
                for author in unique_authors:
                    self.opts.log.info((u" %-50s %-25s %2d" % (author[0][0:45], author[1][0:20],
                       author[2])).encode('utf-8'))

            self.authors = unique_authors

        def fetchBookmarks(self):
            '''
            Collect bookmarks for catalog entries
            This will use the system default save_template specified in
            Preferences|Add/Save|Sending to device, not a customized one specified in
            the Kindle plugin
            '''
            from calibre.devices.usbms.device import Device
            from calibre.devices.kindle.driver import Bookmark
            from calibre.ebooks.metadata import MetaInformation

            MBP_FORMATS = [u'azw', u'mobi', u'prc', u'txt']
            TAN_FORMATS = [u'tpz', u'azw1']
            mbp_formats = set()
            for fmt in MBP_FORMATS:
                mbp_formats.add(fmt)
            tan_formats = set()
            for fmt in TAN_FORMATS:
                tan_formats.add(fmt)

            class BookmarkDevice(Device):
                def initialize(self, save_template):
                    self._save_template = save_template
                    self.SUPPORTS_SUB_DIRS = True
                def save_template(self):
                    return self._save_template

            def resolve_bookmark_paths(storage, path_map):
                pop_list = []
                book_ext = {}
                for id in path_map:
                    file_fmts = set()
                    for fmt in path_map[id]['fmts']:
                        file_fmts.add(fmt)

                    bookmark_extension = None
                    if file_fmts.intersection(mbp_formats):
                        book_extension = list(file_fmts.intersection(mbp_formats))[0]
                        bookmark_extension = 'mbp'
                    elif file_fmts.intersection(tan_formats):
                        book_extension = list(file_fmts.intersection(tan_formats))[0]
                        bookmark_extension = 'tan'

                    if bookmark_extension:
                        for vol in storage:
                            bkmk_path = path_map[id]['path'].replace(os.path.abspath('/<storage>'),vol)
                            bkmk_path = bkmk_path.replace('bookmark',bookmark_extension)
                            print "looking for %s" % bkmk_path
                            if os.path.exists(bkmk_path):
                                path_map[id] = bkmk_path
                                book_ext[id] = book_extension
                                break
                        else:
                            pop_list.append(id)
                    else:
                        pop_list.append(id)
                # Remove non-existent bookmark templates
                for id in pop_list:
                    path_map.pop(id)
                return path_map, book_ext

            if self.generateRecentlyRead:
                self.opts.log.info("     Collecting Kindle bookmarks matching catalog entries")

                d = BookmarkDevice(None)
                d.initialize(self.opts.connected_device['save_template'])

                bookmarks = {}
                for book in self.booksByTitle:
                    if 'formats' in book:
                        path_map = {}
                        id = book['id']
                        original_title = book['title'][book['title'].find(':') + 2:] if book['series'] \
                                   else book['title']
                        myMeta = MetaInformation(original_title,
                                                 authors=book['authors'])
                        myMeta.author_sort = book['author_sort']
                        a_path = d.create_upload_path('/<storage>', myMeta, 'x.bookmark', create_dirs=False)
                        path_map[id] = dict(path=a_path, fmts=[x.rpartition('.')[2] for x in book['formats']])

                        path_map, book_ext = resolve_bookmark_paths(self.opts.connected_device['storage'], path_map)
                        if path_map:
                            bookmark_ext = path_map[id].rpartition('.')[2]
                            myBookmark = Bookmark(path_map[id], id, book_ext[id], bookmark_ext)
                            print "book: %s\nlast_read_location: %d\nlength: %d" % (book['title'],
                                                                                    myBookmark.last_read_location,
                                                                                    myBookmark.book_length)
                            if myBookmark.book_length:
                                book['percent_read'] = float(100*myBookmark.last_read_location / myBookmark.book_length)
                                dots = int((book['percent_read'] + 5)/10)
                                dot_string = self.READ_PROGRESS_SYMBOL * dots
                                empty_dots = self.UNREAD_PROGRESS_SYMBOL * (10 - dots)
                                book['reading_progress'] = '%s%s' % (dot_string,empty_dots)
                                bookmarks[id] = ((myBookmark,book))

                self.bookmarked_books = bookmarks
            else:
                self.bookmarked_books = {}

        def generateHTMLDescriptions(self):
            # Write each title to a separate HTML file in contentdir
            self.updateProgressFullStep("'Descriptions'")

            for (title_num, title) in enumerate(self.booksByTitle):
                if False:
                    self.opts.log.info("%3s: %s - %s" % (title['id'], title['title'], title['author']))

                self.updateProgressMicroStep("Description %d of %d" % \
                                             (title_num, len(self.booksByTitle)),
                                             float(title_num*100/len(self.booksByTitle))/100)

                # Generate the header
                soup = self.generateHTMLDescriptionHeader("%s" % title['title'])
                body = soup.find('body')

                btc = 0

                # Insert the anchor
                aTag = Tag(soup, "a")
                aTag['name'] = "book%d" % int(title['id'])
                body.insert(btc, aTag)
                btc += 1

                # Insert the book title
                #<p class="title"><a name="<database_id>"></a><em>Book Title</em></p>
                emTag = Tag(soup, "em")
                if title['series']:
                    # title<br />series series_index
                    brTag = Tag(soup,'br')
                    title_tokens = title['title'].split(': ')
                    emTag.insert(0, escape(NavigableString(title_tokens[1])))
                    emTag.insert(1, brTag)
                    smallTag = Tag(soup,'small')
                    smallTag.insert(0, escape(NavigableString(title_tokens[0])))
                    emTag.insert(2, smallTag)
                else:
                    emTag.insert(0, NavigableString(escape(title['title'])))
                titleTag = body.find(attrs={'class':'title'})
                titleTag.insert(0,emTag)

                # Create the author anchor
                authorTag = body.find(attrs={'class':'author'})
                aTag = Tag(soup, "a")
                aTag['href'] = "%s.html#%s" % ("ByAlphaAuthor",
                                                self.generateAuthorAnchor(title['author']))
                aTag.insert(0, title['author'])

                # This will include the reading progress dots even if we're not generating Recently Read
                if self.opts.connected_kindle and title['id'] in self.bookmarked_books:
                    authorTag.insert(0, NavigableString(self.READING_SYMBOL + " by "))
                else:
                    # Insert READ/NOT_READ SYMBOL
                    if title['read']:
                        authorTag.insert(0, NavigableString(self.READ_SYMBOL + "by "))
                    else:
                        authorTag.insert(0, NavigableString(self.NOT_READ_SYMBOL + "by "))
                authorTag.insert(1, aTag)

                '''
                # Insert Series info or remove.
                seriesTag = body.find(attrs={'class':'series'})
                if title['series']:
                    # Insert a spacer to match the author indent
                    stc = 0
                    fontTag = Tag(soup,"font")
                    fontTag['style'] = 'color:white;font-size:large'
                    if self.opts.fmt == 'epub':
                        fontTag['style'] += ';opacity: 0.0'
                    fontTag.insert(0, NavigableString("by "))
                    seriesTag.insert(stc, fontTag)
                    stc += 1
                    if float(title['series_index']) - int(title['series_index']):
                        series_str = 'Series: %s [%4.2f]' % (title['series'], title['series_index'])
                    else:
                        series_str = '%s [%d]' % (title['series'], title['series_index'])
                    seriesTag.insert(stc,NavigableString(series_str))
                else:
                    seriesTag.extract()
                '''
                # Insert linked genres
                if 'tags' in title:
                    tagsTag = body.find(attrs={'class':'tags'})
                    ttc = 0

                    # Insert a spacer to match the author indent
                    fontTag = Tag(soup,"font")
                    fontTag['style'] = 'color:white;font-size:large'
                    if self.opts.fmt == 'epub':
                        fontTag['style'] += ';opacity: 0.0'
                    fontTag.insert(0, NavigableString("by "))
                    tagsTag.insert(ttc, fontTag)
                    ttc += 1

                    for tag in title['tags']:
                        aTag = Tag(soup,'a')
                        #print "aTag: %s" % "Genre_%s.html" % re.sub("\W","",tag.lower())
                        aTag['href'] = "Genre_%s.html" % re.sub("\W","",tag.lower())
                        aTag.insert(0,escape(NavigableString(tag)))
                        emTag = Tag(soup, "em")
                        emTag.insert(0, aTag)
                        if ttc < len(title['tags']):
                            emTag.insert(1, NavigableString(' &middot; '))
                        tagsTag.insert(ttc, emTag)
                        ttc += 1

                # Insert the cover <img> if available
                imgTag = Tag(soup,"img")
                if 'cover' in title:
                    imgTag['src']  = "../images/thumbnail_%d.jpg" % int(title['id'])
                else:
                    imgTag['src']  = "../images/thumbnail_default.jpg"
                imgTag['alt'] = "cover"

                '''
                if self.opts.fmt == 'mobi':
                    imgTag['style'] = 'width: %dpx; height:%dpx;' % (self.thumbWidth, self.thumbHeight)
                '''

                thumbnailTag = body.find(attrs={'class':'thumbnail'})
                thumbnailTag.insert(0,imgTag)

                # Insert the publisher
                publisherTag = body.find(attrs={'class':'publisher'})
                if 'publisher' in title:
                    publisherTag.insert(0,NavigableString(title['publisher'] + '<br/>' ))
                else:
                    publisherTag.insert(0,NavigableString('<br/>'))

                # Insert the publication date
                pubdateTag = body.find(attrs={'class':'date'})
                if title['date'] is not None:
                    pubdateTag.insert(0,NavigableString(title['date'] + '<br/>'))
                else:
                    pubdateTag.insert(0,NavigableString('<br/>'))

                # Insert the rating
                # Render different ratings chars for epub/mobi
                stars = int(title['rating']) / 2
                star_string = self.FULL_RATING_SYMBOL * stars
                empty_stars = self.EMPTY_RATING_SYMBOL * (5 - stars)

                ratingTag = body.find(attrs={'class':'rating'})
                ratingTag.insert(0,NavigableString('%s%s <br/>' % (star_string,empty_stars)))

                # Insert user notes or remove Notes label.  Notes > 1 line will push formatting down
                if 'notes' in title:
                    notesTag = body.find(attrs={'class':'notes'})
                    notesTag.insert(0,NavigableString(title['notes'] + '<br/>'))
                else:
                    notes_labelTag = body.find(attrs={'class':'notes_label'})
                    empty_labelTag = Tag(soup, "td")
                    empty_labelTag.insert(0,NavigableString('<br/>'))
                    notes_labelTag.replaceWith(empty_labelTag)

                # Insert the blurb
                if 'description' in title and title['description'] > '':
                    blurbTag = body.find(attrs={'class':'description'})
                    blurbTag.insert(0,NavigableString(title['description']))

                # Write the book entry to contentdir
                outfile = open("%s/book_%d.html" % (self.contentDir, int(title['id'])), 'w')
                outfile.write(soup.prettify())
                outfile.close()

        def generateHTMLByTitle(self):
            # Write books by title A-Z to HTML file

            self.updateProgressFullStep("'Titles'")

            soup = self.generateHTMLEmptyHeader("Books By Alpha Title")
            body = soup.find('body')
            btc = 0

            # Insert section tag
            aTag = Tag(soup,'a')
            aTag['name'] = 'section_start'
            body.insert(btc, aTag)
            btc += 1

            # Insert the anchor
            aTag = Tag(soup, "a")
            aTag['name'] = "bytitle"
            body.insert(btc, aTag)
            btc += 1

            '''
            # We don't need this because the Kindle shows section titles
            #<h2><a name="byalphatitle" id="byalphatitle"></a>By Title</h2>
            h2Tag = Tag(soup, "h2")
            aTag = Tag(soup, "a")
            aTag['name'] = "bytitle"
            h2Tag.insert(0,aTag)
            h2Tag.insert(1,NavigableString('By Title (%d)' % len(self.booksByTitle)))
            body.insert(btc,h2Tag)
            btc += 1
            '''

            # <p class="letter_index">
            # <p class="book_title">
            divTag = Tag(soup, "div")
            dtc = 0
            current_letter = ""

            # 2/14/10 7:11 AM Experimental: re-sort title list without leading series/series_index
            if not self.useSeriesPrefixInTitlesSection:
                nspt = deepcopy(self.booksByTitle)
                for book in nspt:
                    if book['series']:
                        tokens = book['title'].split(': ')
                        book['title'] = '%s (%s)' % (tokens[1], tokens[0])
                        book['title_sort'] = self.generateSortTitle(book['title'])
                nspt = sorted(nspt,
                                     key=lambda x:(x['title_sort'].upper(), x['title_sort'].upper()))
                self.booksByTitle_noSeriesPrefix = nspt
                if False and self.verbose:
                    self.opts.log.info("no_series_prefix_titles: %d books" % len(nspt))
                    self.opts.log.info(" %-40s %-40s" % ('title', 'title_sort'))
                    for title in nspt:
                        self.opts.log.info((u" %-40s %-40s" % (title['title'][0:40],
                                                               title['title_sort'][0:40])).encode('utf-8'))

            # Loop through the books by title
            title_list = self.booksByTitle
            if not self.useSeriesPrefixInTitlesSection:
                title_list = self.booksByTitle_noSeriesPrefix
            for book in title_list:
                if self.letter_or_symbol(book['title_sort'][0]) != current_letter :
                    # Start a new letter
                    current_letter = self.letter_or_symbol(book['title_sort'][0])
                    pIndexTag = Tag(soup, "p")
                    pIndexTag['class'] = "letter_index"
                    aTag = Tag(soup, "a")
                    aTag['name'] = "%s" % self.letter_or_symbol(book['title_sort'][0])
                    pIndexTag.insert(0,aTag)
                    pIndexTag.insert(1,NavigableString(self.letter_or_symbol(book['title_sort'][0])))
                    divTag.insert(dtc,pIndexTag)
                    dtc += 1

                # Add books
                pBookTag = Tag(soup, "p")
                ptc = 0

                #  book with read/reading/unread symbol
                if book['read']:
                    # check mark
                    pBookTag.insert(ptc,NavigableString(self.READ_SYMBOL))
                    pBookTag['class'] = "read_book"
                    ptc += 1
                elif book['id'] in self.bookmarked_books:
                    pBookTag.insert(ptc,NavigableString(self.READING_SYMBOL))
                    pBookTag['class'] = "read_book"
                    ptc += 1
                else:
                    # hidden check mark
                    pBookTag['class'] = "unread_book"
                    pBookTag.insert(ptc,NavigableString(self.NOT_READ_SYMBOL))
                    ptc += 1

                # Link to book
                aTag = Tag(soup, "a")
                aTag['href'] = "book_%d.html" % (int(float(book['id'])))
                aTag.insert(0,escape(book['title']))
                pBookTag.insert(ptc, aTag)
                ptc += 1

                # Dot
                pBookTag.insert(ptc, NavigableString(" &middot; "))
                ptc += 1

                # Link to author
                emTag = Tag(soup, "em")
                aTag = Tag(soup, "a")
                aTag['href'] = "%s.html#%s" % ("ByAlphaAuthor", self.generateAuthorAnchor(book['author']))
                aTag.insert(0, NavigableString(book['author']))
                emTag.insert(0,aTag)
                pBookTag.insert(ptc, emTag)
                ptc += 1

                divTag.insert(dtc, pBookTag)
                dtc += 1

            # Add the divTag to the body
            body.insert(btc, divTag)
            btc += 1

            # Write the volume to contentdir
            outfile_spec = "%s/ByAlphaTitle.html" % (self.contentDir)
            outfile = open(outfile_spec, 'w')
            outfile.write(soup.prettify())
            outfile.close()
            self.htmlFileList.append("content/ByAlphaTitle.html")

        def generateHTMLByAuthor(self):
            # Write books by author A-Z
            self.updateProgressFullStep("'Authors'")

            friendly_name = "By Author"

            soup = self.generateHTMLEmptyHeader(friendly_name)
            body = soup.find('body')

            btc = 0

            # Insert section tag
            aTag = Tag(soup,'a')
            aTag['name'] = 'section_start'
            body.insert(btc, aTag)
            btc += 1

            # Insert the anchor
            aTag = Tag(soup, "a")
            anchor_name = friendly_name.lower()
            aTag['name'] = anchor_name.replace(" ","")
            body.insert(btc, aTag)
            btc += 1
            '''
            # We don't need this because the kindle inserts section titles
            #<h2><a name="byalphaauthor" id="byalphaauthor"></a>By Author</h2>
            h2Tag = Tag(soup, "h2")
            aTag = Tag(soup, "a")
            anchor_name = friendly_name.lower()
            aTag['name'] = anchor_name.replace(" ","")
            h2Tag.insert(0,aTag)
            h2Tag.insert(1,NavigableString('%s' % friendly_name))
            body.insert(btc,h2Tag)
            btc += 1
            '''

            # <p class="letter_index">
            # <p class="author_index">
            divTag = Tag(soup, "div")
            dtc = 0
            current_letter = ""
            current_author = ""
            current_series = None

            # Loop through booksByAuthor
            book_count = 0
            for book in self.booksByAuthor:
                book_count += 1
                if self.letter_or_symbol(book['author_sort'][0].upper()) != current_letter :
                    '''
                    # Start a new letter - anchor only, hidden
                    current_letter = book['author_sort'][0].upper()
                    aTag = Tag(soup, "a")
                    aTag['name'] = "%sauthors" % current_letter
                    divTag.insert(dtc, aTag)
                    dtc += 1
                    '''
                    # Start a new letter with Index letter
                    current_letter = self.letter_or_symbol(book['author_sort'][0].upper())
                    pIndexTag = Tag(soup, "p")
                    pIndexTag['class'] = "letter_index"
                    aTag = Tag(soup, "a")
                    aTag['name'] = "%sauthors" % self.letter_or_symbol(current_letter)
                    pIndexTag.insert(0,aTag)
                    pIndexTag.insert(1,NavigableString(self.letter_or_symbol(book['author_sort'][0].upper())))
                    divTag.insert(dtc,pIndexTag)
                    dtc += 1

                if book['author'] != current_author:
                    # Start a new author
                    current_author = book['author']
                    non_series_books = 0
                    current_series = None
                    pAuthorTag = Tag(soup, "p")
                    pAuthorTag['class'] = "author_index"
                    emTag = Tag(soup, "em")
                    aTag = Tag(soup, "a")
                    aTag['name'] = "%s" % self.generateAuthorAnchor(current_author)
                    aTag.insert(0,NavigableString(current_author))
                    emTag.insert(0,aTag)
                    pAuthorTag.insert(0,emTag)
                    divTag.insert(dtc,pAuthorTag)
                    dtc += 1

                # Insert an <hr /> between non-series and series
                if not current_series and non_series_books and book['series']:
                    # Insert an <hr />
                    hrTag = Tag(soup,'hr')
                    hrTag['class'] = "series_divider"
                    divTag.insert(dtc,hrTag)
                    dtc += 1

                # Check for series
                if book['series'] and book['series'] != current_series:
                    # Start a new series
                    current_series = book['series']
                    pSeriesTag = Tag(soup,'p')
                    pSeriesTag['class'] = "series"
                    pSeriesTag.insert(0,NavigableString(self.NOT_READ_SYMBOL + book['series']))
                    divTag.insert(dtc,pSeriesTag)
                    dtc += 1
                if current_series and not book['series']:
                    current_series = None

                # Add books
                pBookTag = Tag(soup, "p")
                ptc = 0

                #  book with read/reading/unread symbol
                if book['read']:
                    # check mark
                    pBookTag.insert(ptc,NavigableString(self.READ_SYMBOL))
                    pBookTag['class'] = "read_book"
                    ptc += 1
                elif book['id'] in self.bookmarked_books:
                    pBookTag.insert(ptc,NavigableString(self.READING_SYMBOL))
                    pBookTag['class'] = "read_book"
                    ptc += 1
                else:
                    # hidden check mark
                    pBookTag['class'] = "unread_book"
                    pBookTag.insert(ptc,NavigableString(self.NOT_READ_SYMBOL))
                    ptc += 1

                aTag = Tag(soup, "a")
                aTag['href'] = "book_%d.html" % (int(float(book['id'])))
                # Use series, series index if avail else just title
                if current_series:
                    aTag.insert(0,escape(book['title'][len(book['series'])+1:]))
                else:
                    aTag.insert(0,escape(book['title']))
                    non_series_books += 1
                pBookTag.insert(ptc, aTag)
                ptc += 1

                divTag.insert(dtc, pBookTag)
                dtc += 1

            '''
            # Insert the <h2> tag with book_count at the head
            #<h2><a name="byalphaauthor" id="byalphaauthor"></a>By Author</h2>
            h2Tag = Tag(soup, "h2")
            aTag = Tag(soup, "a")
            anchor_name = friendly_name.lower()
            aTag['name'] = anchor_name.replace(" ","")
            h2Tag.insert(0,aTag)
            h2Tag.insert(1,NavigableString('%s (%d)' % (friendly_name, book_count)))
            body.insert(btc,h2Tag)
            btc += 1
            '''

            # Add the divTag to the body
            body.insert(btc, divTag)


            # Write the generated file to contentdir
            outfile_spec = "%s/ByAlphaAuthor.html" % (self.contentDir)
            outfile = open(outfile_spec, 'w')
            outfile.write(soup.prettify())
            outfile.close()
            self.htmlFileList.append("content/ByAlphaAuthor.html")

        def generateHTMLByDateAdded(self):
            # Write books by reverse chronological order
            self.updateProgressFullStep("'Recently Added'")

            def add_books_to_HTML_by_month(this_months_list, dtc):
                if len(this_months_list):

                    this_months_list.sort(self.author_compare)

                    # Create a new month anchor
                    date_string = strftime(u'%B %Y', current_date.timetuple())
                    pIndexTag = Tag(soup, "p")
                    pIndexTag['class'] = "date_index"
                    aTag = Tag(soup, "a")
                    aTag['name'] = "bda_%s-%s" % (current_date.year, current_date.month)
                    pIndexTag.insert(0,aTag)
                    pIndexTag.insert(1,NavigableString(date_string))
                    divTag.insert(dtc,pIndexTag)
                    dtc += 1
                    current_author = None
                    current_series = None

                    for new_entry in this_months_list:
                        if new_entry['author'] != current_author:
                            # Start a new author
                            current_author = new_entry['author']
                            non_series_books = 0
                            current_series = None
                            pAuthorTag = Tag(soup, "p")
                            pAuthorTag['class'] = "author_index"
                            emTag = Tag(soup, "em")
                            aTag = Tag(soup, "a")
                            aTag['name'] = "%s" % self.generateAuthorAnchor(current_author)
                            aTag.insert(0,NavigableString(current_author))
                            emTag.insert(0,aTag)
                            pAuthorTag.insert(0,emTag)
                            divTag.insert(dtc,pAuthorTag)
                            dtc += 1

                        # Insert an <hr /> between non-series and series
                        if not current_series and non_series_books and new_entry['series']:
                            # Insert an <hr />
                            hrTag = Tag(soup,'hr')
                            hrTag['class'] = "series_divider"
                            divTag.insert(dtc,hrTag)
                            dtc += 1

                        # Check for series
                        if new_entry['series'] and new_entry['series'] != current_series:
                            # Start a new series
                            current_series = new_entry['series']
                            pSeriesTag = Tag(soup,'p')
                            pSeriesTag['class'] = "series"
                            pSeriesTag.insert(0,NavigableString(self.NOT_READ_SYMBOL + new_entry['series']))
                            divTag.insert(dtc,pSeriesTag)
                            dtc += 1
                        if current_series and not new_entry['series']:
                            current_series = None

                        # Add books
                        pBookTag = Tag(soup, "p")
                        ptc = 0

                        #  book with read/reading/unread symbol
                        if new_entry['read']:
                            # check mark
                            pBookTag.insert(ptc,NavigableString(self.READ_SYMBOL))
                            pBookTag['class'] = "read_book"
                            ptc += 1
                        elif new_entry['id'] in self.bookmarked_books:
                            pBookTag.insert(ptc,NavigableString(self.READING_SYMBOL))
                            pBookTag['class'] = "read_book"
                            ptc += 1
                        else:
                            # hidden check mark
                            pBookTag['class'] = "unread_book"
                            pBookTag.insert(ptc,NavigableString(self.NOT_READ_SYMBOL))
                            ptc += 1

                        aTag = Tag(soup, "a")
                        aTag['href'] = "book_%d.html" % (int(float(new_entry['id'])))
                        if current_series:
                            aTag.insert(0,escape(new_entry['title'][len(new_entry['series'])+1:]))
                        else:
                            aTag.insert(0,escape(new_entry['title']))
                            non_series_books += 1
                        pBookTag.insert(ptc, aTag)
                        ptc += 1

                        divTag.insert(dtc, pBookTag)
                        dtc += 1
                return dtc

            def add_books_to_HTML_by_date_range(date_range_list, date_range, dtc):
                if len(date_range_list):
                    pIndexTag = Tag(soup, "p")
                    pIndexTag['class'] = "date_index"
                    aTag = Tag(soup, "a")
                    aTag['name'] = "bda_%s" % date_range.replace(' ','')
                    pIndexTag.insert(0,aTag)
                    pIndexTag.insert(1,NavigableString(date_range))
                    divTag.insert(dtc,pIndexTag)
                    dtc += 1

                    for new_entry in date_range_list:
                        # Add books
                        pBookTag = Tag(soup, "p")
                        ptc = 0

                        #  book with read/reading/unread symbol
                        if new_entry['read']:
                            # check mark
                            pBookTag.insert(ptc,NavigableString(self.READ_SYMBOL))
                            pBookTag['class'] = "read_book"
                            ptc += 1
                        elif new_entry['id'] in self.bookmarked_books:
                            pBookTag.insert(ptc,NavigableString(self.READING_SYMBOL))
                            pBookTag['class'] = "read_book"
                            ptc += 1
                        else:
                            # hidden check mark
                            pBookTag['class'] = "unread_book"
                            pBookTag.insert(ptc,NavigableString(self.NOT_READ_SYMBOL))
                            ptc += 1

                        aTag = Tag(soup, "a")
                        aTag['href'] = "book_%d.html" % (int(float(new_entry['id'])))
                        aTag.insert(0,escape(new_entry['title']))
                        pBookTag.insert(ptc, aTag)
                        ptc += 1

                        # Dot
                        pBookTag.insert(ptc, NavigableString(" &middot; "))
                        ptc += 1

                        # Link to author
                        emTag = Tag(soup, "em")
                        aTag = Tag(soup, "a")
                        aTag['href'] = "%s.html#%s" % ("ByAlphaAuthor", self.generateAuthorAnchor(new_entry['author']))
                        aTag.insert(0, NavigableString(new_entry['author']))
                        emTag.insert(0,aTag)
                        pBookTag.insert(ptc, emTag)
                        ptc += 1

                        divTag.insert(dtc, pBookTag)
                        dtc += 1
                return dtc

            friendly_name = "Recently Added"

            soup = self.generateHTMLEmptyHeader(friendly_name)
            body = soup.find('body')

            btc = 0

            # Insert section tag
            aTag = Tag(soup,'a')
            aTag['name'] = 'section_start'
            body.insert(btc, aTag)
            btc += 1

            # Insert the anchor
            aTag = Tag(soup, "a")
            anchor_name = friendly_name.lower()
            aTag['name'] = anchor_name.replace(" ","")
            body.insert(btc, aTag)
            btc += 1
            '''
            # We don't need this because the kindle inserts section titles
            #<h2><a name="byalphaauthor" id="byalphaauthor"></a>By Author</h2>
            h2Tag = Tag(soup, "h2")
            aTag = Tag(soup, "a")
            anchor_name = friendly_name.lower()
            aTag['name'] = anchor_name.replace(" ","")
            h2Tag.insert(0,aTag)
            h2Tag.insert(1,NavigableString('%s' % friendly_name))
            body.insert(btc,h2Tag)
            btc += 1
            '''

            # <p class="letter_index">
            # <p class="author_index">
            divTag = Tag(soup, "div")
            dtc = 0

            # Add books by date range
            if self.useSeriesPrefixInTitlesSection:
                self.booksByDateRange = sorted(self.booksByTitle,
                                 key=lambda x:(x['timestamp'], x['timestamp']),reverse=True)
            else:
                nspt = deepcopy(self.booksByTitle)
                for book in nspt:
                    if book['series']:
                        tokens = book['title'].split(': ')
                        book['title'] = '%s (%s)' % (tokens[1], tokens[0])
                        book['title_sort'] = self.generateSortTitle(book['title'])
                self.booksByDateRange = sorted(nspt, key=lambda x:(x['timestamp'], x['timestamp']),reverse=True)

            date_range_list = []
            today_time = nowf().replace(hour=23, minute=59, second=59)
            books_added_in_date_range = False
            for (i, date) in enumerate(self.DATE_RANGE):
                date_range_limit = self.DATE_RANGE[i]
                if i:
                    date_range = '%d to %d days ago' % (self.DATE_RANGE[i-1], self.DATE_RANGE[i])
                else:
                    date_range = 'Last %d days' % (self.DATE_RANGE[i])

                for book in self.booksByDateRange:
                    book_time = book['timestamp']
                    delta = today_time-book_time
                    if delta.days <= date_range_limit:
                        date_range_list.append(book)
                        books_added_in_date_range = True
                    else:
                        break

                dtc = add_books_to_HTML_by_date_range(date_range_list, date_range, dtc)
                date_range_list = [book]

            if books_added_in_date_range:
                # Add an <hr> separating date ranges from months
                hrTag = Tag(soup,'hr')
                divTag.insert(dtc,hrTag)
                dtc += 1

            # >>>> Books by month <<<<
            # Sort titles case-insensitive for by month using series prefix
            self.booksByMonth = sorted(self.booksByTitle,
                                 key=lambda x:(x['timestamp'], x['timestamp']),reverse=True)

            # Loop through books by date
            current_date = datetime.date.fromordinal(1)
            this_months_list = []
            for book in self.booksByMonth:
                if book['timestamp'].month != current_date.month or \
                   book['timestamp'].year != current_date.year:
                    dtc = add_books_to_HTML_by_month(this_months_list, dtc)
                    this_months_list = []
                    current_date = book['timestamp'].date()
                this_months_list.append(book)

            # Add the last month's list
            add_books_to_HTML_by_month(this_months_list, dtc)

            # Add the divTag to the body
            body.insert(btc, divTag)

            # Write the generated file to contentdir
            outfile_spec = "%s/ByDateAdded.html" % (self.contentDir)
            outfile = open(outfile_spec, 'w')
            outfile.write(soup.prettify())
            outfile.close()
            self.htmlFileList.append("content/ByDateAdded.html")

        def generateHTMLByDateRead(self):
            # Write books by active bookmarks
            friendly_name = 'Recently Read'
            self.updateProgressFullStep("'%s'" % friendly_name)
            if not self.bookmarked_books:
                return

            def add_books_to_HTML_by_day(todays_list, dtc):
                if len(todays_list):
                    # Create a new day anchor
                    date_string = strftime(u'%A, %B %d', current_date.timetuple())
                    pIndexTag = Tag(soup, "p")
                    pIndexTag['class'] = "date_index"
                    aTag = Tag(soup, "a")
                    aTag['name'] = "bdr_%s-%s-%s" % (current_date.year, current_date.month, current_date.day)
                    pIndexTag.insert(0,aTag)
                    pIndexTag.insert(1,NavigableString(date_string))
                    divTag.insert(dtc,pIndexTag)
                    dtc += 1

                    for new_entry in todays_list:
                        pBookTag = Tag(soup, "p")
                        pBookTag['class'] = "date_read"
                        ptc = 0

                        # Percent read
                        pBookTag.insert(ptc, NavigableString(new_entry['reading_progress']))
                        ptc += 1

                        aTag = Tag(soup, "a")
                        aTag['href'] = "book_%d.html" % (int(float(new_entry['id'])))
                        aTag.insert(0,escape(new_entry['title']))
                        pBookTag.insert(ptc, aTag)
                        ptc += 1

                        # Dot
                        pBookTag.insert(ptc, NavigableString(" &middot; "))
                        ptc += 1

                        # Link to author
                        emTag = Tag(soup, "em")
                        aTag = Tag(soup, "a")
                        aTag['href'] = "%s.html#%s" % ("ByAlphaAuthor", self.generateAuthorAnchor(new_entry['author']))
                        aTag.insert(0, NavigableString(new_entry['author']))
                        emTag.insert(0,aTag)
                        pBookTag.insert(ptc, emTag)
                        ptc += 1

                        divTag.insert(dtc, pBookTag)
                        dtc += 1
                return dtc

            def add_books_to_HTML_by_date_range(date_range_list, date_range, dtc):
                if len(date_range_list):
                    pIndexTag = Tag(soup, "p")
                    pIndexTag['class'] = "date_index"
                    aTag = Tag(soup, "a")
                    aTag['name'] = "bdr_%s" % date_range.replace(' ','')
                    pIndexTag.insert(0,aTag)
                    pIndexTag.insert(1,NavigableString(date_range))
                    divTag.insert(dtc,pIndexTag)
                    dtc += 1

                    for new_entry in date_range_list:
                        # Add books
                        pBookTag = Tag(soup, "p")
                        pBookTag['class'] = "date_read"
                        ptc = 0

                        # Percent read
                        dots = int((new_entry['percent_read'] + 5)/10)
                        dot_string = self.READ_PROGRESS_SYMBOL * dots
                        empty_dots = self.UNREAD_PROGRESS_SYMBOL * (10 - dots)
                        pBookTag.insert(ptc, NavigableString('%s%s' % (dot_string,empty_dots)))
                        ptc += 1

                        aTag = Tag(soup, "a")
                        aTag['href'] = "book_%d.html" % (int(float(new_entry['id'])))
                        aTag.insert(0,escape(new_entry['title']))
                        pBookTag.insert(ptc, aTag)
                        ptc += 1

                        # Dot
                        pBookTag.insert(ptc, NavigableString(" &middot; "))
                        ptc += 1

                        # Link to author
                        emTag = Tag(soup, "em")
                        aTag = Tag(soup, "a")
                        aTag['href'] = "%s.html#%s" % ("ByAlphaAuthor", self.generateAuthorAnchor(new_entry['author']))
                        aTag.insert(0, NavigableString(new_entry['author']))
                        emTag.insert(0,aTag)
                        pBookTag.insert(ptc, emTag)
                        ptc += 1

                        divTag.insert(dtc, pBookTag)
                        dtc += 1
                return dtc

            soup = self.generateHTMLEmptyHeader(friendly_name)
            body = soup.find('body')

            btc = 0

            # Insert section tag
            aTag = Tag(soup,'a')
            aTag['name'] = 'section_start'
            body.insert(btc, aTag)
            btc += 1

            # Insert the anchor
            aTag = Tag(soup, "a")
            anchor_name = friendly_name.lower()
            aTag['name'] = anchor_name.replace(" ","")
            body.insert(btc, aTag)
            btc += 1

            # <p class="letter_index">
            # <p class="author_index">
            divTag = Tag(soup, "div")
            dtc = 0

            # self.bookmarked_books: (Bookmark, book)
            bookmarked_books = []
            for bm_book in self.bookmarked_books:
                book = self.bookmarked_books[bm_book]
                #print "bm_book: %s" % bm_book
                book[1]['bookmark_timestamp'] = book[0].timestamp
                book[1]['percent_read'] = float(100*book[0].last_read_location / book[0].book_length)
                bookmarked_books.append(book[1])

            self.booksByDateRead = sorted(bookmarked_books,
                             key=lambda x:(x['bookmark_timestamp'], x['bookmark_timestamp']),reverse=True)

            '''
            # >>>> Recently by date range <<<<
            date_range_list = []
            today_time = datetime.datetime.utcnow()
            today_time.replace(hour=23, minute=59, second=59)
            books_added_in_date_range = False
            for (i, date) in enumerate(self.DATE_RANGE):
                date_range_limit = self.DATE_RANGE[i]
                if i:
                    date_range = '%d to %d days ago' % (self.DATE_RANGE[i-1], self.DATE_RANGE[i])
                else:
                    date_range = 'Last %d days' % (self.DATE_RANGE[i])

                for book in self.booksByDateRead:
                    bookmark_time = datetime.datetime.utcfromtimestamp(book['bookmark_timestamp'])
                    delta = today_time-bookmark_time
                    if delta.days <= date_range_limit:
                        date_range_list.append(book)
                        books_added_in_date_range = True
                    else:
                        break

                dtc = add_books_to_HTML_by_date_range(date_range_list, date_range, dtc)
                date_range_list = [book]
            '''

            # >>>> Recently read by day <<<<
            current_date = datetime.date.fromordinal(1)
            todays_list = []
            for book in self.booksByDateRead:
                bookmark_time = datetime.datetime.utcfromtimestamp(book['bookmark_timestamp'])
                if bookmark_time.day != current_date.day or \
                   bookmark_time.month != current_date.month or \
                   bookmark_time.year != current_date.year:
                    dtc = add_books_to_HTML_by_day(todays_list, dtc)
                    todays_list = []
                    current_date = datetime.datetime.utcfromtimestamp(book['bookmark_timestamp']).date()
                todays_list.append(book)

            # Add the last day's list
            add_books_to_HTML_by_day(todays_list, dtc)

            # Add the divTag to the body
            body.insert(btc, divTag)

            # Write the generated file to contentdir
            outfile_spec = "%s/ByDateRead.html" % (self.contentDir)
            outfile = open(outfile_spec, 'w')
            outfile.write(soup.prettify())
            outfile.close()
            self.htmlFileList.append("content/ByDateRead.html")

        def generateHTMLByTags(self):
            # Generate individual HTML files for each tag, e.g. Fiction, Nonfiction ...
            # Note that special tags - ~+*[] -  have already been filtered from books[]
            # There may be synonomous tags

            self.updateProgressFullStep("'Genres'")

            self.genre_tags_dict = self.filterDbTags(self.db.all_tags())

            # Extract books matching filtered_tags
            genre_list = []
            for friendly_tag in sorted(self.genre_tags_dict):
                #print "\ngenerateHTMLByTags(): looking for books with friendly_tag '%s'" % friendly_tag
                # tag_list => { normalized_genre_tag : [{book},{},{}],
                #               normalized_genre_tag : [{book},{},{}] }

                tag_list = {}
                for book in self.booksByAuthor:
                    # Scan each book for tag matching friendly_tag
                    if 'tags' in book and friendly_tag in book['tags']:
                        this_book = {}
                        this_book['author'] = book['author']
                        this_book['title'] = book['title']
                        this_book['author_sort'] = book['author_sort'].capitalize()
                        this_book['read'] = book['read']
                        this_book['id'] = book['id']
                        this_book['series'] = book['series']
                        normalized_tag = self.genre_tags_dict[friendly_tag]
                        genre_tag_list = [key for genre in genre_list for key in genre]
                        if normalized_tag in genre_tag_list:
                            for existing_genre in genre_list:
                                for key in existing_genre:
                                    new_book = None
                                    if key == normalized_tag:
                                        for book in existing_genre[key]:
                                            if book['title'] == this_book['title']:
                                                new_book = False
                                                break
                                        else:
                                            new_book = True
                                    if new_book:
                                        existing_genre[key].append(this_book)
                        else:
                            tag_list[normalized_tag] = [this_book]
                            genre_list.append(tag_list)

            if self.opts.verbose:
                self.opts.log.info("     Genre summary: %d active genre tags used in generating catalog with %d titles" %
                                    (len(genre_list), len(self.booksByTitle)))

                for genre in genre_list:
                    for key in genre:
                        self.opts.log.info("      %s: %d %s" % (self.getFriendlyGenreTag(key),
                                           len(genre[key]),
                                           'titles' if len(genre[key]) > 1 else 'title'))

            # Write the results
            # genre_list = [ {friendly_tag:[{book},{book}]}, {friendly_tag:[{book},{book}]}, ...]
            master_genre_list = []
            for genre_tag_set in genre_list:
                for (index, genre) in enumerate(genre_tag_set):
                    #print "genre: %s  \t  genre_tag_set[genre]: %s" % (genre, genre_tag_set[genre])

                    # Create sorted_authors[0] = friendly, [1] = author_sort for NCX creation
                    authors = []
                    for book in genre_tag_set[genre]:
                        authors.append((book['author'],book['author_sort']))

                    # authors[] contains a list of all book authors, with multiple entries for multiple books by author
                    # Create unique_authors with a count of books per author as the third tuple element
                    books_by_current_author = 1
                    current_author = authors[0]
                    unique_authors = []
                    for (i,author) in enumerate(authors):
                        if author != current_author and i:
                            unique_authors.append((current_author[0], current_author[1], books_by_current_author))
                            current_author = author
                            books_by_current_author = 1
                        elif i==0 and len(authors) == 1:
                            # Allow for single-book lists
                            unique_authors.append((current_author[0], current_author[1], books_by_current_author))
                        else:
                            books_by_current_author += 1
                    '''
                    # Extract the unique entries
                    unique_authors = []
                    for author in authors:
                        if not author in unique_authors:
                            unique_authors.append(author)
                    '''
                    # Write the genre book list as an article
                    titles_spanned = self.generateHTMLByGenre(genre, True if index==0 else False,
                                          genre_tag_set[genre],
                                          "%s/Genre_%s.html" % (self.contentDir,
                                                                genre))

                    tag_file = "content/Genre_%s.html" % genre
                    master_genre_list.append({'tag':genre,
                                              'file':tag_file,
                                              'authors':unique_authors,
                                              'books':genre_tag_set[genre],
                                              'titles_spanned':titles_spanned})

            if False and self.opts.verbose:
                for genre in master_genre_list:
                    print "genre['tag']: %s" % genre['tag']
                    for book in genre['books']:
                        print book['title']
            self.genres = master_genre_list

        def generateThumbnails(self):
            # Generate a thumbnail per cover.  If a current thumbnail exists, skip
            # If a cover doesn't exist, use default
            # Return list of active thumbs

            self.updateProgressFullStep("'Thumbnails'")
            thumbs = ['thumbnail_default.jpg']
            image_dir = "%s/images" % self.catalogPath
            for (i,title) in enumerate(self.booksByTitle):
                # Update status
                self.updateProgressMicroStep("Thumbnail %d of %d" % \
                    (i,len(self.booksByTitle)),
                        i/float(len(self.booksByTitle)))
                # Check to see if source file exists
                if 'cover' in title and os.path.isfile(title['cover']):
                    # Add the thumb spec to thumbs[]
                    thumbs.append("thumbnail_%d.jpg" % int(title['id']))

                    # Check to see if thumbnail exists
                    thumb_fp = "%s/thumbnail_%d.jpg" % (image_dir,int(title['id']))
                    thumb_file = 'thumbnail_%d.jpg' % int(title['id'])
                    if os.path.isfile(thumb_fp):
                        # Check to see if cover is newer than thumbnail
                        # os.path.getmtime() = modified time
                        # os.path.ctime() = creation time
                        cover_timestamp = os.path.getmtime(title['cover'])
                        thumb_timestamp = os.path.getmtime(thumb_fp)
                        if thumb_timestamp < cover_timestamp:
                           self.generateThumbnail(title, image_dir, thumb_file)
                    else:
                        self.generateThumbnail(title, image_dir, thumb_file)
                else:
                    # Use default cover
                    if False and self.verbose:
                        self.opts.log.warn(" using default cover for '%s'" % \
                        (title['title']))
                    # Check to make sure default is current
                    # Check to see if thumbnail exists
                    thumb_fp = "%s/thumbnail_default.jpg" % (image_dir)
                    cover = "%s/DefaultCover.png" % (self.catalogPath)

                    # Init Qt for image conversion
                    from calibre.gui2 import is_ok_to_use_qt
                    if is_ok_to_use_qt():
                        from PyQt4.Qt import QImage, QColor, QPainter, Qt

                        # Convert .svg to .jpg
                        cover_img = QImage(I('book.svg'))
                        i = QImage(cover_img.size(),
                                QImage.Format_ARGB32_Premultiplied)
                        i.fill(QColor(Qt.white).rgb())
                        p = QPainter(i)
                        p.drawImage(0, 0, cover_img)
                        p.end()
                        i.save(cover)
                    else:
                        if not os.path.exists(cover):
                            shutil.copyfile(I('library.png'), cover)

                    if os.path.isfile(thumb_fp):
                        # Check to see if default cover is newer than thumbnail
                        # os.path.getmtime() = modified time
                        # os.path.ctime() = creation time
                        cover_timestamp = os.path.getmtime(cover)
                        thumb_timestamp = os.path.getmtime(thumb_fp)
                        if thumb_timestamp < cover_timestamp:
                            if False and self.verbose:
                                self.opts.log.warn("updating thumbnail_default for %s" % title['title'])
                            #title['cover'] = "%s/DefaultCover.jpg" % self.catalogPath
                            title['cover'] = cover
                            self.generateThumbnail(title, image_dir, "thumbnail_default.jpg")
                    else:
                        if False and self.verbose:
                            self.opts.log.warn(" generating new thumbnail_default.jpg")
                        #title['cover'] = "%s/DefaultCover.jpg" % self.catalogPath
                        title['cover'] = cover
                        self.generateThumbnail(title, image_dir, "thumbnail_default.jpg")

            self.thumbs = thumbs

        def generateOPF(self):

            self.updateProgressFullStep("Generating OPF")

            header = '''
                <?xml version="1.0" encoding="UTF-8"?>
                <package xmlns="http://www.idpf.org/2007/opf" version="2.0" unique-identifier="calibre_id">
                    <metadata xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:opf="http://www.idpf.org/2007/opf" xmlns:calibre="http://calibre.kovidgoyal.net/2009/metadata" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
                        <dc:language>en-US</dc:language>
                        <meta name="calibre:publication_type" content="periodical:default"/>
                    </metadata>
                    <manifest></manifest>
                    <spine toc="ncx"></spine>
                    <guide></guide>
                </package>
                '''
            # Add the supplied metadata tags
            soup = BeautifulStoneSoup(header, selfClosingTags=['item','itemref', 'reference'])
            metadata = soup.find('metadata')
            mtc = 0

            titleTag = Tag(soup, "dc:title")
            titleTag.insert(0,self.title)
            metadata.insert(mtc, titleTag)
            mtc += 1

            creatorTag = Tag(soup, "dc:creator")
            creatorTag.insert(0, self.creator)
            metadata.insert(mtc, creatorTag)
            mtc += 1

            # Create the OPF tags
            manifest = soup.find('manifest')
            mtc = 0
            spine = soup.find('spine')
            stc = 0
            guide = soup.find('guide')

            itemTag = Tag(soup, "item")
            itemTag['id'] = "ncx"
            itemTag['href'] = '%s.ncx' % self.basename
            itemTag['media-type'] = "application/x-dtbncx+xml"
            manifest.insert(mtc, itemTag)
            mtc += 1

            itemTag = Tag(soup, "item")
            itemTag['id'] = 'stylesheet'
            itemTag['href'] = self.stylesheet
            itemTag['media-type'] = 'text/css'
            manifest.insert(mtc, itemTag)
            mtc += 1

            itemTag = Tag(soup, "item")
            itemTag['id'] = 'mastheadimage-image'
            itemTag['href'] = "images/mastheadImage.gif"
            itemTag['media-type'] = 'image/gif'
            manifest.insert(mtc, itemTag)
            mtc += 1

            # Write the thumbnail images to the manifest
            for thumb in self.thumbs:
                itemTag = Tag(soup, "item")
                itemTag['href'] = "images/%s" % (thumb)
                end = thumb.find('.jpg')
                itemTag['id'] = "%s-image" % thumb[:end]
                itemTag['media-type'] = 'image/jpeg'
                manifest.insert(mtc, itemTag)
                mtc += 1

            # HTML files - add books to manifest and spine
            sort_descriptions_by = self.booksByAuthor if self.opts.sort_descriptions_by_author \
                                                      else self.booksByTitle
            for book in sort_descriptions_by:
                # manifest
                itemTag = Tag(soup, "item")
                itemTag['href'] = "content/book_%d.html" % int(book['id'])
                itemTag['id'] = "book%d" % int(book['id'])
                itemTag['media-type'] = "application/xhtml+xml"
                manifest.insert(mtc, itemTag)
                mtc += 1

                # spine
                itemrefTag = Tag(soup, "itemref")
                itemrefTag['idref'] = "book%d" % int(book['id'])
                spine.insert(stc, itemrefTag)
                stc += 1

            # Add other html_files to manifest and spine

            for file in self.htmlFileList:
                itemTag = Tag(soup, "item")
                start = file.find('/') + 1
                end = file.find('.')
                itemTag['href'] = file
                itemTag['id'] = file[start:end].lower()
                itemTag['media-type'] = "application/xhtml+xml"
                manifest.insert(mtc, itemTag)
                mtc += 1

                # spine
                itemrefTag = Tag(soup, "itemref")
                itemrefTag['idref'] = file[start:end].lower()
                spine.insert(stc, itemrefTag)
                stc += 1

            # Add genre files to manifest and spine
            for genre in self.genres:
                if False: self.opts.log.info("adding %s to manifest and spine" % genre['tag'])
                itemTag = Tag(soup, "item")
                start = genre['file'].find('/') + 1
                end = genre['file'].find('.')
                itemTag['href'] = genre['file']
                itemTag['id'] = genre['file'][start:end].lower()
                itemTag['media-type'] = "application/xhtml+xml"
                manifest.insert(mtc, itemTag)
                mtc += 1

                # spine
                itemrefTag = Tag(soup, "itemref")
                itemrefTag['idref'] = genre['file'][start:end].lower()
                spine.insert(stc, itemrefTag)
                stc += 1

            # Guide
            referenceTag = Tag(soup, "reference")
            referenceTag['type'] = 'masthead'
            referenceTag['title'] = 'mastheadimage-image'
            referenceTag['href'] = 'images/mastheadImage.gif'
            guide.insert(0,referenceTag)

            # Write the OPF file
            outfile = open("%s/%s.opf" % (self.catalogPath, self.basename), 'w')
            outfile.write(soup.prettify())

        def generateNCXHeader(self):

            self.updateProgressFullStep("NCX header")

            header = '''
                <?xml version="1.0" encoding="utf-8"?>
                <ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" xmlns:calibre="http://calibre.kovidgoyal.net/2009/metadata" version="2005-1" xml:lang="en">
                </ncx>
            '''
            soup = BeautifulStoneSoup(header, selfClosingTags=['content','calibre:meta-img'])

            ncx = soup.find('ncx')
            navMapTag = Tag(soup, 'navMap')
            navPointTag = Tag(soup, 'navPoint')
            navPointTag['class'] = "periodical"
            navPointTag['id'] = "title"
            navPointTag['playOrder'] = self.playOrder
            self.playOrder += 1
            navLabelTag = Tag(soup, 'navLabel')
            textTag = Tag(soup, 'text')
            textTag.insert(0, NavigableString(self.title))
            navLabelTag.insert(0, textTag)
            navPointTag.insert(0, navLabelTag)
            contentTag = Tag(soup, 'content')
            contentTag['src'] = "content/book_%d.html" % int(self.booksByTitle[0]['id'])
            navPointTag.insert(1, contentTag)
            cmiTag = Tag(soup, '%s' % 'calibre:meta-img')
            cmiTag['name'] = "mastheadImage"
            cmiTag['src'] = "images/mastheadImage.gif"
            navPointTag.insert(2,cmiTag)
            navMapTag.insert(0,navPointTag)

            ncx.insert(0,navMapTag)

            self.ncxSoup = soup

        def generateNCXDescriptions(self, tocTitle):

            self.updateProgressFullStep("NCX 'Descriptions'")

            # --- Construct the 'Books by Title' section ---
            ncx_soup = self.ncxSoup
            body = ncx_soup.find("navPoint")
            btc = len(body.contents)

            # Add the section navPoint
            navPointTag = Tag(ncx_soup, 'navPoint')
            navPointTag['class'] = "section"
            navPointTag['id'] = "bytitle-ID"
            navPointTag['playOrder'] = self.playOrder
            self.playOrder += 1
            navLabelTag = Tag(ncx_soup, 'navLabel')
            textTag = Tag(ncx_soup, 'text')
            textTag.insert(0, NavigableString(tocTitle))
            navLabelTag.insert(0, textTag)
            nptc = 0
            navPointTag.insert(nptc, navLabelTag)
            nptc += 1
            contentTag = Tag(ncx_soup,"content")
            contentTag['src'] = "content/book_%d.html" % int(self.booksByTitle[0]['id'])
            navPointTag.insert(nptc, contentTag)
            nptc += 1

            # Loop over the titles
            sort_descriptions_by = self.booksByAuthor if self.opts.sort_descriptions_by_author \
                                                      else self.booksByTitle

            for book in sort_descriptions_by:
                navPointVolumeTag = Tag(ncx_soup, 'navPoint')
                navPointVolumeTag['class'] = "article"
                navPointVolumeTag['id'] = "book%dID" % int(book['id'])
                navPointVolumeTag['playOrder'] = self.playOrder
                self.playOrder += 1
                navLabelTag = Tag(ncx_soup, "navLabel")
                textTag = Tag(ncx_soup, "text")
                if book['series']:
                    tokens = book['title'].split(': ')
                    if self.generateForKindle:
                        # Don't include Author for Kindle
                        textTag.insert(0, NavigableString(self.formatNCXText('%s (%s)' % \
                                                      (tokens[1], tokens[0]), dest='title')))
                    else:
                        # Include Author for non-Kindle
                        textTag.insert(0, NavigableString(self.formatNCXText('%s &middot; %s (%s)' % \
                                                      (tokens[1], book['author'], tokens[0]), dest='title')))
                else:
                    if self.generateForKindle:
                        # Don't include Author for Kindle
                        title_str = self.formatNCXText('%s' % (book['title']), dest='title')
                        if self.opts.connected_kindle and book['id'] in self.bookmarked_books:
                            '''
                            dots = int((book['percent_read'] + 5)/10)
                            dot_string = '+' * dots
                            empty_dots = '-' * (10 - dots)
                            title_str += ' %s%s' % (dot_string,empty_dots)
                            '''
                            title_str += '*'
                        textTag.insert(0, NavigableString(title_str))
                    else:
                        # Include Author for non-Kindle
                        textTag.insert(0, NavigableString(self.formatNCXText('%s &middot; %s' % \
                                                      (book['title'], book['author']), dest='title')))
                navLabelTag.insert(0,textTag)
                navPointVolumeTag.insert(0,navLabelTag)

                contentTag = Tag(ncx_soup, "content")
                contentTag['src'] = "content/book_%d.html#book%d" % (int(book['id']), int(book['id']))
                navPointVolumeTag.insert(1, contentTag)

                if self.generateForKindle:
                    # Add the author tag
                    cmTag = Tag(ncx_soup, '%s' % 'calibre:meta')
                    cmTag['name'] = "author"
                    navStr = '%s | %s' % (self.formatNCXText(book['author'], dest='author'),
                          book['date'].split()[1])
                    if 'tags' in book and len(book['tags']):
                        navStr = self.formatNCXText(navStr + ' | ' + ' &middot; '.join(sorted(book['tags'])), dest='author')
                    cmTag.insert(0, NavigableString(navStr))
                    navPointVolumeTag.insert(2, cmTag)

                    # Add the description tag
                    if book['short_description']:
                        cmTag = Tag(ncx_soup, '%s' % 'calibre:meta')
                        cmTag['name'] = "description"
                        cmTag.insert(0, NavigableString(self.formatNCXText(book['short_description'], dest='description')))
                        navPointVolumeTag.insert(3, cmTag)

                # Add this volume to the section tag
                navPointTag.insert(nptc, navPointVolumeTag)
                nptc += 1

            # Add this section to the body
            body.insert(btc, navPointTag)
            btc += 1

            self.ncxSoup = ncx_soup

        def generateNCXByTitle(self, tocTitle):
            self.updateProgressFullStep("NCX 'Titles'")

            def add_to_books_by_letter(current_book_list):
                current_book_list = " &bull; ".join(current_book_list)
                current_book_list = self.formatNCXText(current_book_list, dest="description")
                books_by_letter.append(current_book_list)

            soup = self.ncxSoup
            output = "ByAlphaTitle"
            body = soup.find("navPoint")
            btc = len(body.contents)

            # --- Construct the 'Books By Title' section ---
            navPointTag = Tag(soup, 'navPoint')
            navPointTag['class'] = "section"
            navPointTag['id'] = "byalphatitle-ID"
            navPointTag['playOrder'] = self.playOrder
            self.playOrder += 1
            navLabelTag = Tag(soup, 'navLabel')
            textTag = Tag(soup, 'text')
            textTag.insert(0, NavigableString(tocTitle))
            navLabelTag.insert(0, textTag)
            nptc = 0
            navPointTag.insert(nptc, navLabelTag)
            nptc += 1
            contentTag = Tag(soup,"content")
            contentTag['src'] = "content/%s.html#section_start" % (output)
            navPointTag.insert(nptc, contentTag)
            nptc += 1

            books_by_letter = []

            # Loop over the titles, find start of each letter, add description_preview_count books
            # Special switch for using different title list
            if self.useSeriesPrefixInTitlesSection:
                title_list = self.booksByTitle
            else:
                title_list = self.booksByTitle_noSeriesPrefix
            current_letter = self.letter_or_symbol(title_list[0]['title_sort'][0])
            title_letters = [current_letter]
            current_book_list = []
            current_book = ""
            for book in title_list:
                if self.letter_or_symbol(book['title_sort'][0]) != current_letter:
                    # Save the old list
                    add_to_books_by_letter(current_book_list)

                    # Start the new list
                    current_letter = self.letter_or_symbol(book['title_sort'][0])
                    title_letters.append(current_letter)
                    current_book = book['title']
                    current_book_list = [book['title']]
                else:
                    if len(current_book_list) < self.descriptionClip and \
                       book['title'] != current_book :
                        current_book = book['title']
                        current_book_list.append(book['title'])

            # Add the last book list
            add_to_books_by_letter(current_book_list)

            # Add *article* entries for each populated title letter
            for (i,books) in enumerate(books_by_letter):
                navPointByLetterTag = Tag(soup, 'navPoint')
                navPointByLetterTag['class'] = "article"
                navPointByLetterTag['id'] = "%sTitles-ID" % (title_letters[i].upper())
                navPointTag['playOrder'] = self.playOrder
                self.playOrder += 1
                navLabelTag = Tag(soup, 'navLabel')
                textTag = Tag(soup, 'text')
                textTag.insert(0, NavigableString(u"Titles beginning with %s" % \
                    (title_letters[i] if len(title_letters[i])>1 else "'" + title_letters[i] + "'")))
                navLabelTag.insert(0, textTag)
                navPointByLetterTag.insert(0,navLabelTag)
                contentTag = Tag(soup, 'content')
                contentTag['src'] = "content/%s.html#%s" % (output, title_letters[i])
                navPointByLetterTag.insert(1,contentTag)

                if self.generateForKindle:
                    cmTag = Tag(soup, '%s' % 'calibre:meta')
                    cmTag['name'] = "description"
                    cmTag.insert(0, NavigableString(self.formatNCXText(books, dest='description')))
                    navPointByLetterTag.insert(2, cmTag)

                navPointTag.insert(nptc, navPointByLetterTag)
                nptc += 1

            # Add this section to the body
            body.insert(btc, navPointTag)
            btc += 1

            self.ncxSoup = soup

        def generateNCXByAuthor(self, tocTitle):
            self.updateProgressFullStep("NCX 'Authors'")

            def add_to_author_list(current_author_list, current_letter):
                current_author_list = " &bull; ".join(current_author_list)
                current_author_list = self.formatNCXText(current_author_list, dest="description")
                master_author_list.append((current_author_list, current_letter))

            soup = self.ncxSoup
            HTML_file = "content/ByAlphaAuthor.html"
            body = soup.find("navPoint")
            btc = len(body.contents)

            # --- Construct the 'Books By Author' *section* ---
            navPointTag = Tag(soup, 'navPoint')
            navPointTag['class'] = "section"
            file_ID = "%s" % tocTitle.lower()
            file_ID = file_ID.replace(" ","")
            navPointTag['id'] = "%s-ID" % file_ID
            navPointTag['playOrder'] = self.playOrder
            self.playOrder += 1
            navLabelTag = Tag(soup, 'navLabel')
            textTag = Tag(soup, 'text')
            textTag.insert(0, NavigableString('%s' % tocTitle))
            navLabelTag.insert(0, textTag)
            nptc = 0
            navPointTag.insert(nptc, navLabelTag)
            nptc += 1
            contentTag = Tag(soup,"content")
            contentTag['src'] = "%s#section_start" % HTML_file
            navPointTag.insert(nptc, contentTag)
            nptc += 1

            # Create an NCX article entry for each populated author index letter
            # Loop over the sorted_authors list, find start of each letter,
            # add description_preview_count artists
            # self.authors[0]:friendly [1]:author_sort [2]:book_count
            master_author_list = []
            # self.authors[0][1][0] = Initial letter of author_sort[0]
            current_letter = self.letter_or_symbol(self.authors[0][1][0])
            current_author_list = []
            for author in self.authors:
                if self.letter_or_symbol(author[1][0]) != current_letter:
                    # Save the old list
                    add_to_author_list(current_author_list, current_letter)

                    # Start the new list
                    current_letter = self.letter_or_symbol(author[1][0])
                    current_author_list = [author[0]]
                else:
                    if len(current_author_list) < self.descriptionClip:
                        current_author_list.append(author[0])

            # Add the last author list
            add_to_author_list(current_author_list, current_letter)

            # Add *article* entries for each populated author initial letter
            # master_author_list{}: [0]:author list [1]:Initial letter
            for authors_by_letter in master_author_list:
                navPointByLetterTag = Tag(soup, 'navPoint')
                navPointByLetterTag['class'] = "article"
                navPointByLetterTag['id'] = "%sauthors-ID" % (authors_by_letter[1])
                navPointTag['playOrder'] = self.playOrder
                self.playOrder += 1
                navLabelTag = Tag(soup, 'navLabel')
                textTag = Tag(soup, 'text')
                textTag.insert(0, NavigableString("Authors beginning with '%s'" % (authors_by_letter[1])))
                navLabelTag.insert(0, textTag)
                navPointByLetterTag.insert(0,navLabelTag)
                contentTag = Tag(soup, 'content')
                contentTag['src'] = "%s#%sauthors" % (HTML_file, authors_by_letter[1])

                navPointByLetterTag.insert(1,contentTag)

                if self.generateForKindle:
                    cmTag = Tag(soup, '%s' % 'calibre:meta')
                    cmTag['name'] = "description"
                    cmTag.insert(0, NavigableString(authors_by_letter[0]))
                    navPointByLetterTag.insert(2, cmTag)

                navPointTag.insert(nptc, navPointByLetterTag)
                nptc += 1

            # Add this section to the body
            body.insert(btc, navPointTag)
            btc += 1

            self.ncxSoup = soup

        def generateNCXByDateAdded(self, tocTitle):
            self.updateProgressFullStep("NCX 'Recently Added'")

            def add_to_master_month_list(current_titles_list):
                book_count = len(current_titles_list)
                current_titles_list = " &bull; ".join(current_titles_list)
                current_titles_list = self.formatNCXText(current_titles_list, dest='description')
                master_month_list.append((current_titles_list, current_date, book_count))

            def add_to_master_date_range_list(current_titles_list):
                book_count = len(current_titles_list)
                current_titles_list = " &bull; ".join(current_titles_list)
                current_titles_list = self.formatNCXText(current_titles_list, dest='description')
                master_date_range_list.append((current_titles_list, date_range, book_count))

            soup = self.ncxSoup
            HTML_file = "content/ByDateAdded.html"
            body = soup.find("navPoint")
            btc = len(body.contents)

            # --- Construct the 'Recently Added' *section* ---
            navPointTag = Tag(soup, 'navPoint')
            navPointTag['class'] = "section"
            file_ID = "%s" % tocTitle.lower()
            file_ID = file_ID.replace(" ","")
            navPointTag['id'] = "%s-ID" % file_ID
            navPointTag['playOrder'] = self.playOrder
            self.playOrder += 1
            navLabelTag = Tag(soup, 'navLabel')
            textTag = Tag(soup, 'text')
            textTag.insert(0, NavigableString('%s' % tocTitle))
            navLabelTag.insert(0, textTag)
            nptc = 0
            navPointTag.insert(nptc, navLabelTag)
            nptc += 1
            contentTag = Tag(soup,"content")
            contentTag['src'] = "%s#section_start" % HTML_file
            navPointTag.insert(nptc, contentTag)
            nptc += 1

            # Create an NCX article entry for each date range
            current_titles_list = []
            master_date_range_list = []
            today = datetime.datetime.now()
            today_time = datetime.datetime(today.year, today.month, today.day)
            for (i,date) in enumerate(self.DATE_RANGE):
                if i:
                    date_range = '%d to %d days ago' % (self.DATE_RANGE[i-1], self.DATE_RANGE[i])
                else:
                    date_range = 'Last %d days' % (self.DATE_RANGE[i])
                date_range_limit = self.DATE_RANGE[i]
                for book in self.booksByDateRange:
                    book_time = datetime.datetime(book['timestamp'].year, book['timestamp'].month, book['timestamp'].day)
                    if (today_time-book_time).days <= date_range_limit:
                        #print "generateNCXByDateAdded: %s added %d days ago" % (book['title'], (today_time-book_time).days)
                        current_titles_list.append(book['title'])
                    else:
                        break
                if current_titles_list:
                    add_to_master_date_range_list(current_titles_list)
                current_titles_list = [book['title']]

            # Add *article* entries for each populated date range
            # master_date_range_list{}: [0]:titles list [1]:datestr
            for books_by_date_range in master_date_range_list:
                navPointByDateRangeTag = Tag(soup, 'navPoint')
                navPointByDateRangeTag['class'] = "article"
                navPointByDateRangeTag['id'] = "%s-ID" %  books_by_date_range[1].replace(' ','')
                navPointTag['playOrder'] = self.playOrder
                self.playOrder += 1
                navLabelTag = Tag(soup, 'navLabel')
                textTag = Tag(soup, 'text')
                textTag.insert(0, NavigableString(books_by_date_range[1]))
                navLabelTag.insert(0, textTag)
                navPointByDateRangeTag.insert(0,navLabelTag)
                contentTag = Tag(soup, 'content')
                contentTag['src'] = "%s#bda_%s" % (HTML_file,
                    books_by_date_range[1].replace(' ',''))

                navPointByDateRangeTag.insert(1,contentTag)

                if self.generateForKindle:
                    cmTag = Tag(soup, '%s' % 'calibre:meta')
                    cmTag['name'] = "description"
                    cmTag.insert(0, NavigableString(books_by_date_range[0]))
                    navPointByDateRangeTag.insert(2, cmTag)

                    cmTag = Tag(soup, '%s' % 'calibre:meta')
                    cmTag['name'] = "author"
                    navStr = '%d titles' % books_by_date_range[2] if books_by_date_range[2] > 1 else \
                             '%d title' % books_by_date_range[2]
                    cmTag.insert(0, NavigableString(navStr))
                    navPointByDateRangeTag.insert(3, cmTag)

                navPointTag.insert(nptc, navPointByDateRangeTag)
                nptc += 1



            # Create an NCX article entry for each populated month
            # Loop over the booksByDate list, find start of each month,
            # add description_preview_count titles
            # master_month_list(list,date,count)
            current_titles_list = []
            master_month_list = []
            current_date = self.booksByMonth[0]['timestamp']

            for book in self.booksByMonth:
                if book['timestamp'].month != current_date.month or \
                   book['timestamp'].year != current_date.year:
                    # Save the old lists
                    add_to_master_month_list(current_titles_list)

                    # Start the new list
                    current_date = book['timestamp'].date()
                    current_titles_list = [book['title']]
                else:
                    current_titles_list.append(book['title'])

            # Add the last month list
            add_to_master_month_list(current_titles_list)

            # Add *article* entries for each populated month
            # master_months_list{}: [0]:titles list [1]:date
            for books_by_month in master_month_list:
                datestr = strftime(u'%B %Y', books_by_month[1].timetuple())
                navPointByMonthTag = Tag(soup, 'navPoint')
                navPointByMonthTag['class'] = "article"
                navPointByMonthTag['id'] = "bda_%s-%s-ID" % (books_by_month[1].year,books_by_month[1].month )
                navPointTag['playOrder'] = self.playOrder
                self.playOrder += 1
                navLabelTag = Tag(soup, 'navLabel')
                textTag = Tag(soup, 'text')
                textTag.insert(0, NavigableString(datestr))
                navLabelTag.insert(0, textTag)
                navPointByMonthTag.insert(0,navLabelTag)
                contentTag = Tag(soup, 'content')
                contentTag['src'] = "%s#bda_%s-%s" % (HTML_file,
                    books_by_month[1].year,books_by_month[1].month)

                navPointByMonthTag.insert(1,contentTag)

                if self.generateForKindle:
                    cmTag = Tag(soup, '%s' % 'calibre:meta')
                    cmTag['name'] = "description"
                    cmTag.insert(0, NavigableString(books_by_month[0]))
                    navPointByMonthTag.insert(2, cmTag)

                    cmTag = Tag(soup, '%s' % 'calibre:meta')
                    cmTag['name'] = "author"
                    navStr = '%d titles' % books_by_month[2] if books_by_month[2] > 1 else \
                             '%d title' % books_by_month[2]
                    cmTag.insert(0, NavigableString(navStr))
                    navPointByMonthTag.insert(3, cmTag)

                navPointTag.insert(nptc, navPointByMonthTag)
                nptc += 1

            # Add this section to the body
            body.insert(btc, navPointTag)
            btc += 1
            self.ncxSoup = soup

        def generateNCXByDateRead(self, tocTitle):
            self.updateProgressFullStep("NCX 'Recently Read'")
            if not self.booksByDateRead:
                return

            def add_to_master_day_list(current_titles_list):
                book_count = len(current_titles_list)
                current_titles_list = " &bull; ".join(current_titles_list)
                current_titles_list = self.formatNCXText(current_titles_list, dest='description')
                master_day_list.append((current_titles_list, current_date, book_count))

            def add_to_master_date_range_list(current_titles_list):
                book_count = len(current_titles_list)
                current_titles_list = " &bull; ".join(current_titles_list)
                current_titles_list = self.formatNCXText(current_titles_list, dest='description')
                master_date_range_list.append((current_titles_list, date_range, book_count))

            soup = self.ncxSoup
            HTML_file = "content/ByDateRead.html"
            body = soup.find("navPoint")
            btc = len(body.contents)

            # --- Construct the 'Recently Read' *section* ---
            navPointTag = Tag(soup, 'navPoint')
            navPointTag['class'] = "section"
            file_ID = "%s" % tocTitle.lower()
            file_ID = file_ID.replace(" ","")
            navPointTag['id'] = "%s-ID" % file_ID
            navPointTag['playOrder'] = self.playOrder
            self.playOrder += 1
            navLabelTag = Tag(soup, 'navLabel')
            textTag = Tag(soup, 'text')
            textTag.insert(0, NavigableString('%s' % tocTitle))
            navLabelTag.insert(0, textTag)
            nptc = 0
            navPointTag.insert(nptc, navLabelTag)
            nptc += 1
            contentTag = Tag(soup,"content")
            contentTag['src'] = "%s#section_start" % HTML_file
            navPointTag.insert(nptc, contentTag)
            nptc += 1

            # Create an NCX article entry for each date range
            current_titles_list = []
            master_date_range_list = []
            today = datetime.datetime.now()
            today_time = datetime.datetime(today.year, today.month, today.day)
            for (i,date) in enumerate(self.DATE_RANGE):
                if i:
                    date_range = '%d to %d days ago' % (self.DATE_RANGE[i-1], self.DATE_RANGE[i])
                else:
                    date_range = 'Last %d days' % (self.DATE_RANGE[i])
                date_range_limit = self.DATE_RANGE[i]
                for book in self.booksByDateRead:
                    bookmark_time = datetime.datetime.utcfromtimestamp(book['bookmark_timestamp'])
                    if (today_time-bookmark_time).days <= date_range_limit:
                        #print "generateNCXByDateAdded: %s added %d days ago" % (book['title'], (today_time-book_time).days)
                        current_titles_list.append(book['title'])
                    else:
                        break
                if current_titles_list:
                    add_to_master_date_range_list(current_titles_list)
                current_titles_list = [book['title']]

            '''
            # Add *article* entries for each populated date range
            # master_date_range_list{}: [0]:titles list [1]:datestr
            for books_by_date_range in master_date_range_list:
                navPointByDateRangeTag = Tag(soup, 'navPoint')
                navPointByDateRangeTag['class'] = "article"
                navPointByDateRangeTag['id'] = "%s-ID" %  books_by_date_range[1].replace(' ','')
                navPointTag['playOrder'] = self.playOrder
                self.playOrder += 1
                navLabelTag = Tag(soup, 'navLabel')
                textTag = Tag(soup, 'text')
                textTag.insert(0, NavigableString(books_by_date_range[1]))
                navLabelTag.insert(0, textTag)
                navPointByDateRangeTag.insert(0,navLabelTag)
                contentTag = Tag(soup, 'content')
                contentTag['src'] = "%s#bdr_%s" % (HTML_file,
                    books_by_date_range[1].replace(' ',''))

                navPointByDateRangeTag.insert(1,contentTag)

                if self.generateForKindle:
                    cmTag = Tag(soup, '%s' % 'calibre:meta')
                    cmTag['name'] = "description"
                    cmTag.insert(0, NavigableString(books_by_date_range[0]))
                    navPointByDateRangeTag.insert(2, cmTag)

                    cmTag = Tag(soup, '%s' % 'calibre:meta')
                    cmTag['name'] = "author"
                    navStr = '%d titles' % books_by_date_range[2] if books_by_date_range[2] > 1 else \
                             '%d title' % books_by_date_range[2]
                    cmTag.insert(0, NavigableString(navStr))
                    navPointByDateRangeTag.insert(3, cmTag)

                navPointTag.insert(nptc, navPointByDateRangeTag)
                nptc += 1
            '''

            # Create an NCX article entry for each populated day
            # Loop over the booksByDate list, find start of each month,
            # add description_preview_count titles
            # master_month_list(list,date,count)
            current_titles_list = []
            master_day_list = []
            current_date = datetime.datetime.utcfromtimestamp(self.booksByDateRead[0]['bookmark_timestamp'])

            for book in self.booksByDateRead:
                bookmark_time = datetime.datetime.utcfromtimestamp(book['bookmark_timestamp'])
                if bookmark_time.day != current_date.day or \
                   bookmark_time.month != current_date.month or \
                   bookmark_time.year != current_date.year:
                    # Save the old lists
                    add_to_master_day_list(current_titles_list)

                    # Start the new list
                    current_date = datetime.datetime.utcfromtimestamp(book['bookmark_timestamp']).date()
                    current_titles_list = [book['title']]
                else:
                    current_titles_list.append(book['title'])

            # Add the last day list
            add_to_master_day_list(current_titles_list)

            # Add *article* entries for each populated day
            # master_day_list{}: [0]:titles list [1]:date
            for books_by_day in master_day_list:
                datestr = strftime(u'%A, %B %d', books_by_day[1].timetuple())
                navPointByDayTag = Tag(soup, 'navPoint')
                navPointByDayTag['class'] = "article"
                navPointByDayTag['id'] = "bdr_%s-%s-%sID" % (books_by_day[1].year,
                                                             books_by_day[1].month,
                                                             books_by_day[1].day )
                navPointTag['playOrder'] = self.playOrder
                self.playOrder += 1
                navLabelTag = Tag(soup, 'navLabel')
                textTag = Tag(soup, 'text')
                textTag.insert(0, NavigableString(datestr))
                navLabelTag.insert(0, textTag)
                navPointByDayTag.insert(0,navLabelTag)
                contentTag = Tag(soup, 'content')
                contentTag['src'] = "%s#bdr_%s-%s-%s" % (HTML_file,
                                                         books_by_day[1].year,
                                                         books_by_day[1].month,
                                                         books_by_day[1].day)

                navPointByDayTag.insert(1,contentTag)

                if self.generateForKindle:
                    cmTag = Tag(soup, '%s' % 'calibre:meta')
                    cmTag['name'] = "description"
                    cmTag.insert(0, NavigableString(books_by_day[0]))
                    navPointByDayTag.insert(2, cmTag)

                    cmTag = Tag(soup, '%s' % 'calibre:meta')
                    cmTag['name'] = "author"
                    navStr = '%d titles' % books_by_day[2] if books_by_day[2] > 1 else \
                             '%d title' % books_by_day[2]
                    cmTag.insert(0, NavigableString(navStr))
                    navPointByDayTag.insert(3, cmTag)

                navPointTag.insert(nptc, navPointByDayTag)
                nptc += 1

            # Add this section to the body
            body.insert(btc, navPointTag)
            btc += 1
            self.ncxSoup = soup

        def generateNCXByGenre(self, tocTitle):
            # Create an NCX section for 'By Genre'
            # Add each genre as an article
            # 'tag', 'file', 'authors'

            self.updateProgressFullStep("NCX 'Genres'")

            if not len(self.genres):
                self.opts.log.warn(" No genres found in tags.\n"
                                   " No Genre section added to Catalog")
                return

            ncx_soup = self.ncxSoup
            body = ncx_soup.find("navPoint")
            btc = len(body.contents)

            # --- Construct the 'Books By Genre' *section* ---
            navPointTag = Tag(ncx_soup, 'navPoint')
            navPointTag['class'] = "section"
            file_ID = "%s" % tocTitle.lower()
            file_ID = file_ID.replace(" ","")
            navPointTag['id'] = "%s-ID" % file_ID
            navPointTag['playOrder'] = self.playOrder
            self.playOrder += 1
            navLabelTag = Tag(ncx_soup, 'navLabel')
            textTag = Tag(ncx_soup, 'text')
            # textTag.insert(0, NavigableString('%s (%d)' % (section_title, len(genre_list))))
            textTag.insert(0, NavigableString('%s' % tocTitle))
            navLabelTag.insert(0, textTag)
            nptc = 0
            navPointTag.insert(nptc, navLabelTag)
            nptc += 1
            contentTag = Tag(ncx_soup,"content")
            contentTag['src'] = "content/Genre_%s.html#section_start" % self.genres[0]['tag']
            navPointTag.insert(nptc, contentTag)
            nptc += 1

            for genre in self.genres:
                # Add an article for each genre
                navPointVolumeTag = Tag(ncx_soup, 'navPoint')
                navPointVolumeTag['class'] = "article"
                navPointVolumeTag['id'] = "genre-%s-ID" % genre['tag']
                navPointVolumeTag['playOrder'] = self.playOrder
                self.playOrder += 1
                navLabelTag = Tag(ncx_soup, "navLabel")
                textTag = Tag(ncx_soup, "text")

                # GwR *** Can this be optimized?
                normalized_tag = None
                for friendly_tag in self.genre_tags_dict:
                    if self.genre_tags_dict[friendly_tag] == genre['tag']:
                        normalized_tag = self.genre_tags_dict[friendly_tag]
                        break
                textTag.insert(0, self.formatNCXText(NavigableString(friendly_tag), dest='description'))
                navLabelTag.insert(0,textTag)
                navPointVolumeTag.insert(0,navLabelTag)
                contentTag = Tag(ncx_soup, "content")
                contentTag['src'] = "content/Genre_%s.html#Genre_%s" % (normalized_tag, normalized_tag)
                navPointVolumeTag.insert(1, contentTag)

                if self.generateForKindle:
                    # Build the author tag
                    cmTag = Tag(ncx_soup, '%s' % 'calibre:meta')
                    cmTag['name'] = "author"
                    # First - Last author

                    if len(genre['titles_spanned']) > 1 :
                        author_range = "%s - %s" % (genre['titles_spanned'][0][0], genre['titles_spanned'][1][0])
                    else :
                        author_range = "%s" % (genre['titles_spanned'][0][0])

                    cmTag.insert(0, NavigableString(author_range))
                    navPointVolumeTag.insert(2, cmTag)

                    # Build the description tag
                    cmTag = Tag(ncx_soup, '%s' % 'calibre:meta')
                    cmTag['name'] = "description"

                    if False:
                        # Form 1: Titles spanned
                        if len(genre['titles_spanned']) > 1:
                            title_range = "%s -\n%s" % (genre['titles_spanned'][0][1], genre['titles_spanned'][1][1])
                        else:
                            title_range = "%s" % (genre['titles_spanned'][0][1])
                        cmTag.insert(0, NavigableString(self.formatNCXText(title_range, dest='description')))
                    else:
                        # Form 2: title &bull; title &bull; title ...
                        titles = []
                        for title in genre['books']:
                            titles.append(title['title'])
                        titles = sorted(titles, key=lambda x:(self.generateSortTitle(x),self.generateSortTitle(x)))
                        titles_list = self.generateShortDescription(u" &bull; ".join(titles), dest="description")
                        cmTag.insert(0, NavigableString(self.formatNCXText(titles_list, dest='description')))

                    navPointVolumeTag.insert(3, cmTag)

                # Add this volume to the section tag
                navPointTag.insert(nptc, navPointVolumeTag)
                nptc += 1

            # Add this section to the body
            body.insert(btc, navPointTag)
            btc += 1

            self.ncxSoup = ncx_soup

        def writeNCX(self):
            self.updateProgressFullStep("Saving NCX")

            outfile = open("%s/%s.ncx" % (self.catalogPath, self.basename), 'w')
            outfile.write(self.ncxSoup.prettify())

        # Helpers
        def author_to_author_sort(self, author):
            tokens = author.split()
            tokens = tokens[-1:] + tokens[:-1]
            if len(tokens) > 1:
                tokens[0] += ','
            return ' '.join(tokens).capitalize()

        def author_compare(self,x,y):
            # Return -1 if x<y
            # Return  0 if x==y
            # Return  1 if x>y

            # Different authors - sort by author_sort
            if x['author_sort'].capitalize() > y['author_sort'].capitalize():
                return 1
            elif x['author_sort'].capitalize() < y['author_sort'].capitalize():
                return -1
            else:
                # Same author
                if x['series'] != y['series']:
                    # One title is a series, the other is not
                    if not x['series']:
                        # Sort regular titles < series titles
                        return -1
                    elif not y['series']:
                        return 1

                    # Different series
                    if x['title_sort'].lstrip() > y['title_sort'].lstrip():
                        return 1
                    else:
                        return -1
                else:
                    # Same series
                    if x['series'] == y['series']:
                        if float(x['series_index']) > float(y['series_index']):
                            return 1
                        elif float(x['series_index']) < float(y['series_index']):
                            return -1
                        else:
                            return 0
                    else:
                        if x['series'] > y['series']:
                            return 1
                        else:
                            return -1

        def calculateThumbnailSize(self):
            ''' Calculate thumbnail dimensions based on device DPI.  Scale Kindle by 50% '''
            from calibre.customize.ui import output_profiles
            for x in output_profiles():
                if x.short_name == self.opts.output_profile:
                    # .9" width  aspect ratio: 3:4
                    self.thumbWidth = int(x.dpi * .9)
                    self.thumbHeight = int(self.thumbWidth * 1.33)
                    if 'kindle' in x.short_name and self.opts.fmt == 'mobi':
                        # Kindle DPI appears to be off by a factor of 2
                        self.thumbWidth = int(self.thumbWidth/2)
                        self.thumbHeight = int(self.thumbHeight/2)
                    break
            if False and self.verbose:
                self.opts.log("     DPI = %d; thumbnail dimensions: %d x %d" % \
                              (x.dpi, self.thumbWidth, self.thumbHeight))

        def convertHTMLEntities(self, s):
            matches = re.findall("&#\d+;", s)
            if len(matches) > 0:
                hits = set(matches)
                for hit in hits:
                        name = hit[2:-1]
                        try:
                                entnum = int(name)
                                s = s.replace(hit, unichr(entnum))
                        except ValueError:
                                pass

            matches = re.findall("&\w+;", s)
            hits = set(matches)
            amp = "&amp;"
            if amp in hits:
                hits.remove(amp)
            for hit in hits:
                name = hit[1:-1]
                if htmlentitydefs.name2codepoint.has_key(name):
                        s = s.replace(hit, unichr(htmlentitydefs.name2codepoint[name]))
            s = s.replace(amp, "&")
            return s

        def createDirectoryStructure(self):
            catalogPath = self.catalogPath
            self.cleanUp()

            if not os.path.isdir(catalogPath):
                os.makedirs(catalogPath)

            # Create /content and /images
            content_path = catalogPath + "/content"
            if not os.path.isdir(content_path):
                os.makedirs(content_path)
            images_path = catalogPath + "/images"
            if not os.path.isdir(images_path):
                os.makedirs(images_path)

        def filterDbTags(self, tags):
            # Remove the special marker tags from the database's tag list,
            # return sorted list of normalized genre tags

            normalized_tags = []
            friendly_tags = []
            for tag in tags:
                if tag[0] in self.markerTags:
                    continue
                if re.search(self.opts.exclude_genre, tag):
                    continue
                if tag == ' ':
                    continue

                normalized_tags.append(re.sub('\W','',tag).lower())
                friendly_tags.append(tag)

            genre_tags_dict = dict(zip(friendly_tags,normalized_tags))

            # Test for multiple genres resolving to same normalized form
            normalized_set = set(normalized_tags)
            for normalized in normalized_set:
                if normalized_tags.count(normalized) > 1:
                    self.opts.log.warn("      Warning: multiple tags resolving to genre '%s':" % normalized)
                    for key in genre_tags_dict:
                        if genre_tags_dict[key] == normalized:
                            self.opts.log.warn("       %s" % key)
            if self.verbose:
                def next_tag(tags):
                    for (i, tag) in enumerate(tags):
                        if i < len(tags) - 1:
                            yield tag + ", "
                        else:
                            yield tag

                self.opts.log.info(u'     %d genre tags in database (excluding genres matching %s):' % \
                                     (len(genre_tags_dict), self.opts.exclude_genre))

                # Display friendly/normalized genres
                # friendly => normalized
                if False:
                    sorted_tags = ['%s => %s' % (key, genre_tags_dict[key]) for key in sorted(genre_tags_dict.keys())]
                    for tag in next_tag(sorted_tags):
                        self.opts.log(u'      %s' % tag)
                else:
                    sorted_tags = ['%s' % (key) for key in sorted(genre_tags_dict.keys())]
                    out_str = ''
                    line_break = 70
                    for tag in next_tag(sorted_tags):
                        out_str += tag
                        if len(out_str) >= line_break:
                            self.opts.log.info('      %s' % out_str)
                            out_str = ''
                    self.opts.log.info('      %s' % out_str)

            return genre_tags_dict

        def formatNCXText(self, description, dest=None):
            # Kindle TOC descriptions won't render certain characters
            # Fix up
            massaged = unicode(BeautifulStoneSoup(description, convertEntities=BeautifulStoneSoup.HTML_ENTITIES))

            # Replace '&' with '&#38;'
            massaged = re.sub("&","&#38;", massaged)

            if massaged.strip() and dest:
                #print traceback.print_stack(limit=3)
                return self.generateShortDescription(massaged.strip(), dest=dest)
            else:
                return None

        def generateAuthorAnchor(self, author):
            # Strip white space to ''
            return re.sub("\W","", author)

        def generateHTMLByGenre(self, genre, section_head, books, outfile):
            # Write an HTML file of this genre's book list
            # Return a list with [(first_author, first_book), (last_author, last_book)]

            soup = self.generateHTMLGenreHeader(genre)
            body = soup.find('body')

            btc = 0

            # Insert section tag if this is the section start - first article only
            if section_head:
                aTag = Tag(soup,'a')
                aTag['name'] = 'section_start'
                body.insert(btc, aTag)
                btc += 1

            # Create an anchor from the tag
            aTag = Tag(soup, 'a')
            aTag['name'] = "Genre_%s" % genre
            body.insert(btc,aTag)
            btc += 1

            titleTag = body.find(attrs={'class':'title'})
            titleTag.insert(0,NavigableString('<b><i>%s</i></b>' % escape(self.getFriendlyGenreTag(genre))))

            # Insert the books by author list
            divTag = body.find(attrs={'class':'authors'})
            dtc = 0

            current_author = ''
            current_series = None
            for book in books:
                if book['author'] != current_author:
                    # Start a new author with link
                    current_author = book['author']
                    non_series_books = 0
                    current_series = None
                    pAuthorTag = Tag(soup, "p")
                    pAuthorTag['class'] = "author_index"
                    emTag = Tag(soup, "em")
                    aTag = Tag(soup, "a")
                    aTag['href'] = "%s.html#%s" % ("ByAlphaAuthor", self.generateAuthorAnchor(book['author']))
                    aTag.insert(0, book['author'])
                    emTag.insert(0,aTag)
                    pAuthorTag.insert(0,emTag)
                    divTag.insert(dtc,pAuthorTag)
                    dtc += 1

                # Insert an <hr /> between non-series and series
                if not current_series and non_series_books and book['series']:
                    # Insert an <hr />
                    hrTag = Tag(soup,'hr')
                    hrTag['class'] = "series_divider"
                    divTag.insert(dtc,hrTag)
                    dtc += 1

                # Check for series
                if book['series'] and book['series'] != current_series:
                    # Start a new series
                    current_series = book['series']
                    pSeriesTag = Tag(soup,'p')
                    pSeriesTag['class'] = "series"
                    pSeriesTag.insert(0,NavigableString(self.NOT_READ_SYMBOL + book['series']))
                    divTag.insert(dtc,pSeriesTag)
                    dtc += 1

                if current_series and not book['series']:
                    current_series = None

                # Add books
                pBookTag = Tag(soup, "p")
                ptc = 0

                #  book with read/reading/unread symbol
                if book['read']:
                    # check mark
                    pBookTag.insert(ptc,NavigableString(self.READ_SYMBOL))
                    pBookTag['class'] = "read_book"
                    ptc += 1
                elif book['id'] in self.bookmarked_books:
                    pBookTag.insert(ptc,NavigableString(self.READING_SYMBOL))
                    pBookTag['class'] = "read_book"
                    ptc += 1
                else:
                    # hidden check mark
                    pBookTag['class'] = "unread_book"
                    pBookTag.insert(ptc,NavigableString(self.NOT_READ_SYMBOL))
                    ptc += 1

                # Add the book title
                aTag = Tag(soup, "a")
                aTag['href'] = "book_%d.html" % (int(float(book['id'])))
                # Use series, series index if avail else just title
                if current_series:
                    aTag.insert(0,escape(book['title'][len(book['series'])+1:]))
                else:
                    aTag.insert(0,escape(book['title']))
                    non_series_books += 1
                pBookTag.insert(ptc, aTag)
                ptc += 1

                divTag.insert(dtc, pBookTag)
                dtc += 1

            # Write the generated file to contentdir
            outfile = open(outfile, 'w')
            outfile.write(soup.prettify())
            outfile.close()

            if len(books) > 1:
                titles_spanned = [(books[0]['author'],books[0]['title']), (books[-1]['author'],books[-1]['title'])]
            else:
                titles_spanned = [(books[0]['author'],books[0]['title'])]

            return titles_spanned

        def generateHTMLDescriptionHeader(self, title):

            title_border = '' if self.opts.fmt == 'epub' else \
                    '<div class="hr"><blockquote><hr/></blockquote></div>'
            header = '''
            <!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.1//EN" "http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd">
            <html xmlns="http://www.w3.org/1999/xhtml" xmlns:calibre="http://calibre.kovidgoyal.net/2009/metadata">
            <head>
            <meta http-equiv="Content-Type" content="text/html; charset=UTF-8" />
                <link rel="stylesheet" type="text/css" href="stylesheet.css" media="screen" />
            <title></title>
            </head>
            <body>
            <p class="title"></p>
            {0}
            <p class="author"></p>
            <!--p class="series"></p-->
            <p class="tags">&nbsp;</p>
            <table width="100%" border="0">
              <tr>
                <td class="thumbnail" rowspan="7"></td>
                <td>&nbsp;</td>
                <td>&nbsp;</td>
              </tr>
              <tr>
                <td>&nbsp;</td>
                <td>&nbsp;</td>
              </tr>
              <tr>
                <td>Publisher</td>
                <td class="publisher"></td>
              </tr>
              <tr>
                <td>Published</td>
                <td class="date"></td>
              </tr>
              <tr>
                <td>Rating</td>
                <td class="rating"></td>
              </tr>
              <tr>
                <td class="notes_label">Notes</td>
                <td class="notes"></td>
              </tr>
              <tr>
                <td>&nbsp;</td>
                <td>&nbsp;</td>
              </tr>
            </table>
            <blockquote><hr/></blockquote>
            <div class="description"></div>
            </body>
            </html>
            '''.format(title_border)

            # Insert the supplied title
            soup = BeautifulSoup(header, selfClosingTags=['mbp:pagebreak'])
            titleTag = soup.find('title')
            titleTag.insert(0,NavigableString(escape(title)))
            return soup

        def generateHTMLEmptyHeader(self, title):
            header = '''
                <!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.1//EN" "http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd">
                <html xmlns="http://www.w3.org/1999/xhtml" xmlns:calibre="http://calibre.kovidgoyal.net/2009/metadata">
                <head>
                <meta http-equiv="Content-Type" content="text/html; charset=UTF-8" />
                    <link rel="stylesheet" type="text/css" href="stylesheet.css" media="screen" />
                <title></title>
                </head>
                <body>
                </body>
                </html>
                '''
            # Insert the supplied title
            soup = BeautifulSoup(header)
            titleTag = soup.find('title')
            titleTag.insert(0,NavigableString(title))
            return soup

        def generateHTMLGenreHeader(self, title):
            header = '''
                <!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.1//EN" "http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd">
                <html xmlns="http://www.w3.org/1999/xhtml" xmlns:calibre="http://calibre.kovidgoyal.net/2009/metadata">
                <head>
                <meta http-equiv="Content-Type" content="text/html; charset=UTF-8" />
                    <link rel="stylesheet" type="text/css" href="stylesheet.css" media="screen" />
                <title></title>
                </head>
                <body>
                    <p class="title"></p>
                    <div class="hr"><blockquote><hr/></blockquote></div>
                    <div class="authors"></div>
                </body>
                </html>
                '''
            # Insert the supplied title
            soup = BeautifulSoup(header)
            titleTag = soup.find('title')
            titleTag.insert(0,escape(NavigableString(title)))
            return soup

        def generateMastheadImage(self, out_path):
            from calibre.ebooks.conversion.config import load_defaults
            from calibre.utils.fonts import fontconfig
            font_path = default_font = P('fonts/liberation/LiberationSerif-Bold.ttf')
            recs = load_defaults('mobi_output')
            masthead_font_family = recs.get('masthead_font', 'Default')

            if masthead_font_family != 'Default':
                masthead_font = fontconfig.files_for_family(masthead_font_family)
                # Assume 'normal' always in dict, else use default
                # {'normal': (path_to_font, friendly name)}
                if 'normal' in masthead_font:
                    font_path = masthead_font['normal'][0]

            if not font_path or not os.access(font_path, os.R_OK):
                font_path = default_font

            MI_WIDTH = 600
            MI_HEIGHT = 60

            try:
                from PIL import Image, ImageDraw, ImageFont
                Image, ImageDraw, ImageFont
            except ImportError:
                import Image, ImageDraw, ImageFont

            img = Image.new('RGB', (MI_WIDTH, MI_HEIGHT), 'white')
            draw = ImageDraw.Draw(img)
            try:
                font = ImageFont.truetype(font_path, 48)
            except:
                self.opts.log.error("     Failed to load user-specifed font '%s'" % font_path)
                font = ImageFont.truetype(default_font, 48)
            text = self.title.encode('utf-8')
            width, height = draw.textsize(text, font=font)
            left = max(int((MI_WIDTH - width)/2.), 0)
            top = max(int((MI_HEIGHT - height)/2.), 0)
            draw.text((left, top), text, fill=(0,0,0), font=font)
            img.save(open(out_path, 'wb'), 'GIF')

        def generateSeriesTitle(self, title):
            if float(title['series_index']) - int(title['series_index']):
                series_title = '%s %4.2f: %s' % (title['series'],
                                                title['series_index'],
                                                title['title'])
            else:
                series_title = '%s %d: %s' % (title['series'],
                                             title['series_index'],
                                             title['title'])
            return series_title

        def generateShortDescription(self, description, dest=None):
            # Truncate the description, on word boundaries if necessary
            # Possible destinations:
            #  description  NCX summary
            #  title        NCX title
            #  author       NCX author

            def shortDescription(description, limit):
                short_description = ""
                words = description.split()
                for word in words:
                    short_description += word + " "
                    if len(short_description) > limit:
                        short_description += "..."
                        return short_description

            if not description:
                return None

            if dest == 'title':
                # No truncation for titles, let the device deal with it
                return description
            elif dest == 'author':
                if self.authorClip and len(description) < self.authorClip:
                    return description
                else:
                    return shortDescription(description, self.authorClip)
            elif dest == 'description':
                if self.descriptionClip and len(description) < self.descriptionClip:
                    return description
                else:
                    return shortDescription(description, self.descriptionClip)
            else:
                print " returning description with unspecified destination '%s'" % description
                raise RuntimeError

        def generateSortTitle(self, title):
            # Convert the actual title to a string suitable for sorting.
            # Ignore leading stop words
            # Optionally convert leading numbers to strings
            from calibre.ebooks.metadata import title_sort
            # Strip stop words
            title_words = title_sort(title).split()
            translated = []

            for (i,word) in enumerate(title_words):
                # Leading numbers optionally translated to text equivalent
                # Capitalize leading sort word
                if i==0:
                    if self.opts.numbers_as_text and re.match('[0-9]+',word[0]):
                        translated.append(EPUB_MOBI.NumberToText(word).text.capitalize())
                    else:
                        if re.match('[0-9]+',word[0]):
                            word =  word.replace(',','')
                            suffix = re.search('[\D]', word)
                            if suffix:
                                word = '%10.0f%s' % (float(word[:suffix.start()]),word[suffix.start():])
                            else:
                                word = '%10.0f' % (float(word))
                        translated.append(word.capitalize())

                else:
                    if re.search('[0-9]+',word[0]):
                        word =  word.replace(',','')
                        suffix = re.search('[\D]', word)
                        if suffix:
                            word = '%10.0f%s' % (float(word[:suffix.start()]),word[suffix.start():])
                        else:
                            word = '%10.0f' % (float(word))
                    translated.append(word)
            return ' '.join(translated)

        def generateThumbnail(self, title, image_dir, thumb_file):
            import calibre.utils.PythonMagickWand as pw
            try:
                img = pw.NewMagickWand()
                if img < 0:
                    raise RuntimeError('generateThumbnail(): Cannot create wand')
                # Read the cover
                if not pw.MagickReadImage(img,
                        title['cover'].encode(filesystem_encoding)):
                    self.opts.log.error('generateThumbnail(): Failed to read cover image from: %s' % title['cover'])
                    raise IOError
                thumb = pw.CloneMagickWand(img)
                if thumb < 0:
                    self.opts.log.error('generateThumbnail(): Cannot clone cover')
                    raise RuntimeError
                # img, width, height
                pw.MagickThumbnailImage(thumb, self.thumbWidth, self.thumbHeight)
                pw.MagickWriteImage(thumb, os.path.join(image_dir, thumb_file))
                pw.DestroyMagickWand(thumb)
                pw.DestroyMagickWand(img)
            except IOError:
                self.opts.log.error("generateThumbnail(): IOError with %s" % title['title'])
            except RuntimeError:
                self.opts.log.error("generateThumbnail(): RuntimeError with %s" % title['title'])

        def getMarkerTags(self):
            ''' Return a list of special marker tags to be excluded from genre list '''
            markerTags = []
            markerTags.extend(self.opts.exclude_tags.split(','))
            markerTags.extend(self.opts.note_tag.split(','))
            markerTags.extend(self.opts.read_tag.split(','))
            return markerTags

        def letter_or_symbol(self,char):
            if not re.search('[a-zA-Z]',char):
                return 'Symbols'
            else:
                return char

        def getFriendlyGenreTag(self, genre):
            # Find the first instance of friendly_tag matching genre
            for friendly_tag in self.genre_tags_dict:
                if self.genre_tags_dict[friendly_tag] == genre:
                    return friendly_tag

        def markdownComments(self, comments):
            '''
            Convert random comment text to normalized, xml-legal block of <p>s
            'plain text' returns as
            <p>plain text</p>

            'plain text with <i>minimal</i> <b>markup</b>' returns as
            <p>plain text with <i>minimal</i> <b>markup</b></p>

            '<p>pre-formatted text</p> returns untouched

            'A line of text\n\nFollowed by a line of text' returns as
            <p>A line of text</p>
            <p>Followed by a line of text</p>

            'A line of text.\nA second line of text.\rA third line of text' returns as
            <p>A line of text.<br />A second line of text.<br />A third line of text.</p>

            '...end of a paragraph.Somehow the break was lost...' returns as
            <p>...end of a paragraph.</p>
            <p>Somehow the break was lost...</p>

            Deprecated HTML returns as HTML via BeautifulSoup()

            '''
            # Hackish - ignoring sentences ending or beginning in numbers to avoid
            # confusion with decimal points.

            # Explode lost CRs to \n\n
            for lost_cr in re.finditer('([a-z])([\.\?!])([A-Z])',comments):
                comments = comments.replace(lost_cr.group(),
                                            '%s%s\n\n%s' % (lost_cr.group(1),
                                                            lost_cr.group(2),
                                                            lost_cr.group(3)))
            # Extract pre-built elements - annotations, etc.
            if not isinstance(comments, unicode):
                comments = comments.decode('utf-8', 'replace')
            soup = BeautifulSoup(comments)
            elems = soup.findAll('div')
            for elem in elems:
                elem.extract()

            # Reconstruct comments w/o <div>s
            comments = soup.renderContents()
            if not isinstance(comments, unicode):
                comments = comments.decode('utf-8', 'replace')

            # Convert \n\n to <p>s
            if re.search('\n\n', comments):
                soup = BeautifulSoup()
                split_ps = comments.split(u'\n\n')
                tsc = 0
                for p in split_ps:
                    pTag = Tag(soup,'p')
                    pTag.insert(0,p)
                    soup.insert(tsc,pTag)
                    tsc += 1
                comments = soup.renderContents()

            # Convert solo returns to <br />
            comments = re.sub('[\r\n]','<br />', comments)

            # Convert two hypens to emdash
            comments = re.sub('--','&mdash;',comments)
            soup = BeautifulSoup(comments)
            result = BeautifulSoup()
            rtc = 0
            open_pTag = False

            all_tokens = list(soup.contents)
            for token in all_tokens:
                if type(token) is NavigableString:
                    if not open_pTag:
                        pTag = Tag(result,'p')
                        open_pTag = True
                        ptc = 0
                    pTag.insert(ptc,prepare_string_for_xml(token))
                    ptc += 1

                elif token.name in ['br','b','i','em']:
                    if not open_pTag:
                        pTag = Tag(result,'p')
                        open_pTag = True
                        ptc = 0
                    pTag.insert(ptc, token)
                    ptc += 1

                else:
                    if open_pTag:
                        result.insert(rtc, pTag)
                        rtc += 1
                        open_pTag = False
                        ptc = 0
                    # Clean up NavigableStrings for xml
                    sub_tokens = list(token.contents)
                    for sub_token in sub_tokens:
                        if type(sub_token) is NavigableString:
                            sub_token.replaceWith(prepare_string_for_xml(sub_token))
                    result.insert(rtc, token)
                    rtc += 1

            if open_pTag:
                result.insert(rtc, pTag)

            paras = result.findAll('p')
            for p in paras:
                p['class'] = 'description'

            # Add back <div> elems initially removed
            for elem in elems:
                result.insert(rtc,elem)
                rtc += 1

            return result.renderContents(encoding=None)

        def processSpecialTags(self, tags, this_title, opts):
            tag_list = []
            for tag in tags:
                tag = self.convertHTMLEntities(tag)
                if tag.startswith(opts.note_tag):
                    this_title['notes'] = tag[len(self.opts.note_tag):]
                elif tag == opts.read_tag:
                    this_title['read'] = True
                elif re.search(opts.exclude_genre, tag):
                    continue
                else:
                    tag_list.append(tag)
            return tag_list

        def updateProgressFullStep(self, description):
            self.currentStep += 1
            self.progressString = description
            self.progressInt = float((self.currentStep-1)/self.totalSteps)
            self.reporter(self.progressInt, self.progressString)
            if self.opts.cli_environment:
                self.opts.log(u"%3.0f%% %s" % (self.progressInt*100, self.progressString))

        def updateProgressMicroStep(self, description, micro_step_pct):
            step_range = 100/self.totalSteps
            self.progressString = description
            coarse_progress = float((self.currentStep-1)/self.totalSteps)
            fine_progress = float((micro_step_pct*step_range)/100)
            self.progressInt = coarse_progress + fine_progress
            self.reporter(self.progressInt, self.progressString)

        class NotImplementedError:
            def __init__(self, error):
                self.error = error

            def logerror(self):
                self.opts.log.info('%s not implemented' % self.error)

    def run(self, path_to_output, opts, db, notification=DummyReporter()):
        opts.log = log
        opts.fmt = self.fmt = path_to_output.rpartition('.')[2]

        # Add local options
        opts.creator = "calibre"
        opts.connected_kindle = False

        # Finalize output_profile
        op = opts.output_profile
        if op is None:
            op = 'default'
        if opts.connected_device['name'] and 'kindle' in opts.connected_device['name'].lower():
            opts.connected_kindle = True
            if opts.connected_device['serial'] and opts.connected_device['serial'][:4] in ['B004','B005']:
                op = "kindle_dx"
            else:
                op = "kindle"
        opts.descriptionClip = 380 if op.endswith('dx') or 'kindle' not in op else 100
        opts.authorClip = 100 if op.endswith('dx') or 'kindle' not in op else 60
        opts.output_profile = op

        opts.basename = "Catalog"
        opts.cli_environment = not hasattr(opts,'sync')
        opts.sort_descriptions_by_author = True

        build_log = []

        build_log.append(u"%s(): Generating %s %sin %s environment" %
            (self.name,self.fmt,'for %s ' % opts.output_profile if opts.output_profile else '',
             'CLI' if opts.cli_environment else 'GUI'))

        # If exclude_genre is blank, assume user wants all genre tags included
        if opts.exclude_genre.strip() == '':
            opts.exclude_genre = '\[^.\]'
            build_log.append(" converting empty exclude_genre to '\[^.\]'")

        if opts.connected_device['name']:
            if opts.connected_device['serial']:
                build_log.append(u" connected_device: '%s' #%s%s " % \
                    (opts.connected_device['name'],
                     opts.connected_device['serial'][0:4],
                     'x' * (len(opts.connected_device['serial']) - 4)))
                for storage in opts.connected_device['storage']:
                    if storage:
                        build_log.append(u"  mount point: %s" % storage)
            else:
                build_log.append(u" connected_device: '%s'" % opts.connected_device['name'])
                for storage in opts.connected_device['storage']:
                    if storage:
                        build_log.append(u"  mount point: %s" % storage)

        opts_dict = vars(opts)
        if opts_dict['ids']:
            build_log.append(" book count: %d" % len(opts_dict['ids']))

        sections_list = ['Descriptions','Authors']
        if opts.generate_titles:
            sections_list.append('Titles')
        if opts.generate_recently_added:
            sections_list.append('Recently Added')
        if not opts.exclude_genre.strip() == '.':
            sections_list.append('Genres')
        build_log.append(u" Sections: %s" % ', '.join(sections_list))

        # Display opts
        keys = opts_dict.keys()
        keys.sort()
        build_log.append(" opts:")
        for key in keys:
            if key in ['catalog_title','authorClip','connected_kindle','descriptionClip',
                       'exclude_genre','exclude_tags','note_tag','numbers_as_text','read_tag',
                       'search_text','sort_by','sort_descriptions_by_author','sync']:
                build_log.append("  %s: %s" % (key, opts_dict[key]))

        if opts.verbose:
            log('\n'.join(line for line in build_log))

        self.opts = opts

        # Launch the Catalog builder
        catalog = self.CatalogBuilder(db, opts, self, report_progress=notification)
        if opts.verbose:
            log.info(" Begin catalog source generation")
        catalog.createDirectoryStructure()
        catalog.copyResources()
        catalog.calculateThumbnailSize()
        catalog_source_built = catalog.buildSources()
        if opts.verbose:
            if catalog_source_built:
                log.info(" Completed catalog source generation\n")
            else:
                log.warn(" No database hits with supplied criteria")

        if catalog_source_built:
            recommendations = []
            recommendations.append(('comments', '\n'.join(line for line in build_log),
                    OptionRecommendation.HIGH))

            dp = getattr(opts, 'debug_pipeline', None)
            if dp is not None:
                recommendations.append(('debug_pipeline', dp,
                    OptionRecommendation.HIGH))

            if opts.fmt == 'mobi' and opts.output_profile and opts.output_profile.startswith("kindle"):
                recommendations.append(('output_profile', opts.output_profile,
                    OptionRecommendation.HIGH))
                recommendations.append(('no_inline_toc', True,
                    OptionRecommendation.HIGH))
                recommendations.append(('book_producer',opts.output_profile,
                    OptionRecommendation.HIGH))

            # Run ebook-convert
            from calibre.ebooks.conversion.plumber import Plumber
            plumber = Plumber(os.path.join(catalog.catalogPath,
                            opts.basename + '.opf'), path_to_output, log, report_progress=notification,
                            abort_after_input_dump=False)
            plumber.merge_ui_recommendations(recommendations)
            plumber.run()
            return 0
        else:
            return 1
