# -*- coding: utf-8 -*-
# Copyright (C) 2006-2007 Søren Roug, European Environment Agency
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301  USA
#
# Contributor(s):
#

from namespaces import XFORMSNS
from element import Element

# ODF 1.0 section 11.2
# XForms is designed to be embedded in another XML format.
# Autogenerated
def Model(**args):
    return Element(qname = (XFORMSNS,'model'), **args)

def Instance(**args):
    return Element(qname = (XFORMSNS,'instance'), **args)

def Bind(**args):
    return Element(qname = (XFORMSNS,'bind'), **args)
