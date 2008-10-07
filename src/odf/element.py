#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright (C) 2007-2008 Søren Roug, European Environment Agency
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

# Note: This script has copied a lot of text from xml.dom.minidom.
# Whatever license applies to that file also applies to this file.
#
import xml.dom
from xml.dom.minicompat import *
from namespaces import nsdict
import grammar
from attrconverters import AttrConverters

# The following code is pasted form xml.sax.saxutils
# Tt makes it possible to run the code without the xml sax package installed
# To make it possible to have <rubbish> in your text elements, it is necessary to escape the texts
def _escape(data, entities={}):
    """ Escape &, <, and > in a string of data.

        You can escape other strings of data by passing a dictionary as
        the optional entities parameter.  The keys and values must all be
        strings; each key will be replaced with its corresponding value.
    """
    data = data.replace("&", "&amp;")
    data = data.replace("<", "&lt;")
    data = data.replace(">", "&gt;")
    for chars, entity in entities.items():
        data = data.replace(chars, entity)
    return data

def _quoteattr(data, entities={}):
    """ Escape and quote an attribute value.

        Escape &, <, and > in a string of data, then quote it for use as
        an attribute value.  The \" character will be escaped as well, if
        necessary.

        You can escape other strings of data by passing a dictionary as
        the optional entities parameter.  The keys and values must all be
        strings; each key will be replaced with its corresponding value.
    """
    data = _escape(data, entities)
    if '"' in data:
        if "'" in data:
            data = '"%s"' % data.replace('"', "&quot;")
        else:
            data = "'%s'" % data
    else:
        data = '"%s"' % data
    return data

def _nssplit(qualifiedName):
    """ Split a qualified name into namespace part and local part.  """
    fields = qualifiedName.split(':', 1)
    if len(fields) == 2:
        return fields
    else:
        return (None, fields[0])

def _nsassign(namespace):
    return nsdict.setdefault(namespace,"ns" + str(len(nsdict)))

# Exceptions
class IllegalChild(StandardError):
    """ Complains if you add an element to a parent where it is not allowed """
class IllegalText(StandardError):
    """ Complains if you add text or cdata to an element where it is not allowed """

class Node(xml.dom.Node):
    """ super class for more specific nodes """
    parentNode = None
    nextSibling = None
    previousSibling = None

    def hasChildNodes(self):
        """ Tells whether this element has any children; text nodes,
            subelements, whatever.
        """
        if self.childNodes:
            return True
        else:
            return False

    def _get_childNodes(self):
        return self.childNodes

    def _get_firstChild(self):
        if self.childNodes:
            return self.childNodes[0]

    def _get_lastChild(self):
        if self.childNodes:
            return self.childNodes[-1]

    def insertBefore(self, newChild, refChild):
        if newChild.nodeType not in self._child_node_types:
            raise IllegalChild, "%s cannot be child of %s" % (newChild.tagName, self.tagName)
        if newChild.parentNode is not None:
            newChild.parentNode.removeChild(newChild)
        if refChild is None:
            self.appendChild(newChild)
        else:
            try:
                index = self.childNodes.index(refChild)
            except ValueError:
                raise xml.dom.NotFoundErr()
            self.childNodes.insert(index, newChild)
            newChild.nextSibling = refChild
            refChild.previousSibling = newChild
            if index:
                node = self.childNodes[index-1]
                node.nextSibling = newChild
                newChild.previousSibling = node
            else:
                newChild.previousSibling = None
            newChild.parentNode = self
        return newChild

    def appendChild(self, node):
        if node.nodeType == self.DOCUMENT_FRAGMENT_NODE:
            for c in tuple(node.childNodes):
                self.appendChild(c)
            ### The DOM does not clearly specify what to return in this case
            return node
        if node.nodeType not in self._child_node_types:
            raise IllegalChild, "<%s> is not allowed in %s" % ( node.tagName, self.tagName)
        if node.parentNode is not None:
            node.parentNode.removeChild(node)
        _append_child(self, node)
        node.nextSibling = None
        return node

    def removeChild(self, oldChild):
        #FIXME: update ownerDocument.element_dict or find other solution
        try:
            self.childNodes.remove(oldChild)
        except ValueError:
            raise xml.dom.NotFoundErr()
        if oldChild.nextSibling is not None:
            oldChild.nextSibling.previousSibling = oldChild.previousSibling
        if oldChild.previousSibling is not None:
            oldChild.previousSibling.nextSibling = oldChild.nextSibling
        oldChild.nextSibling = oldChild.previousSibling = None
        if self.ownerDocument:
            self.ownerDocument.clear_caches()
        oldChild.parentNode = None
        return oldChild

defproperty(Node, "firstChild", doc="First child node, or None.")
defproperty(Node, "lastChild",  doc="Last child node, or None.")

def _append_child(self, node):
    # fast path with less checks; usable by DOM builders if careful
    childNodes = self.childNodes
    if childNodes:
        last = childNodes[-1]
        node.__dict__["previousSibling"] = last
        last.__dict__["nextSibling"] = node
    childNodes.append(node)
    node.__dict__["parentNode"] = self

class Childless:
    """Mixin that makes childless-ness easy to implement and avoids
    the complexity of the Node methods that deal with children.
    """

    attributes = None
    childNodes = EmptyNodeList()
    firstChild = None
    lastChild = None

    def _get_firstChild(self):
        return None

    def _get_lastChild(self):
        return None

    def appendChild(self, node):
        raise xml.dom.HierarchyRequestErr(
            self.tagName + " nodes cannot have children")

    def hasChildNodes(self):
        return False

    def insertBefore(self, newChild, refChild):
        raise xml.dom.HierarchyRequestErr(
            self.tagName + " nodes do not have children")

    def removeChild(self, oldChild):
        raise xml.dom.NotFoundErr(
            self.tagName + " nodes do not have children")

    def replaceChild(self, newChild, oldChild):
        raise xml.dom.HierarchyRequestErr(
            self.tagName + " nodes do not have children")

class Text(Childless, Node):
    nodeType = Node.TEXT_NODE
    tagName = "Text"

    def __init__(self, data):
        self.data = data

    def __str__(self):
        return self.data

    def toXml(self,level,f):
        """ Write XML in UTF-8 """
        if self.data:
            f.write(_escape(unicode(self.data).encode('utf-8')))
    
class CDATASection(Childless, Text):
    nodeType = Node.CDATA_SECTION_NODE

    def toXml(self,level,f):
        if self.data:
            f.write('<![CDATA[%s]]>' % self.data)

class Element(Node):
    """ Creates a arbitrary element and is intended to be subclassed not used on its own.
        This element is the base of every element it defines a class which resembles
        a xml-element. The main advantage of this kind of implementation is that you don't
        have to create a toXML method for every different object. Every element
        consists of an attribute, optional subelements, optional text and optional cdata.
    """

    nodeType = Node.ELEMENT_NODE
    namespaces = {}  # Due to shallow copy this is a static variable

    _child_node_types = (Node.ELEMENT_NODE,
                         Node.PROCESSING_INSTRUCTION_NODE,
                         Node.COMMENT_NODE,
                         Node.TEXT_NODE,
                         Node.CDATA_SECTION_NODE,
                         Node.ENTITY_REFERENCE_NODE)
    
    def __init__(self, attributes=None, text=None, cdata=None, qname=None, qattributes=None, check_grammar=True, **args):
        if qname is not None:
            self.qname = qname
        assert(hasattr(self, 'qname'))
        self.ownerDocument = None
        self.childNodes=[]
        self.allowed_children = grammar.allowed_children.get(self.qname)
        namespace = self.qname[0]
        prefix = _nsassign(namespace)
        if not self.namespaces.has_key(namespace):
            self.namespaces[namespace] = prefix
        self.tagName = prefix + ":" + self.qname[1]
        if text is not None:
            self.addText(text)
        if cdata is not None:
            self.addCDATA(cdata)

        allowed_attrs = self.allowed_attributes()
        if allowed_attrs is not None:
            allowed_args = [ a[1].lower().replace('-','') for a in allowed_attrs]
        self.attributes={}
        # Load the attributes from the 'attributes' argument
        if attributes:
            for attr, value in attributes.items():
                self.setAttribute(attr, value)
        # Load the qualified attributes
        if qattributes:
            for attr, value in qattributes.items():
                self.setAttrNS(attr[0], attr[1], value)
        if allowed_attrs is not None:
            # Load the attributes from the 'args' argument
            for arg in args.keys():
                self.setAttribute(arg, args[arg])
        else:
            for arg in args.keys():  # If any attribute is allowed
                self.attributes[arg]=args[arg]
        if not check_grammar:
            return
        # Test that all mandatory attributes have been added.
        required = grammar.required_attributes.get(self.qname)
        if required:
            for r in required:
                if self.getAttrNS(r[0],r[1]) is None:
                    raise AttributeError, "Required attribute missing: %s in <%s>" % (r[1].lower().replace('-',''), self.tagName)

    def allowed_attributes(self):
        return grammar.allowed_attributes.get(self.qname)

    def _setOwnerDoc(self, element):
        element.ownerDocument = self.ownerDocument
        for child in element.childNodes:
            self._setOwnerDoc(child)
        
    def addElement(self, element, check_grammar=True):
        """ adds an element to an Element

            Element.addElement(Element)
        """
        if check_grammar and self.allowed_children is not None:
            if element.qname not in self.allowed_children:
                raise IllegalChild, "<%s> is not allowed in <%s>" % ( element.tagName, self.tagName)
        self.appendChild(element)
        self._setOwnerDoc(element)
        if self.ownerDocument:
            self.ownerDocument.rebuild_caches(element)

    def addText(self, text, check_grammar=True):
        if check_grammar and self.qname not in grammar.allows_text:
            raise IllegalText, "The <%s> element does not allow text" % self.tagName
        else:
            if text != '':
                self.appendChild(Text(text))

    def addCDATA(self, cdata, check_grammar=True):
        if check_grammar and self.qname not in grammar.allows_text:
            raise IllegalText, "The <%s> element does not allow text" % self.tagName
        else:
            self.appendChild(CDATASection(cdata))

    def removeAttribute(self, attr, check_grammar=True):
        """ Removes an attribute by name. """
        allowed_attrs = self.allowed_attributes()
        if allowed_attrs is None:
            if type(attr) == type(()):
                prefix, localname = attr
                self.removeAttrNS(prefix, localname)
            else:
                raise AttributeError, "Unable to add simple attribute - use (namespace, localpart)"
        else:
            # Construct a list of allowed arguments
            allowed_args = [ a[1].lower().replace('-','') for a in allowed_attrs]
            if check_grammar and attr not in allowed_args:
                raise AttributeError, "Attribute %s is not allowed in <%s>" % ( attr, self.tagName)
            i = allowed_args.index(attr)
            self.removeAttrNS(allowed_attrs[i][0], allowed_attrs[i][1])

    def setAttribute(self, attr, value, check_grammar=True):
        """ Add an attribute to the element
            This is sort of a convenience method. All attributes in ODF have
            namespaces. The library knows what attributes are legal and then allows
            the user to provide the attribute as a keyword argument and the
            library will add the correct namespace.
            Must overwrite, If attribute already exists.
        """
        allowed_attrs = self.allowed_attributes()
        if allowed_attrs is None:
            if type(attr) == type(()):
                prefix, localname = attr
                self.setAttrNS(prefix, localname, value)
            else:
                raise AttributeError, "Unable to add simple attribute - use (namespace, localpart)"
        else:
            # Construct a list of allowed arguments
            allowed_args = [ a[1].lower().replace('-','') for a in allowed_attrs]
            if check_grammar and attr not in allowed_args:
                raise AttributeError, "Attribute %s is not allowed in <%s>" % ( attr, self.tagName)
            i = allowed_args.index(attr)
            self.setAttrNS(allowed_attrs[i][0], allowed_attrs[i][1], value)

    def setAttrNS(self, namespace, localpart, value):
        """ Add an attribute to the element
            In case you need to add an attribute the library doesn't know about
            then you must provide the full qualified name
            It will not check that the attribute is legal according to the schema.
            Must overwrite, If attribute already exists.
        """
        allowed_attrs = self.allowed_attributes()
        prefix = _nsassign(namespace)
        if not self.namespaces.has_key(namespace):
            self.namespaces[namespace] = prefix
#       if allowed_attrs and (namespace, localpart) not in allowed_attrs:
#           raise AttributeError, "Attribute %s:%s is not allowed in element <%s>" % ( prefix, localpart, self.tagName)
        c = AttrConverters()
        self.attributes[prefix + ":" + localpart] = c.convert((namespace, localpart), value, self.qname)

    def getAttrNS(self, namespace, localpart):
        prefix = _nsassign(namespace)
        if not self.namespaces.has_key(namespace):
            self.namespaces[namespace] = prefix
        return self.attributes.get(prefix + ":" + localpart)

    def removeAttrNS(self, namespace, localpart):
        prefix = _nsassign(namespace)
        if not self.namespaces.has_key(namespace):
            self.namespaces[namespace] = prefix
        del self.attributes[prefix + ":" + localpart]

    def getAttribute(self, attr):
        allowed_attrs = self.allowed_attributes()
        if allowed_attrs is None:
            if type(attr) == type(()):
                prefix, localname = attr
                return self.getAttrNS(prefix, localname)
            else:
                raise AttributeError, "Unable to get simple attribute - use (namespace, localpart)"
        else:
            # Construct a list of allowed arguments
            allowed_args = [ a[1].lower().replace('-','') for a in allowed_attrs]
            i = allowed_args.index(attr)
            return self.getAttrNS(allowed_attrs[i][0], allowed_attrs[i][1])

    def write_open_tag(self, level, f):
        f.write('<'+self.tagName)
        if level == 0:
            for namespace, prefix in self.namespaces.items():
                f.write(' xmlns:' + prefix + '="'+ _escape(str(namespace))+'"')
        for attkey in self.attributes.keys():
            f.write(' '+_escape(str(attkey))+'='+_quoteattr(unicode(self.attributes[attkey]).encode('utf-8')))
        f.write('>')

    def write_close_tag(self, level, f):
        f.write('</'+self.tagName+'>')

    def toXml(self, level, f):
        """ Generate XML stream out of the tree structure """
        f.write('<'+self.tagName)
        if level == 0:
            for namespace, prefix in self.namespaces.items():
                f.write(' xmlns:' + prefix + '="'+ _escape(str(namespace))+'"')
        for attkey in self.attributes.keys():
            f.write(' '+_escape(str(attkey))+'='+_quoteattr(unicode(self.attributes[attkey]).encode('utf-8')))
        if self.childNodes:
            f.write('>')
            for element in self.childNodes:
                element.toXml(level+1,f)
            f.write('</'+self.tagName+'>')
        else:
            f.write('/>')

    def _getElementsByObj(self, obj, accumulator):
        if self.qname == obj.qname:
            accumulator.append(self)
        for e in self.childNodes:
            if e.nodeType == Node.ELEMENT_NODE:
                accumulator = e._getElementsByObj(obj, accumulator)
        return accumulator

    def getElementsByType(self, element):
        obj = element(check_grammar=False)
        return self._getElementsByObj(obj,[])

