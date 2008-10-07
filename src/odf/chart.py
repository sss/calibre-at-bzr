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

from namespaces import CHARTNS
from element import Element

# Autogenerated
def Axis(**args):
    return Element(qname = (CHARTNS,'axis'), **args)

def Categories(**args):
    return Element(qname = (CHARTNS,'categories'), **args)

def Chart(**args):
    return Element(qname = (CHARTNS,'chart'), **args)

def DataPoint(**args):
    return Element(qname = (CHARTNS,'data-point'), **args)

def Domain(**args):
    return Element(qname = (CHARTNS,'domain'), **args)

def ErrorIndicator(**args):
    return Element(qname = (CHARTNS,'error-indicator'), **args)

def Floor(**args):
    return Element(qname = (CHARTNS,'floor'), **args)

def Footer(**args):
    return Element(qname = (CHARTNS,'footer'), **args)

def Grid(**args):
    return Element(qname = (CHARTNS,'grid'), **args)

def Legend(**args):
    return Element(qname = (CHARTNS,'legend'), **args)

def MeanValue(**args):
    return Element(qname = (CHARTNS,'mean-value'), **args)

def PlotArea(**args):
    return Element(qname = (CHARTNS,'plot-area'), **args)

def RegressionCurve(**args):
    return Element(qname = (CHARTNS,'regression-curve'), **args)

def Series(**args):
    return Element(qname = (CHARTNS,'series'), **args)

def StockGainMarker(**args):
    return Element(qname = (CHARTNS,'stock-gain-marker'), **args)

def StockLossMarker(**args):
    return Element(qname = (CHARTNS,'stock-loss-marker'), **args)

def StockRangeLine(**args):
    return Element(qname = (CHARTNS,'stock-range-line'), **args)

def Subtitle(**args):
    return Element(qname = (CHARTNS,'subtitle'), **args)

def SymbolImage(**args):
    return Element(qname = (CHARTNS,'symbol-image'), **args)

def Title(**args):
    return Element(qname = (CHARTNS,'title'), **args)

def Wall(**args):
    return Element(qname = (CHARTNS,'wall'), **args)

