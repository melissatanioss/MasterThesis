import sys
import ply.lex as lex
import ply.yacc as yacc

tokens = ( 'NAME', 'LPAR', 'RPAR', 'COMMA')

t_NAME = r'[a-zA-Z_][a-zA-Z0-9_]*'
t_LPAR = r'\('
t_RPAR = r'\)'
t_COMMA = r','

t_ignore  = ' \t \n \r\n'


def t_error(t):
    print(f'Illegal character {t.value[0]!r}')
    t.lexer.skip(1)


def p_property(p):
    '''
    property : list optproperty 
    '''
    p[0] = p[1]

def p_optproperty(p):
    '''
    optproperty : empty
                | property
    '''
    p[0] = p[1]


def p_list(p):
    '''
    list : tuple opttuple
    '''
    res = list()
    res.append(p[1])
    if p[2] != None:
        res = res + p[2]
    p[0] = res

def p_opttuple(p):
    '''
    opttuple : COMMA tuple opttuple
             | empty
    '''
    res = list()
    if len(p) == 4:
        res.append(p[2])
        res = res + p[3]
    p[0] = res

def p_tuple(p):
    '''
    tuple : LPAR NAME COMMA NAME optresname RPAR
    '''
    res = list()
    res.append(p[2])
    res.append(p[4])
    if p[5] != None:
        res = res + p[5]
    p[0] = res

def p_optresname(p):
    '''
    optresname : COMMA NAME optresname
               | empty
    '''
    res = list()
    if len(p) == 4:
        res.append(p[2])
        res = res + p[3]
    p[0] = res

def p_empty(p):
    'empty : '
    pass

def p_error(p):
    print(p)
    if p:
        print(f'Syntax error at {p.value!r}')

def parse(property):
    lex.lex()
    parser = yacc.yacc() 
    # Parse the properties
    pretty_prop = parser.parse(property)
    if pretty_prop == None:
        pretty_prop = []

    return expand_symmetric(pretty_prop)

def expand_symmetric(pair_list):
    """
        Given a list of pairs and/or tuples (as lists), for the pair add the 
        respective symmetric pair, for the tuple compute all the possibile combinations
        of 2 elements and their symmetric pairs. 
    """
    new_list = list()
    for tup in pair_list:
        if len(tup) == 2:
            new_list.append((tup[0], tup[1]))
            # Add the symmetric pair if not already in the list
            if not simmetric_pair_exists(tup, pair_list):
                new_list.append((tup[1], tup[0]))
        
        elif len(tup) > 2:
            # Expand the tuple into a list of pairs
            tuple_list = split_into_pair_list(tup)
            new_list = new_list + tuple_list

    return new_list

def simmetric_pair_exists(pair, pair_list):
    """
        Check if the symmetric pair of the given one is in the given list
    """
    found = False
    i = 0
    while not found and i < len(pair_list):
        item = pair_list[i]
        found =  pair[0] == item[1] and pair[1] ==  item[0]
        i += 1
    return found

def split_into_pair_list(item_list):
    """
        Given a list of elements, compute all the pairs of two non-identical elements 
    """
    res = list()
    for i in range(len(item_list)):
        for j in range(i, len(item_list)):
            if item_list[i] != item_list[j]:
                res.append((item_list[i], item_list[j]))
                res.append((item_list[j], item_list[i]))
    return res
