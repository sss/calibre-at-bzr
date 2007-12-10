all : gui2 translations

clean : 
	cd src/libprs500/gui2 && python make.py clean

gui2 :
	 cd src/libprs500/gui2 && python make.py

test : gui2
	cd src/libprs500/gui2 && python make.py test

translations :
	cd src/libprs500 && python translations/__init__.py
    
