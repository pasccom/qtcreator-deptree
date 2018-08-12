
first:
	@echo "Nothing to build"

install: install-progs install-docs

install-module: deptree.py
	[ -d $(DESTDIR)$(PYTHON_SITELIB) ] || mkdir -p $(DESTDIR)$(PYTHON_SITELIB)
	install -c deptree.py $(DESTDIR)$(PYTHON_SITELIB)/deptree.py

install-deptree: qtcreator-deptree
	[ -d $(DESTDIR)/usr/bin ] || mkdir -p $(DESTDIR)/usr/bin
	install -c qtcreator-deptree $(DESTDIR)/usr/bin/qtcreator-deptree

install-specfile: qtcreator-specfile
	[ -d $(DESTDIR)/usr/bin ] || mkdir -p $(DESTDIR)/usr/bin
	install -c qtcreator-specfile $(DESTDIR)/usr/bin/qtcreator-specfile

install-doc-deptree: qtcreator-deptree.1
	[ -d $(DESTDIR)/usr/share/man/man1 ] || mkdir -p $(DESTDIR)/usr/share/man/man1
	install -c -m 644 qtcreator-deptree.1 $(DESTDIR)/usr/share/man/man1/qtcreator-deptree.1

install-doc-specfile: qtcreator-specfile.1
	[ -d $(DESTDIR)/usr/share/man/man1 ] || mkdir -p $(DESTDIR)/usr/share/man/man1
	install -c -m 644 qtcreator-specfile.1 $(DESTDIR)/usr/share/man/man1/qtcreator-specfile.1

install-progs: install-module install-deptree install-specfile

install-docs: install-doc-deptree install-doc-specfile
