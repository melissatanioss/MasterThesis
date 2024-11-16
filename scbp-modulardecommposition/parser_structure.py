import sys
import xml.etree.ElementTree as ET
import re

import parser_properties
import parser_constraints

BLOCK_ID_REGEXP = "^[a-zA-Z0-9_]+$"
PROP_ID_REGEXP = "^[a-zA-Z0-9_]+$"
RESOURCE_REGEXP = "^[a-zA-Z0-9_]+$"
GUARD_REGEXP = "^[a-zA-Z0-9_]+$"
BRANCH_REGEXP = "^[a-zA-Z0-9_]+$"


class Tags:
    INSTANCE = 'instance'
    PROCESS = 'process'
    TASK = 'task'
    SEQUENCE = 'sequence'
    AND = 'and'
    XOR = 'xor'
    LOOP = 'loop'
    WHILE = 'while'
    CONSTR = 'constraints'
    PROPERTY = 'property'
    TCC = 'tcc'


class Attributes:
    ID = 'id'

    CONTROLLABLE_RES = 'ctrl_res'
    UNCONTROLLABLE_RES = 'unctrl_res'

    CONTROLLABLE_BRANCH = 'ctrl_branch'
    UNCONTROLLABLE_BRANCH = 'unctrl_branch'
    DEFAULT = 'default'
    CONTROLLABLE_DEFAULT = 'ctrl_default'

    REPEAT = 'repeat'
    CONTROLLABLE_REPEAT = 'ctrl_repeat'
    EXIT = 'exit'
    CONTROLLABLE_EXIT = 'ctrl_exit'


AVAILABLE_PROC_TAGS = [
    Tags.TASK, Tags.SEQUENCE, Tags.AND, Tags.XOR, Tags.LOOP, Tags.WHILE
]

AVAILABLE_CONSTR_TAG = [
    Tags.PROPERTY, Tags.TCC
]


class ProcessNode:
    def __init__(self, xml_element: ET.Element) -> None:
        self.tag = xml_element.tag
        attribs = xml_element.attrib
        self.id = attribs.get(Attributes.ID)

        self.ctrl_res = parse_resources(attribs.get(Attributes.CONTROLLABLE_RES, ""))
        self.unctrl_res = parse_resources(attribs.get(Attributes.UNCONTROLLABLE_RES, ""))

        self.ctrl_branch = parse_branches(attribs.get(Attributes.CONTROLLABLE_BRANCH, ""))
        self.unctrl_branch = parse_branches(attribs.get(Attributes.UNCONTROLLABLE_BRANCH, ""))
        self.default = parse_default_branch(attribs.get(Attributes.DEFAULT)) if attribs.get(
            Attributes.DEFAULT) != None else None
        self.ctrl_default = parse_boolean(attribs.get(Attributes.CONTROLLABLE_DEFAULT, 'false'))

        self.repeat = parse_guard(attribs.get(Attributes.REPEAT)) if attribs.get(Attributes.REPEAT) != None else None
        self.ctrl_repeat = parse_boolean(attribs.get(Attributes.CONTROLLABLE_REPEAT, 'false'))
        self.exit = parse_guard(attribs.get(Attributes.EXIT)) if attribs.get(Attributes.EXIT) != None else None
        self.ctrl_exit = parse_boolean(attribs.get(Attributes.CONTROLLABLE_EXIT, 'false'))

        self.children = list()

    def is_task(self) -> bool:
        return self.tag == Tags.TASK

    def is_sequence(self) -> bool:
        return self.tag == Tags.SEQUENCE

    def is_and(self) -> bool:
        return self.tag == Tags.AND

    def is_xor(self) -> bool:
        return self.tag == Tags.XOR

    def is_loop(self) -> bool:
        return self.tag == Tags.LOOP

    def is_while(self) -> bool:
        return self.tag == Tags.WHILE

    def is_process(self) -> bool:
        return self.tag == Tags.PROCESS

    def add_child(self, child):
        self.children.append(child)


def parse(path):
    """
        Parse the structure.xml document
    """

    xml = parse_xml(path)

    root = xml.getroot()
    if root.tag != Tags.INSTANCE:
        sys.exit(f"SYNTAX ERROR: Root element must be a '{Tags.INSTANCE}' tag")

    if get_children_count(root) != 2:
        sys.exit(f"SYNTAX ERROR: '{Tags.INSTANCE}' must have exactly two children")

    # Check syntax
    id_list = check_process(root[0])

    # Build the tree
    process = ProcessNode(root[0])
    build_tree(process, root[0])

    # Check constraints syntax
    (properties, constraints) = check_constraints(root[1], id_list)

    return (process, properties, constraints)


def parse_xml(path: str) -> ET.ElementTree:
    """
        Parse an XML document at a given path
    """
    # print("- Parsing XML specified at:", path)
    tree = ET.parse(path)
    return tree


def check_process(process: ET.Element):
    """
        Check if the process block is correctly defined
    """
    # Check tag
    if process.tag != Tags.PROCESS:
        sys.exit(f"SYNTAX ERROR: Invalid tag '{process.tag}'. '{Tags.PROCESS}' tag is required")

    # process tag must have only one child
    if get_children_count(process) != 1:
        sys.exit(f"SYNTAX ERROR: '{Tags.PROCESS}' element must have exactly one child")

    id = get_id(process)
    id_list = {
        id: process.tag
    }
    check_block(process[0], id_list)
    return id_list


def check_common(element: ET.Element, id_list: dict):
    """
        Check the properties that are in common for all block, that are:
        - check if the tag is valid
        - check if has an id attribute
        - check if the id hasn't been already defined
    """
    if element.tag not in AVAILABLE_PROC_TAGS:
        sys.exit(f"SYNTAX ERROR: '{element.tag}' is not a valid tag")

    id = get_id(element)

    if id_list.get(id) != None:
        sys.exit(f"SYNTAX ERROR: '{id}' id is already assigned to a '{id_list.get(id)}' block")

    id_list[id] = element.tag


def get_children_count(element: ET.Element):
    """
        Count the children of an element
    """
    i = 0
    for _ in element:
        i += 1
    return i


def check_block(element: ET.Element, id_list: dict):
    """
        Check if the given block is correctly defined
    """
    # Check the common properties
    check_common(element, id_list)
    # Check the individual properties
    tag_name = element.tag
    if tag_name == Tags.TASK:
        check_task(element)
    elif tag_name == Tags.SEQUENCE:
        check_sequence(element, id_list)
    elif tag_name == Tags.AND:
        check_and(element, id_list)
    elif tag_name == Tags.XOR:
        check_xor(element, id_list)
    elif tag_name == Tags.LOOP:
        check_loop(element, id_list)
    elif tag_name == Tags.WHILE:
        check_while(element, id_list)


def check_task(task_elem: ET.Element):
    """
        Check correctness of a task element
    """
    if get_children_count(task_elem) > 0:
        sys.exit(f"SYNTAX ERROR: '{Tags.TASK}' elements must be empty blocks")

    attribs = task_elem.attrib
    # Check amount of resources
    controllable = parse_resources(attribs.get(Attributes.CONTROLLABLE_RES, ""))
    uncontrollable = parse_resources(attribs.get(Attributes.UNCONTROLLABLE_RES, ""))
    if len(controllable) == 0 and len(uncontrollable) == 0:
        sys.exit(f"SYNTAX ERROR: '{Tags.TASK}' must have at least a controllable or an uncontrollable resource")

    intersect = list(set(controllable) & set(uncontrollable))
    if len(intersect):
        # print("The following resources cannot be controllable and uncontrollable:")
        for r in intersect:
            print(f"- {r}")
        sys.exit()

    tmp_dict = {}
    for r in controllable + uncontrollable:
        if tmp_dict.get(r) != None:
            sys.exit(f"Duplicate resource '{r}' for task '{get_id(task_elem)}'")
        tmp_dict[r] = 0


def parse_resources(res_string):
    # Split by ';' character and remove empty spaces
    resources = list(filter(None, [res.strip() for res in res_string.split(",")]))
    for r in resources:
        match = re.search(RESOURCE_REGEXP, r)
        if match == None:
            sys.exit(
                f"SYNTAX ERROR: '{r}' element is not well formed. It may contain only lowercase/uppercase letters and numbers, separated by an underscore")

    return resources


def parse_branches(res_string):
    # Split by ';' character and remove empty spaces
    resources = list(filter(None, [res.strip() for res in res_string.split(",")]))
    for r in resources:
        match = re.search(BRANCH_REGEXP, r)
        if match == None:
            sys.exit(
                f"SYNTAX ERROR: '{r}' element is not well formed. It may contain only lowercase/uppercase letters and numbers, separated by an underscore")

    return resources


def check_sequence(seq_elem: ET.Element, id_list: dict):
    """
        Check correctness of a sequence element
    """
    if get_children_count(seq_elem) == 0:
        sys.exit(f"SYNTAX ERROR: '{Tags.SEQUENCE}' element must have at least one child")

    # Check recursively all the children
    for child in seq_elem:
        check_block(child, id_list)


def check_and(and_elem: ET.Element, id_list):
    """
        Check correctness of an and element
    """
    if get_children_count(and_elem) == 0:
        sys.exit(f"SYNTAX ERROR: '{Tags.AND}' element must have at least one child")

    # Check recursively all the children
    for child in and_elem:
        check_block(child, id_list)


def check_xor(xor_elem: ET.Element, id_list):
    """
        Check correctness of a XOR element
    """
    if get_children_count(xor_elem) == 0:
        sys.exit(f"SYNTAX ERROR: '{Tags.XOR}' element must have at least one child")

    default = xor_elem.get(Attributes.DEFAULT)

    # Defaul attribute is not required, but if specified, we check the correctness
    # and if the ctrl_default attribute is present.
    if default != None:
        parse_default_branch(default)

        if xor_elem.get(Attributes.CONTROLLABLE_DEFAULT) == None:
            sys.exit(
                f"SYNTAX ERROR: '{Attributes.CONTROLLABLE_DEFAULT}' is required since '{Attributes.DEFAULT}' has been specified")

        parse_boolean(xor_elem.get(Attributes.CONTROLLABLE_DEFAULT))

    ctrl_branches = parse_branches(xor_elem.get(Attributes.CONTROLLABLE_BRANCH, ""))
    unctrl_branches = parse_branches(xor_elem.get(Attributes.UNCONTROLLABLE_BRANCH, ""))

    if len(ctrl_branches) == 0 and len(unctrl_branches) == 0:
        sys.exit(f"SYNTAX ERROR: '{Tags.XOR}' must have at least a controllable or an uncontrollable branch")

    # Each branch must be associated to a child
    if get_children_count(xor_elem) != (len(ctrl_branches) + len(unctrl_branches)):
        sys.exit(f"SYNTAX ERROR: The number of '{Tags.XOR}' children and the number of defined branches must coincide")

    # A branch cannot be both controllable and uncontrollable
    intersect = list(set(ctrl_branches) & set(unctrl_branches))
    if len(intersect) > 0:
        # print("The following branches cannot be controllable and uncontrollable:")
        # for r in intersect:
        #    print(f"- {r}")
        sys.exit()

    # Check recursively all the children
    for child in xor_elem:
        check_block(child, id_list)


def parse_boolean(string):
    if string == "true":
        return True
    elif string == "false":
        return False
    else:
        sys.exit(f"SYNTAX ERROR: '{string}' is not valid boolean value.")


def parse_default_branch(default_branch: str):
    match = re.search(BRANCH_REGEXP, default_branch)
    if match == None:
        sys.exit(
            f"SYNTAX ERROR: '{default_branch}' is not well formed. It may contain only lowercase/uppercase letters and numbers, separated by an underscore")

    return default_branch


def check_loop(loop_elem: ET.Element, id_list):
    """
        Check correctness of a loop element
    """
    n = get_children_count(loop_elem)
    if n == 0 or n > 2:
        sys.exit(f"SYNTAX ERROR: '{Tags.LOOP}' element must have at least one child and at most two")

    if loop_elem.attrib.get(Attributes.REPEAT) == None:
        sys.exit(f"SYNTAX ERROR: '{Tags.LOOP}' element must have a '{Attributes.REPEAT}' attribute")

    # Just for checking if the value matches the regula expression
    parse_guard(loop_elem.attrib.get(Attributes.REPEAT))

    if loop_elem.attrib.get(Attributes.CONTROLLABLE_REPEAT) == None:
        sys.exit(f"SYNTAX ERROR: '{Tags.LOOP}' element must have a '{Attributes.CONTROLLABLE_REPEAT}' attribute")

    # Just for checking if the value matches the regula expression
    parse_boolean(loop_elem.attrib.get(Attributes.CONTROLLABLE_REPEAT))

    if loop_elem.attrib.get(Attributes.EXIT) == None:
        sys.exit(f"SYNTAX ERROR: '{Tags.LOOP}' element must have a '{Attributes.EXIT}' attribute")

    parse_guard(loop_elem.attrib.get(Attributes.EXIT))

    if loop_elem.attrib.get(Attributes.CONTROLLABLE_EXIT) == None:
        sys.exit(f"SYNTAX ERROR: '{Tags.LOOP}' element must have a '{Attributes.CONTROLLABLE_EXIT}' attribute")

    parse_boolean(loop_elem.attrib.get(Attributes.CONTROLLABLE_EXIT))

    check_block(loop_elem[0], id_list)
    if n == 2:
        check_block(loop_elem[1], id_list)


def check_while(while_elem: ET.Element, id_list):
    """
        Check correctness of a while element
    """
    if get_children_count(while_elem) != 1:
        sys.exit(f"SYNTAX ERROR: '{Tags.WHILE}' element must exactly one child")

    if while_elem.attrib.get(Attributes.REPEAT) == None:
        sys.exit(f"SYNTAX ERROR: '{Tags.WHILE}' element must have a '{Attributes.REPEAT}' attribute")

    parse_guard(while_elem.attrib.get(Attributes.REPEAT))

    if while_elem.attrib.get(Attributes.CONTROLLABLE_REPEAT) == None:
        sys.exit(f"SYNTAX ERROR: '{Tags.WHILE}' element must have a '{Attributes.CONTROLLABLE_REPEAT}' attribute")

    parse_boolean(while_elem.attrib.get(Attributes.CONTROLLABLE_REPEAT))

    if while_elem.attrib.get(Attributes.EXIT) == None:
        sys.exit(f"SYNTAX ERROR: '{Tags.WHILE}' element must have a '{Attributes.EXIT}' attribute")

    parse_guard(while_elem.attrib.get(Attributes.EXIT))

    if while_elem.attrib.get(Attributes.CONTROLLABLE_EXIT) == None:
        sys.exit(f"SYNTAX ERROR: '{Tags.WHILE}' element must have a '{Attributes.CONTROLLABLE_EXIT}' attribute")

    parse_guard(while_elem.attrib.get(Attributes.EXIT))

    check_block(while_elem[0], id_list)


def get_id(element: ET.Element):
    attributes = element.attrib
    id = attributes.get(Attributes.ID)
    if id == None:
        sys.exit(
            f"SYNTAX ERROR: '{Attributes.ID}' attribute not present for tag '{element.tag}'. '{Attributes.ID}' attribute is required")

    match = re.search(BLOCK_ID_REGEXP, id)
    if match == None:
        sys.exit(
            f"SYNTAX ERROR: '{id}' id is not well formed. It may contain only lowercase/uppercase letters and numbers, separated by an underscore")

    return id


def parse_guard(guard: str):
    match = re.search(GUARD_REGEXP, guard)
    if match == None:
        sys.exit(
            f"SYNTAX ERROR: '{guard}'  is not well formed. It may contain only lowercase/uppercase letters and numbers, separated by an underscore")

    return guard


def check_constraints(constr: ET.Element, task_ids: dict):
    """
        Check if the constraints block is correctly defined
    """
    # Check tag
    if constr.tag != Tags.CONSTR:
        sys.exit(f"SYNTAX ERROR: Invalid tag '{constr.tag}'. '{Tags.CONSTR}' tag is required")

    # Map between property name and pairs
    properties = {}
    constraints = []
    task_ids_list = list(task_ids.keys())
    for element in constr:

        if element.tag == Tags.PROPERTY:
            id = get_id(element)
            if id.lower() == 'equal':
                sys.exit("SYNTAX ERROR: EQUAL is a built-in property and cannot be used")

            print("- Parsing property:", id)
            if properties.get(id) != None:
                sys.exit(f"SYNTAX ERROR: Property {id} already defined.")

            # if element.text == None:
            #     sys.exit(f"SYNTAX ERROR: Empty property detected")

            pair_list = parser_properties.parse(element.text if element.text != None else "")
            properties[id] = pair_list
        elif element.tag == Tags.TCC:
            tcc = parser_constraints.parse(element.text, task_ids_list, list(properties.keys()))
            constraints.append(tcc)
        else:
            sys.exit(f"SYNTAX ERROR: Invalid tag '{element.tag}'.")

    return (properties, constraints)


def build_tree(node: ProcessNode, xml_element: ET.Element):
    for child in xml_element:
        child_node = ProcessNode(child)
        node.add_child(child_node)
        build_tree(child_node, child)
