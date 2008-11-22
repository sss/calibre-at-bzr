#!/usr/bin/env  python

__license__   = 'GPL v3'
__copyright__ = '2008, Darko Miletic <darko.miletic at gmail.com>'
'''
politika.rs
'''
import locale
from calibre.web.feeds.news import BasicNewsRecipe

class Politika(BasicNewsRecipe):
    title                 = u'Politika Online'
    __author__            = 'Darko Miletic'
    description           = 'Najstariji dnevni list na Balkanu'    
    oldest_article        = 7
    max_articles_per_feed = 100
    no_stylesheets        = True
    extra_css             = '.content_center_border {text-align: left;}' 
    use_embedded_content  = False
    timefmt               = ' [%A, %d %B, %Y]' 
    #Locale setting to get appropriate date/month values in Serbian if possible
    try:
      #Windows seting for locale
      locale.setlocale(locale.LC_TIME,'Serbian (Latin)')
    except locale.Error:
      #Linux setting for locale -- choose one appropriate for your distribution
      try:
        locale.setlocale(locale.LC_TIME,'sr_YU')
      except locale.Error:
        try:
          locale.setlocale(locale.LC_TIME,'sr_CS@Latn')
        except locale.Error:
          try:
            locale.setlocale(locale.LC_TIME,'sr@Latn')
          except locale.Error:
            try:
              locale.setlocale(locale.LC_TIME,'sr_Latn')
            except locale.Error:
              try:
                locale.setlocale(locale.LC_TIME,'sr_RS')
              except locale.Error:                  
                locale.setlocale(locale.LC_TIME,'C')

    remove_tags_before = dict(name='div', attrs={'class':'content_center_border'})
    remove_tags_after  = dict(name='div', attrs={'class':'datum_item_details'})

    feeds          = [  
                         (u'Politika'             , u'http://www.politika.rs/rubrike/Politika/index.1.lt.xml'             )
                        ,(u'Svet'                 , u'http://www.politika.rs/rubrike/Svet/index.1.lt.xml'                 )
                        ,(u'Redakcijski komentari', u'http://www.politika.rs/rubrike/redakcijski-komentari/index.1.lt.xml')
                        ,(u'Pogledi'              , u'http://www.politika.rs/pogledi/index.lt.xml'                        )
                        ,(u'Pogledi sa strane'    , u'http://www.politika.rs/rubrike/Pogledi-sa-strane/index.1.lt.xml'    )
                        ,(u'Tema dana'            , u'http://www.politika.rs/rubrike/tema-dana/index.1.lt.xml'            )
                        ,(u'Kultura'              , u'http://www.politika.rs/rubrike/Kultura/index.1.lt.xml'              )
                        ,(u'Zivot i stil'         , u'http://www.politika.rs/rubrike/zivot-i-stil/index.1.lt.xml'         )                        
                     ]
