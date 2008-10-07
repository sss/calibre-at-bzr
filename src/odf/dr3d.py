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

from namespaces import DR3DNS
from element import Element
from draw import StyleRefElement

# Autogenerated
def Cube(**args):
    return StyleRefElement(qname = (DR3DNS,'cube'), **args)

def Extrude(**args):
    return StyleRefElement(qname = (DR3DNS,'extrude'), **args)

def Light(Element):
    return StyleRefElement(qname = (DR3DNS,'light'), **args)

def Rotate(**args):
    return StyleRefElement(qname = (DR3DNS,'rotate'), **args)

def Scene(**args):
    return StyleRefElement(qname = (DR3DNS,'scene'), **args)

def Sphere(**args):
    return StyleRefElement(qname = (DR3DNS,'sphere'), **args)

