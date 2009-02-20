"""productions for cssutils based on a mix of CSS 2.1 and CSS 3 Syntax
productions

- http://www.w3.org/TR/css3-syntax
- http://www.w3.org/TR/css3-syntax/#grammar0

open issues
    - numbers contain "-" if present
    - HASH: #aaa is, #000 is not anymore,
            CSS2.1: 'nmchar': r'[_a-z0-9-]|{nonascii}|{escape}',
            CSS3: 'nmchar': r'[_a-z-]|{nonascii}|{escape}',
"""
__all__ = ['CSSProductions', 'MACROS', 'PRODUCTIONS']
__docformat__ = 'restructuredtext'
__version__ = '$Id: cssproductions.py 1537 2008-12-03 14:37:10Z cthedot $'

# a complete list of css3 macros
MACROS = {
    'nonascii': r'[^\0-\177]',
    'unicode': r'\\[0-9a-f]{1,6}(?:{nl}|{s})?',
    # 'escape': r'{unicode}|\\[ -~\200-\4177777]',
    'escape': r'{unicode}|\\[ -~\200-\777]',
    'nmstart': r'[_a-zA-Z]|{nonascii}|{escape}',
    'nmchar': r'[-_a-zA-Z0-9]|{nonascii}|{escape}',
    'string1': r'"([^\n\r\f\\"]|\\{nl}|{escape})*"',
    'string2': r"'([^\n\r\f\\']|\\{nl}|{escape})*'",
    'invalid1': r'\"([^\n\r\f\\"]|\\{nl}|{escape})*',
    'invalid2': r"\'([^\n\r\f\\']|\\{nl}|{escape})*",

    'comment': r'\/\*[^*]*\*+([^/][^*]*\*+)*\/',
    'ident': r'[-]?{nmstart}{nmchar}*',
    'name': r'{nmchar}+',
    'num': r'[0-9]*\.[0-9]+|[0-9]+', #r'[-]?\d+|[-]?\d*\.\d+',   
    'string': r'{string1}|{string2}',
    # from CSS2.1
    'invalid': r'{invalid1}|{invalid2}',
    'url':  r'[\x09\x21\x23-\x26\x28\x2a-\x7E]|{nonascii}|{escape}',

    's': r'\t|\r|\n|\f|\x20',
    'w': r'{s}*',
    'nl': r'\n|\r\n|\r|\f',

    'A': r'A|a|\\0{0,4}(?:41|61)(?:\r\n|[ \t\r\n\f])?',
    'C': r'C|c|\\0{0,4}(?:43|63)(?:\r\n|[ \t\r\n\f])?',
    'D': r'D|d|\\0{0,4}(?:44|64)(?:\r\n|[ \t\r\n\f])?',
    'E': r'E|e|\\0{0,4}(?:45|65)(?:\r\n|[ \t\r\n\f])?',
    'F': r'F|f|\\0{0,4}(?:46|66)(?:\r\n|[ \t\r\n\f])?',
    'G': r'G|g|\\0{0,4}(?:47|67)(?:\r\n|[ \t\r\n\f])?|\\G|\\g',
    'H': r'H|h|\\0{0,4}(?:48|68)(?:\r\n|[ \t\r\n\f])?|\\H|\\h',
    'I': r'I|i|\\0{0,4}(?:49|69)(?:\r\n|[ \t\r\n\f])?|\\I|\\i',
    'K': r'K|k|\\0{0,4}(?:4b|6b)(?:\r\n|[ \t\r\n\f])?|\\K|\\k',
    'L': r'L|l|\\0{0,4}(?:4c|6c)(?:\r\n|[ \t\r\n\f])?|\\L|\\l',
    'M': r'M|m|\\0{0,4}(?:4d|6d)(?:\r\n|[ \t\r\n\f])?|\\M|\\m',
    'N': r'N|n|\\0{0,4}(?:4e|6e)(?:\r\n|[ \t\r\n\f])?|\\N|\\n',
    'O': r'O|o|\\0{0,4}(?:4f|6f)(?:\r\n|[ \t\r\n\f])?|\\O|\\o',
    'P': r'P|p|\\0{0,4}(?:50|70)(?:\r\n|[ \t\r\n\f])?|\\P|\\p',
    'R': r'R|r|\\0{0,4}(?:52|72)(?:\r\n|[ \t\r\n\f])?|\\R|\\r',
    'S': r'S|s|\\0{0,4}(?:53|73)(?:\r\n|[ \t\r\n\f])?|\\S|\\s',
    'T': r'T|t|\\0{0,4}(?:54|74)(?:\r\n|[ \t\r\n\f])?|\\T|\\t',
    'U': r'U|u|\\0{0,4}(?:55|75)(?:\r\n|[ \t\r\n\f])?|\\U|\\u',
    'X': r'X|x|\\0{0,4}(?:58|78)(?:\r\n|[ \t\r\n\f])?|\\X|\\x',
    'Z': r'Z|z|\\0{0,4}(?:5a|7a)(?:\r\n|[ \t\r\n\f])?|\\Z|\\z',
    }

# The following productions are the complete list of tokens
# used by cssutils, a mix of CSS3 and some CSS2.1 productions.
# The productions are **ordered**:
PRODUCTIONS = [
    ('BOM', r'\xFEFF'), # will only be checked at beginning of CSS
    
    ('S', r'{s}+'), # 1st in list of general productions
    ('URI', r'{U}{R}{L}\({w}({string}|{url}*){w}\)'),
    ('FUNCTION', r'{ident}\('),
    ('IDENT', r'{ident}'),
    ('STRING', r'{string}'),
    ('INVALID', r'{invalid}'), # from CSS2.1
    ('HASH', r'\#{name}'),
    ('PERCENTAGE', r'{num}\%'),
    ('DIMENSION', r'{num}{ident}'),
    ('NUMBER', r'{num}'),
    # valid ony at start so not checked everytime
    #('CHARSET_SYM', r'@charset '), # from Errata includes ending space!
    ('ATKEYWORD', r'@{ident}'), # other keywords are done in the tokenizer
    #('UNICODE-RANGE', r'[0-9A-F?]{1,6}(\-[0-9A-F]{1,6})?'), #???
    ('CDO', r'\<\!\-\-'),
    ('CDC', r'\-\-\>'),
    ('INCLUDES', '\~\='),
    ('DASHMATCH', r'\|\='),
    ('PREFIXMATCH', r'\^\='),
    ('SUFFIXMATCH', r'\$\='),
    ('SUBSTRINGMATCH', r'\*\='),
    # checked specially if fullsheet is parsed
    ('COMMENT', r'{comment}'), #r'\/\*[^*]*\*+([^/][^*]*\*+)*\/'),
    ('CHAR', r'[^"\']') # MUST always be last
    ]

class CSSProductions(object):
    """
    most attributes are set later
    """
    EOF = True
    # removed from productions as they simply are ATKEYWORD until 
    # tokenizing
    CHARSET_SYM = 'CHARSET_SYM' 
    FONT_FACE_SYM = 'FONT_FACE_SYM'
    MEDIA_SYM = 'MEDIA_SYM'
    IMPORT_SYM = 'IMPORT_SYM'
    NAMESPACE_SYM = 'NAMESPACE_SYM'
    PAGE_SYM = 'PAGE_SYM'

for i, t in enumerate(PRODUCTIONS):
    setattr(CSSProductions, t[0].replace('-', '_'), t[0])
