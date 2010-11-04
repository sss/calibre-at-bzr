from __future__ import with_statement
__license__ = 'GPL 3'
__copyright__ = '2010, Fabian Grassl <fg@jusmeum.de>'
__docformat__ = 'restructuredtext en'

import os, re, shutil

from calibre.utils import zipfile

from os.path import dirname, abspath, relpath, exists, basename

from lxml import etree
from templite import Templite

from calibre.ebooks.oeb.base import element
from calibre.customize.conversion import OutputFormatPlugin, OptionRecommendation
from calibre import CurrentDir
from calibre.ptempfile import PersistentTemporaryDirectory
from calibre.utils.zipfile import ZipFile

from urllib import unquote

from calibre.ebooks.html.meta import EasyMeta

class HTMLOutput(OutputFormatPlugin):

    name = 'HTML Output'
    author = 'Fabian Grassl'
    file_type = 'zip'

    options = set([
        OptionRecommendation(name='template_css',
            help=_('CSS file used for the output instead of the default file')),

        OptionRecommendation(name='template_html_index',
            help=_('Template used for generation of the html index file instead of the default file')),

        OptionRecommendation(name='template_html',
            help=_('Template used for the generation of the html contents of the book instead of the default file')),

        OptionRecommendation(name='extract_to',
            help=_('Extract the contents of the generated ZIP file to the specified directory')
        ),
    ])

    recommendations = set([('pretty_print', True, OptionRecommendation.HIGH)])

    def generate_toc(self, oeb_book, ref_url, output_dir):
        '''
        Generate table of contents
        '''
        with CurrentDir(output_dir):
            def build_node(current_node, parent=None):
                if parent is None:
                    parent = etree.Element('ul')
                elif len(current_node.nodes):
                    parent = element(parent, ('ul'))
                for node in current_node.nodes:
                    point = element(parent, 'li')
                    href = relpath(abspath(unquote(node.href)), dirname(ref_url))
                    link = element(point, 'a', href=href)
                    title = node.title
                    if title:
                        title = re.sub(r'\s+', ' ', title)
                    link.text=title
                    build_node(node, point)
                return parent
            wrap = etree.Element('div')
            wrap.append(build_node(oeb_book.toc))
            return wrap

    def generate_html_toc(self, oeb_book, ref_url, output_dir):
        root = self.generate_toc(oeb_book, ref_url, output_dir)
        return etree.tostring(root, pretty_print=True, encoding='utf-8',
                xml_declaration=False)

    def convert(self, oeb_book, output_path, input_plugin, opts, log):

        # read template files
        if opts.template_html_index is not None:
            template_html_index_data = open(opts.template_html_index, 'rb').read()
        else:
            template_html_index_data = P('templates/html_export_default_index.tmpl', data=True)

        if opts.template_html is not None:
            template_html_data = open(opts.template_html, 'rb').read()
        else:
            template_html_data = P('templates/html_export_default.tmpl', data=True)

        if opts.template_css is not None:
            template_css_data = open(opts.template_css, 'rb').read()
        else:
            template_css_data = P('templates/html_export_default.css', data=True)

        template_html_index_data = template_html_index_data.decode('utf-8')
        template_html_data = template_html_data.decode('utf-8')
        template_css_data = template_css_data.decode('utf-8')

        self.log  = log
        self.opts = opts
        meta = EasyMeta(oeb_book.metadata)

        tempdir = PersistentTemporaryDirectory()
        output_file = os.path.join(tempdir,
                basename(re.sub(r'\.zip', '', output_path)+'.html'))
        output_dir = re.sub(r'\.html', '', output_file)+'_files'

        if not exists(output_dir):
            os.makedirs(output_dir)

        css_path = output_dir+os.sep+'calibreHtmlOutBasicCss.css'
        with open(css_path, 'wb') as f:
            f.write(template_css_data.encode('utf-8'))

        with open(output_file, 'wb') as f:
            html_toc = self.generate_html_toc(oeb_book, output_file, output_dir)
            templite = Templite(template_html_index_data)
            nextLink = oeb_book.spine[0].href
            nextLink = relpath(output_dir+os.sep+nextLink, dirname(output_file))
            cssLink = relpath(abspath(css_path), dirname(output_file))
            tocUrl = relpath(output_file, dirname(output_file))
            t = templite.render(has_toc=bool(oeb_book.toc.count()),
                    toc=html_toc, meta=meta, nextLink=nextLink,
                    tocUrl=tocUrl, cssLink=cssLink,
                    firstContentPageLink=nextLink)
            f.write(t)

        with CurrentDir(output_dir):
            for item in oeb_book.manifest:
                path = abspath(unquote(item.href))
                dir = dirname(path)
                if not exists(dir):
                    os.makedirs(dir)
                if item.spine_position is not None:
                    with open(path, 'wb') as f:
                        pass
                else:
                    with open(path, 'wb') as f:
                        f.write(str(item))
                    item.unload_data_from_memory(memory=path)

            for item in oeb_book.spine:
                path = abspath(unquote(item.href))
                dir = dirname(path)
                root = item.data.getroottree()

                # get & clean HTML <HEAD>-data
                head = root.xpath('//h:head', namespaces={'h': 'http://www.w3.org/1999/xhtml'})[0]
                head_content = etree.tostring(head, pretty_print=True, encoding='utf-8')
                head_content = re.sub(r'\<\/?head.*\>', '', head_content)
                head_content = re.sub(re.compile(r'\<style.*\/style\>', re.M|re.S), '', head_content)

                # get & clean HTML <BODY>-data
                body = root.xpath('//h:body', namespaces={'h': 'http://www.w3.org/1999/xhtml'})[0]
                ebook_content = etree.tostring(body, pretty_print=True, encoding='utf-8')
                ebook_content = re.sub(r'\<\/?body.*\>', '', ebook_content)
                ebook_content = re.sub(r'<(div|a|span)([^>]*)/>', r'<\1\2></\1>', ebook_content)

                # generate link to next page
                if item.spine_position+1 < len(oeb_book.spine):
                    nextLink = oeb_book.spine[item.spine_position+1].href
                    nextLink = relpath(abspath(nextLink), dir)
                else:
                    nextLink = None

                # generate link to previous page
                if item.spine_position > 0:
                    prevLink = oeb_book.spine[item.spine_position-1].href
                    prevLink = relpath(abspath(prevLink), dir)
                else:
                    prevLink = None

                cssLink = relpath(abspath(css_path), dir)
                tocUrl = relpath(output_file, dir)
                firstContentPageLink = oeb_book.spine[0].href

                # render template
                templite = Templite(template_html_data)
                toc = lambda: self.generate_html_toc(oeb_book, path, output_dir)
                t = templite.render(ebookContent=ebook_content,
                        prevLink=prevLink, nextLink=nextLink,
                        has_toc=bool(oeb_book.toc.count()), toc=toc,
                        tocUrl=tocUrl, head_content=head_content,
                        meta=meta, cssLink=cssLink,
                        firstContentPageLink=firstContentPageLink)

                # write html to file
                with open(path, 'wb') as f:
                    f.write(t)
                item.unload_data_from_memory(memory=path)

        zfile = ZipFile(output_path, "w")
        zfile.add_dir(output_dir, basename(output_dir))
        zfile.write(output_file, basename(output_file), zipfile.ZIP_DEFLATED)

        if opts.extract_to:
            if not os.path.exists(opts.extract_to):
              os.makedirs(opts.extract_to)
            zfile.extractall(opts.extract_to)
            self.log('Zip file extracted to', opts.extract_to)

        zfile.close()

        # cleanup temp dir
        shutil.rmtree(tempdir)
