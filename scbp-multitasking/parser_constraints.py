import sys

def parse(constraint, id_list: list, prop_list: list, tcc: bool ):
    """
        Parse the given constraint.
    """
    
    print(f"- Parsing constraint: '{constraint}'")

    # Clean the line and consider only non-empty strings
    tokens = list(filter(None,  constraint.strip().split(" ")))
    length = len(tokens)
    # Minimum 3 words, maximum 4 
    if length < 2 or length > 4:
        sys.exit(f"Incorrect format. The format is task_id [NOT] PROPERTY task_id")

    # The second word must be the negation keyword
    if length == 4 and tokens[1].upper() != "NOT" and tokens[1] != "!":
        sys.exit("Four words detected, the second one must by the keyword NOT")

    task_1 = tokens[0]
    task_2 = tokens[-1]
    prop = tokens[-2]
    negation = False
    if tcc and prop == '=' or prop == 'equal':
        # Convert special equal symbol
        prop = 'EQUAL'
    elif tcc and prop == '!=':
        # Convert NOT EQUAL (!=) symbol
        prop = 'EQUAL'
        negation = True
    elif not tcc and prop == 'lessThan':
        prop = '<'
    elif not tcc and prop == 'lessThanOrEqualTo':
        prop = '<='
    elif prop[0] == '!':
        # Convert negation of the property when ! is as prefix of the property
        prop = prop[1:]
        negation = True

    # If there are four words, it must be a negation
    if length == 4  :
        negation = True

    if task_1 not in id_list:
        sys.exit(f"Unknown '{task_1}' task id")

    if tcc and task_2 not in id_list:
        sys.exit(f"Unknown '{task_2}' task id")

    if prop.upper() != 'EQUAL' and prop not in prop_list:
        sys.exit(f"Unknown '{prop}' property")

    return (task_1, task_2, prop, negation)
