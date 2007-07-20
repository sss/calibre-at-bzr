##    Copyright (C) 2007 Kovid Goyal kovid@kovidgoyal.net
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
import textwrap

from PyQt4.QtGui import QStatusBar, QMovie, QLabel, QFrame, QHBoxLayout, QPixmap
from PyQt4.QtCore import Qt, QSize

class BookInfoDisplay(QFrame):
    class BookCoverDisplay(QLabel):
        WIDTH = 80
        HEIGHT = 100
        def __init__(self, coverpath=':/images/book.svg'):
            QLabel.__init__(self)
            self.default_pixmap = QPixmap(coverpath).scaled(self.__class__.WIDTH,
                                                            self.__class__.HEIGHT,
                                                            Qt.IgnoreAspectRatio,
                                                            Qt.SmoothTransformation)
            self.setPixmap(self.default_pixmap)
            self.setMaximumSize(QSize(self.WIDTH, self.HEIGHT))
            self.setScaledContents(True)
        
        def sizeHint(self):
            return QSize(self.__class__.WIDTH, self.__class__.HEIGHT)
        
    
    class BookDataDisplay(QLabel):
        def __init__(self):
            QLabel.__init__(self)
            self.setTextInteractionFlags(Qt.TextSelectableByMouse)
            self.setText('')#<table><tr><td>row 1</td><td>row 2</td></tr><tr><td>fsfdsfsfsfsfsfsdfsffsfsd</td></tr></table>')
    
    def __init__(self, clear_message):
        QFrame.__init__(self)
        self.clear_message = clear_message
        self.layout = QHBoxLayout()
        self.setLayout(self.layout)
        self.cover_display = BookInfoDisplay.BookCoverDisplay()
        self.layout.addWidget(self.cover_display)        
        self.book_data = BookInfoDisplay.BookDataDisplay()
        self.layout.addWidget(self.book_data)
        self.setVisible(False)
        
    def show_data(self, data):
        if data.has_key('cover'):
            cover_data = data.pop('cover')
            pixmap = QPixmap()
            pixmap.loadFromData(cover_data)
            if pixmap.isNull():
                self.cover_display.setPixmap(self.cover_display.default_pixmap)
            else:
                self.cover_display.setPixmap(pixmap)
        else:
            self.cover_display.setPixmap(self.cover_display.default_pixmap)
            
        rows = u''
        self.book_data.setText('')
        for key in data.keys():
            txt = '<br />\n'.join(textwrap.wrap(data[key], 120))
            rows += '<tr><td><b>%s:</b></td><td>%s</td></tr>'%(key, txt)
        self.book_data.setText('<table>'+rows+'</table>')
        
        self.clear_message()
        self.setVisible(True)

class MovieButton(QLabel):
    def __init__(self, movie):
        QLabel.__init__(self)
        self.movie = movie
        self.setMovie(movie)
        self.movie.start()
        self.movie.setPaused(True)

class StatusBar(QStatusBar):
    def __init__(self):
        QStatusBar.__init__(self)
        self.movie_button = MovieButton(QMovie(':/images/jobs-animated.mng'))
        self.addPermanentWidget(self.movie_button)
        self.book_info = BookInfoDisplay(self.clearMessage)
        self.addWidget(self.book_info)
        
    def job_added(self, id):
        if self.movie_button.movie.state() == QMovie.Paused:
            self.movie_button.movie.setPaused(False)
            
    def no_more_jobs(self):
        if self.movie_button.movie.state() == QMovie.Running:
            self.movie_button.movie.setPaused(True)
            self.movie_button.movie.jumpToFrame(0) # This causes MNG error 11, but seems to work regardless
            
        
if __name__ == '__main__':
    # Used to create the animated status icon
    from PyQt4.Qt import QApplication, QPainter, QSvgRenderer, QPixmap, QColor
    from subprocess import check_call
    import os
    app = QApplication([])

    def create_pixmaps(path, size=16, delta=20):
        r = QSvgRenderer(path)
        if not r.isValid():
            raise Exception(path + ' not valid svg')
        pixmaps = []
        for angle in range(0, 360+delta, delta):
            pm = QPixmap(size, size)
            pm.fill(QColor(0,0,0,0))
            p = QPainter(pm)
            p.translate(size/2., size/2.)
            p.rotate(angle)
            p.translate(-size/2., -size/2.)
            r.render(p)
            p.end()
            pixmaps.append(pm)
        return pixmaps

    def create_mng(path='/home/kovid/work/libprs500/src/libprs500/gui2/images/jobs.svg', size=64, angle=5, delay=5):
        pixmaps = create_pixmaps(path, size, angle)
        filesl = []
        for i in range(len(pixmaps)):
            name = 'a%s.png'%(i,)
            filesl.append(name)
            pixmaps[i].save(name, 'PNG')
            filesc = ' '.join(filesl)
        cmd = 'convert -dispose Background -delay '+str(delay)+ ' ' + filesc + ' -loop 0 animated.mng'
        try:
            check_call(cmd, shell=True)
        finally:
            for file in filesl:
                os.remove(file)
        
