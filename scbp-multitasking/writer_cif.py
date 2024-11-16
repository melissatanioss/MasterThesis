import sys
import os

import parser_structure

PLANT_DIR = 'plant'
REQ_DIR = 'requirements'
SUP_DIR = 'supervisor'

EVENTS_FILE = 'events.cif'
SYNTH_TOOLDEF = 'synthesis.tooldef'
MERGE_OUT = 'merge_res.cif'
SUPERVISOR = 'supervisor.cif'

users_dict = {}
class CifContent:
    """
        Class for collecting all the blocks that will be written in the files
    """
    def __init__(self) -> None:
        self.blocks = {}
        self.output = ""

    def concat(self, content):
        self.output += content

    def lock_block(self, block_id):
        self.blocks[block_id] = self.output
        self.output = ""

class Task:
    def __init__(self, id, ctrl_res, unctrl_res) -> None:
        self.id = id
        self.ctrl_res = ctrl_res
        self.unctrl_res = unctrl_res

    def get_ctrl_events(self) -> list:
        """
            Get the list of controllable events.
            Name convention taken from: 
            https://www.eclipse.org/escet/v0.7/cif/synthesis-based-engineering/in-practice/steps/modeling-events.html
        """
        return [f"c_{self.id}_{res_name}" for res_name in self.ctrl_res]

    def get_ctrl_out_events(self) -> list:
        """
            Get the list of controllable events.
            Name convention taken from:
            https://www.eclipse.org/escet/v0.7/cif/synthesis-based-engineering/in-practice/steps/modeling-events.html
        """
        unique_elements = set(self.ctrl_res + self.unctrl_res)
        return [f"c_{self.id}_{res_name}_out" for res_name in unique_elements]

    def get_unctrl_events(self) -> list:
        """
            Get the list of uncontrollable events.
            Name convention taken from: 
            https://www.eclipse.org/escet/v0.7/cif/synthesis-based-engineering/in-practice/steps/modeling-events.html
        """
        return [f"u_{self.id}_{res_name}" for res_name in self.unctrl_res]

    def get_users(self, users: dict) -> dict:
        # Ensure `users` is initialized for each resource
        for res_name in self.ctrl_res + self.unctrl_res:
            if res_name not in users:
                users[res_name] = set()
        # Add the user ID to the sets corresponding to controlled resources
        for res_name in self.ctrl_res:
            users[res_name].update({f"c_{self.id}_{res_name}", f"c_{self.id}_{res_name}_out"})

        # Add the user ID to the sets corresponding to uncontrolled resources
        for res_name in self.unctrl_res:
            users[res_name].update({f"u_{self.id}_{res_name}", f"c_{self.id}_{res_name}_out"})

        return users

    def get_input_events(self) -> list:
        return self.get_ctrl_events() + self.get_unctrl_events()

    def get_output_events(self) -> list:
        return self.get_ctrl_out_events()

    def get_children(self) -> list:
        return []

    def get_events(self) -> list:
        """
            Get a list of all the events of this block.
            The list will contain the vents of the sub-blocks too, if there are any.
        """
        res = list()
        for event in self.get_ctrl_events():
            res.append((True, event))

        for event in self.get_unctrl_events():
            res.append((False, event))

        for event in self.get_ctrl_out_events():
            res.append((True, event))

        return res

    def self_write(self, output: CifContent):
        """
            Generate the CIF content
        """
        output.concat(format_plant(self.id))
        output.concat(format_location("s0", True, True))
        for event in self.get_input_events():
            output.concat(format_event(event, "s1"))
        output.concat("\n")
        output.concat(format_location("s1"))
        for event in self.get_output_events():
            output.concat(format_event(event, "s0"))
        output.concat(format_end())
        output.lock_block(self.id)

class Sequence:
    def __init__(self, id, children) -> None:
        self.id = id
        self.children = children

    def get_input_events(self) -> list:
        return self.children[0].get_input_events()

    def get_output_events(self) -> list:
        return self.children[-1].get_output_events()


    def get_events(self) -> list:
        res = list()
        for child in self.children:
            res = res + child.get_events()

        return res

    def get_children(self) -> list:
        return self.children

    def self_write(self, output: CifContent):
        output.concat(format_plant(self.id))

        i = 0
        total = len(self.children) * 2
        # For each child we will have two states. 
        while i < total:
            if i % 2 == 0:
                # For even states we have input events
                output.concat(format_location(f"s{i}", i == 0, i == 0))
                for event in self.children[int(i / 2)].get_input_events():
                    output.concat(format_event(event, f"s{i + 1}"))

            else:
                # For odd states we have output events
                next_loc = i+1 if i != total - 1 else 0
                output.concat(format_location(f"s{i}"))
                for event in self.children[int(i/2)].get_output_events():
                    output.concat(format_event(event, f"s{next_loc}"))
            output.concat("\n")
            i += 1
        output.concat(format_end())
        output.lock_block(self.id)

class And:
    def __init__(self, id, children) -> None:
        self.id = id
        self.children = children

    def get_input_events(self) -> list:
        return [f"c_{self.id}_in"]

    def get_output_events(self) -> list:
        return [f"c_{self.id}_out"]

    def get_events(self) -> list:
        res = [(True, event) for event in self.get_input_events() + self.get_output_events()]
        for child in self.children:
            res = res + child.get_events()

        return res

    def get_children(self) -> list:
        return self.children

    def self_write(self, output: CifContent):
        i = 0
        input_event = self.get_input_events()[0]
        output_event = self.get_output_events()[0]
        for child in self.children:
            output.concat(format_plant(f"{self.id}_{i}"))
            
            output.concat(format_location(f"s{i}_0", True, True))
            output.concat(format_event(input_event, f"s{i}_1"))
            output.concat("\n")

            output.concat(format_location(f"s{i}_1"))
            for event in child.get_input_events():
                output.concat(format_event(event, f"s{i}_2"))
            output.concat("\n")

            output.concat(format_location(f"s{i}_2"))
            for event in child.get_output_events():
                output.concat(format_event(event, f"s{i}_3"))
            output.concat("\n")

            output.concat(format_location(f"s{i}_3"))
            output.concat(format_event(output_event, f"s{i}_0"))
            output.concat(format_end())
            output.lock_block(f"{self.id}_{i}")
            i += 1
            

            
class Xor:
    def __init__(self, id, default, ctrl_default, ctrl_branch, unctrl_branch, children) -> None:
        self.id = id
        self.ctrl_branch = ctrl_branch
        self.unctrl_branch = unctrl_branch
        self.default = default
        self.ctrl_default = ctrl_default
        self.children = children

    def get_ctrl_events(self) -> list:
        """
            Get the list of controllable events.
            Name convention taken from: 
            https://www.eclipse.org/escet/v0.7/cif/synthesis-based-engineering/in-practice/steps/modeling-events.html
        """
        return [f"c_{self.id}_{branch_name}" for branch_name in self.ctrl_branch]
        
    def get_unctrl_events(self) -> list: #out events are controllable
        """
            Get the list of uncontrollable events.
            Name convention taken from: 
            https://www.eclipse.org/escet/v0.7/cif/synthesis-based-engineering/in-practice/steps/modeling-events.html
        """
        return [f"c_{self.id}_{branch_name}" for branch_name in self.unctrl_branch]
    
    def get_default_event(self) -> str:
        if self.default != None:
            prefix = 'c' if self.ctrl_default else 'u'
            return f"{prefix}_{self.id}_{self.default}"
        return ''

    def get_input_events(self) -> list:
        result = self.get_ctrl_events() + self.get_unctrl_events()
        # Add default branch if specified
        if self.default != None:
            result.append(self.get_default_event())
        return result

    def get_output_events(self) -> list:
        return [f"c_{self.id}_out"]

    def get_events(self) -> list:
        res = list()
        for event in self.get_ctrl_events():
            res.append((True, event))

        for event in self.get_unctrl_events():
            res.append((False, event))

        if self.default != None:
            res.append((self.ctrl_default, self.get_default_event()))

        res.append((True, self.get_output_events().pop()))

        for child in self.children:
            res = res + child.get_events()

        return res

    def get_children(self) -> list:
        return self.children

    def self_write(self, output: CifContent):
        output.concat(format_plant(f"{self.id}"))
        output.concat(format_location(f"s0", True, True))

        i = 0
        events_list = self.get_input_events()
        n_children = len(self.children)
        while i < len(events_list):
            # The default branch is not associated to a child
            if i == n_children:
                output.concat(format_event(events_list[i], f"s3"))
            else:
                output.concat(format_event(events_list[i], f"s{i}_1"))
            i+=1
        
        # Iterate only the branches 
        i = 0
        for child in self.children:
            output.concat(format_location(f"s{i}_1"))
            for event in child.get_input_events():
                output.concat(format_event(event, f"s{i}_2"))
            output.concat("\n")

            output.concat(format_location(f"s{i}_2"))
            for event in child.get_output_events():
                output.concat(format_event(event, f"s3"))
            output.concat("\n")
            i+=1

        output.concat(format_location(f"s3"))
        output.concat(format_event(self.get_output_events().pop(), f"s0"))
        output.concat(format_end())
        output.lock_block(self.id)

class Loop:
    def __init__(self, id, repeat, repeat_ctrl, exit, exit_ctrl, first_child, second_child = None) -> None:
        self.id = id
        self.repeat = repeat
        self.repeat_ctrl = repeat_ctrl
        self.exit = exit
        self.exit_ctrl = exit_ctrl
        self.first_child = first_child
        self.second_child = second_child

    def get_input_events(self) -> list:
        return [f"c_{self.id}_in"]

    def get_output_events(self) -> list:
        return [self.get_exit_event()]

    def get_repeat_event(self) -> str:
        prefix = 'c' if self.repeat_ctrl else 'u'
        return f"{prefix}_{self.id}_{self.repeat}"

    def get_exit_event(self) -> str:
        prefix = 'c' if self.exit_ctrl else 'u'
        return f"{prefix}_{self.id}_{self.exit}"

    def get_events(self) -> list:
        res = list()
        res.append((True, self.get_input_events().pop()))
        res.append((self.repeat_ctrl, self.get_repeat_event()))
        res.append((self.exit_ctrl, self.get_exit_event()))

        res = res + self.first_child.get_events()
        
        if self.second_child:
            res = res + self.second_child.get_events()

        return res

    def get_children(self) -> list:
        res = list()
        res.append(self.first_child)
        if self.second_child != None:
            res.append(self.second_child)
        return res

    def self_write(self, output: CifContent):
        output.concat(format_plant(f"{self.id}"))

        output.concat(format_location(f"s0", True, True))
        for event in self.get_input_events():
            output.concat(format_event(event, "s1"))
        output.concat("\n")

        output.concat(format_location(f"s1"))
        for event in self.first_child.get_input_events():
            output.concat(format_event(event, "s2"))
        output.concat("\n")

        output.concat(format_location(f"s2"))
        for event in self.first_child.get_output_events():
            output.concat(format_event(event, "s3"))
        output.concat("\n")

        output.concat(format_location(f"s3"))
        output.concat(format_event(self.get_output_events().pop(), "s0"))

        # If there is the second child, we add the states
        if self.second_child:
            output.concat(format_event(self.get_repeat_event(), "s4"))
            output.concat("\n")

            output.concat(format_location(f"s4"))
            for event in self.second_child.get_input_events():
                output.concat(format_event(event, "s5"))
            output.concat("\n")

            output.concat(format_location(f"s5"))
            for event in self.second_child.get_output_events():
                output.concat(format_event(event, "s1"))

        else:
            output.concat(format_event(self.get_repeat_event(), "s1"))
        
        output.concat(format_end())
        output.lock_block(self.id)

class While:
    def __init__(self, id, repeat, repeat_ctrl, exit, exit_ctrl, child) -> None:
        self.id = id
        self.repeat = repeat
        self.repeat_ctrl = repeat_ctrl
        self.exit = exit
        self.exit_ctrl = exit_ctrl
        self.child = child

    def get_input_events(self) -> list:
        return [f"c_{self.id}_in"]

    def get_output_events(self) -> list:
        return [self.get_exit_event()]

    def get_repeat_event(self) -> str:
        prefix = 'c' if self.repeat_ctrl else 'u'
        return f"{prefix}_{self.id}_{self.repeat}"

    def get_exit_event(self) -> str:
        prefix = 'c' if self.exit_ctrl else 'u'
        return f"{prefix}_{self.id}_{self.exit}"

    def get_events(self) -> list:
        res = list()
        res.append((True, self.get_input_events().pop()))
        res.append((self.guard_ctrl, self.get_repeat_event()))
        res.append((self.guard_ctrl, self.get_exit_event()))
        return res + self.child.get_events()

    def get_children(self) -> list:
        return [self.child]

    def self_write(self, output: CifContent):
        output.concat(format_plant(f"{self.id}"))

        output.concat(format_location(f"s0", True, True))
        for event in self.get_input_events():
            output.concat(format_event(event, "s1"))
        
        output.concat("\n")

        output.concat(format_location(f"s1"))
        output.concat(format_event(self.get_repeat_event(), "s2"))
        output.concat(format_event(self.get_output_events().pop(), "s0"))
        output.concat("\n")

        output.concat(format_location(f"s2"))
        for event in self.child.get_input_events():
            output.concat(format_event(event, "s3"))
        output.concat("\n")

        output.concat(format_location(f"s3"))
        for event in self.child.get_output_events():
            output.concat(format_event(event, "s1"))
        output.concat(format_end())
        output.lock_block(self.id)

class Process:
    def __init__(self, id, child) -> None:
        self.id = id
        self.child = child
    
    def get_input_events(self) -> list:
        return [f"c_{self.id}_in"]

    def get_output_events(self) -> list:
        return [f"c_{self.id}_out"]

    def get_events(self) -> list:
        res = [(True, event) for event in self.get_input_events() + self.get_output_events()]
        return res + self.child.get_events()
    
    def get_children(self) -> list:
        return [self.child]

    def self_write(self, output: CifContent):
        output.concat(format_plant(f"{self.id}"))

        output.concat(format_location(f"s0", True))
        output.concat(format_event(self.get_input_events().pop(), "s1"))
        output.concat("\n")

        output.concat(format_location(f"s1"))
        for event in self.child.get_input_events():
            output.concat(format_event(event, "s2"))
        output.concat("\n")

        output.concat(format_location(f"s2"))
        for event in self.child.get_output_events():
            output.concat(format_event(event, "s3"))
        output.concat("\n")

        output.concat(format_location(f"s3"))
        output.concat(format_event(self.get_output_events().pop(), "s4"))
        output.concat("\n")
        output.concat(format_location(f"s4", False, True))
        output.concat(format_end())
        output.lock_block(self.id)


def format_plant(id) -> str:
    """
        Get the string for starting a plant
    """
    return f"plant {id}:\n"

def format_requirement(id) -> str:
    """
        Get the string for starting requirement
    """
    return f"requirement {id}:\n"

def format_end() -> str:
    """
        Get the closing string for the plant
    """
    return "end\n\n"

def format_int(a,b, name) -> str:
    out = get_tab_space()
    out += f"disc int[{a}..{b}] {name} = {a};\n"
    return out

def format_location(loc, initial = False, marked = False) -> str:
    """
        Get the string for specifying a location.
        A location can be initial, marked, both or none. 
    """
    out = get_tab_space()
    out += f"location {loc}:\n"
    if initial: 
        out += get_tab_space(2)
        out += "initial; "
    
    if marked:
        if not initial:
            out += get_tab_space(2)
        out += "marked;"

    if initial or marked:
        out += "\n"
    return out

def format_event(event, goto = None):
    """
        Get the string for the edge. 
        If a goto location is not specified, the edge will refer to itself (cycle)
    """
    out = get_tab_space(2)
    out += f"edge {event}"
    if goto != None:
        out += f" goto {goto}"
    out += ";\n"
    return out

def get_tab_space(n = 1) -> str:
    """
        Get a tab by spaces
    """
    out = ""
    for i in range(n * 4):
        out += " "
    return out

def write_structure(process: parser_structure.ProcessNode):
    """
        Convert the XML tree into a CIF set of plants.
    """

    # Collect the content to be written in the file
    cif_content = CifContent()
    process_block = write_rec(process, cif_content)
    parent = "."
    base_dir = os.path.join(parent, process_block.id)
    plant_dir = os.path.join(base_dir, PLANT_DIR)
    # Create base dir, that is the Id of the process bloc
    if os.path.exists(base_dir):
        os.system(f"rm -rf {base_dir}")
    os.mkdir(base_dir)

    # Create dir for plants
    if os.path.exists(plant_dir):
        os.system(f"rm -rf {plant_dir}")
    os.mkdir(plant_dir)

    writeplant = open(os.path.join(base_dir, f"plant.cif"), "a")
    writeplant.write(f"import \"{EVENTS_FILE}\";\n\n")

    # Write the events
    events = process_block.get_events()
    ctrl_events = filter(lambda tuple: tuple[0], events)
    unctrl_events = filter(lambda tuple: not tuple[0], events)
    # Write the events.cif file
    fp = open(os.path.join(plant_dir, EVENTS_FILE), "w")

    # Just for a bit more order, we write the controllable events before, 
    # then the uncontrollable ones
    for tuple in ctrl_events:
        fp.write(f"controllable {tuple[1]};\n")

    for tuple in unctrl_events:
        fp.write(f"uncontrollable {tuple[1]};\n")


    fp.close()
    # Write a cif file for each block
    for block_id, content in cif_content.blocks.items():
        fp = open(os.path.join(plant_dir, f"{block_id}.cif"), "w")
        fp.write(f"import \"{EVENTS_FILE}\";\n\n")

        writeplant.write(content)
        writeplant.write("\n")

        fp.write(content)
        fp.close()
    writeplant.close()

    return (process_block, base_dir)


def write_rec(node: parser_structure.ProcessNode, output: CifContent):
    # Recursion ends on the Task block, because it cannot have any child
    if node.is_task():
        task = Task(node.id, node.ctrl_res, node.unctrl_res)
        task.self_write(output)
        return task
    
    # Format the sub-blocks
    sub_blocks = list()
    for child in node.children:
        sub_blocks.append(write_rec(child, output))
        
    # Format current block, by cases
    if node.is_sequence():
        block = Sequence(node.id, sub_blocks)
    elif node.is_and():
        block = And(node.id, sub_blocks)
    elif node.is_xor():
        block = Xor(node.id, node.default, node.ctrl_default, node.ctrl_branch, node.unctrl_branch, sub_blocks)
    elif node.is_loop():
        block = Loop(node.id, node.repeat, node.ctrl_repeat, node.exit, node.ctrl_exit, sub_blocks[0], sub_blocks[1] if len(sub_blocks) == 2 else None)
    elif node.is_while():
        block = While(node.id, node.repeat, node.ctrl_repeat, node.exit, node.ctrl_exit, sub_blocks[0])
    elif node.is_process():
        block = Process(node.id, sub_blocks[0])
    else:
        print(node.id)
        sys.exit(f"Unknown node")

    block.self_write(output)
    return block

#################################################################################
#################################################################################
#################################################################################
def write_count_requirements(counter_constraints, base_dir: str):
    req_dir = os.path.join(base_dir, REQ_DIR)
    filtered_users_dict = {
        user: actions
        for user, actions in users_dict.items()
        if user in {constraint[0] for constraint in counter_constraints}
    }
    fp = open(os.path.join(req_dir, f"users.cif"), "a")
    fp.write(f"import \"{os.path.join('..', PLANT_DIR, EVENTS_FILE)}\";\n\n")
    for key in filtered_users_dict:
        fp.write(format_plant(key))
        fp.write(format_int(0,int(len(filtered_users_dict[key])/2),"counter"))
        fp.write(format_location("s0", True, True))

        values_list = list(users_dict[key])
        for val in values_list:
            if "out" not in val:
                fp.write(format_event(val + " do counter := counter + 1", "s0" ))
            else:
                fp.write(format_event( val + " do counter := counter - 1", "s0" ))

        fp.write(format_end())
        fp.write("\n")

    for c in counter_constraints:
        if not c[3]:
            req = "requirement " + c[0] + ".counter " + c[2] + " " + c[1] + ";\n"
        else: req = "requirement " + c[0] + ".counter NOT" + c[2] + " " + c[1] + ";\n"
        fp.write(req)
    print("done writing users requirements")


def write_requirements(process_block: Process, properties, constraints, base_dir: str):
    req_dir = os.path.join(base_dir, REQ_DIR)
    # Create the dir for requirements
    if os.path.exists(req_dir):
        os.system(f"rm -rf {req_dir}")
    os.mkdir(req_dir)
    task_map = {}
    # Build a dictionary where we map the task id with the
    # set of its resources and the events that can make a repeatition
    build_block_auth_rept(process_block, task_map, list(), dict())
    # Build a dict of the names of the requirmenets
    names_dict = compute_req_names(constraints)
    # For each constraint, compute the list of pairs that respects the property
    pairs_dict = compute_good_pairs(properties, constraints, task_map)
    i = 1

    # Loop over each task in the task map
    for task_name, task_info in task_map.items():
        # Loop over each user in the task's users dictionary
        for user_name, user_actions in task_info['users'].items():
            # Check if the user name matches the filter condition
            if user_name not in users_dict:
                users_dict[user_name] = set()
                # Add the user actions to the dictionary under the user's name
            users_dict[user_name].update(set(user_actions))

    for pair, prop_pairs in pairs_dict.items():
        fp = open(os.path.join(req_dir, f"requirement{i}_1.cif"), "w")
        fp.write(f"import \"{os.path.join('..', PLANT_DIR, EVENTS_FILE)}\";\n\n")
        fp.write(
            write_requirement(
                names_dict[pair], task_map[pair[0]]['auth'], task_map[pair[1]]['auth'], task_map[pair[0]]['rept'], prop_pairs, 0 
            )
        )
        fp.close()

        fp = open(os.path.join(req_dir, f"requirement{i}_2.cif"), "w")
        fp.write(f"import \"{os.path.join('..', PLANT_DIR, EVENTS_FILE)}\";\n\n")
        fp.write(
            write_requirement(
                names_dict[(pair[1], pair[0])], task_map[pair[1]]['auth'], task_map[pair[0]]['auth'], task_map[pair[1]]['rept'], prop_pairs, 1 
            )
        )
        fp.close()
        i += 1

def write_requirement(name, t1_auth, t2_auth, t1_rept, prop_pairs, index):
    output = ''
    event_map = {}
    location_pref = f"s_{index}"
    i = 1
    for event in t1_auth:
        event_map[event] = i
        i+= 1

    # There will be n_resources + 1 states
    output += format_requirement(name)
    # Write the first state
    output += format_location(f"{location_pref}_0", True, True)
    # Self loops for all edges in Auth(t2) U Rept(t1)
    for event in t2_auth + t1_rept:
        output += format_event(event)
    # An edge for each resources, that points to another state
    for event in t1_auth:
        output += format_event(event, f"{location_pref}_{event_map[event]}")
    
    output += "\n"

    # Let's write all the other states
    for event in t1_auth:
        output += format_location(f"{location_pref}_{event_map[event]}", False, True)
        
        # For each Rept(t1) we go back to state 0
        for rept in t1_rept:
             output += format_event(rept, f"{location_pref}_0")
        
        # For each resource event we go to the corresponding state
        # for event2 in t1_auth:
            # Self-loop if the event is itself, otherwise point to the state
            # dest = f"{location_pref}_{event_map[event2]}" if event != event2 else None
            # output += format_event(event2, dest)

        # Now we iterate all the events of t2 knowing that t1 has appeared previously
        epsilon = list(map(lambda pair: pair[(index + 1) % 2], filter(lambda pair: pair[index] == event, prop_pairs )))
        for event in epsilon:
            output += format_event(event)

    output += format_end()
    return output

def build_block_auth_rept(
    block: Process | Sequence | And | Xor | Loop | While | Task, 
    result_dict: dict,
    rept: list,
    users: dict
    ) -> dict:
    """
        Foreach task, get the Auth (list of authorized resources) and 
        Rept (events that can force a repetition) sets
    """
    
    if isinstance(block, Task):
        # Recursion base case
        result_dict[block.id] = {
            'resources': block.ctrl_res + block.unctrl_res,
            'auth' : block.get_ctrl_events() + block.get_unctrl_events(),
            'rept' : rept,
            'users': block.get_users(users)
        }
    
    if isinstance(block, Loop | While):
        # Propagate forward the repeatable events
        rept.append(block.get_repeat_event())


    # Iterate recursively through the children
    for child in block.get_children():
        build_block_auth_rept(child, result_dict, rept.copy(), users.copy())


def compute_good_pairs(properties: dict, constraints: list, task_res: dict):
    """
        Compute all the possible pairs that respects the property
    """
    result = {}
    for constr in constraints:
        res1 = map_resourses_names_to_task_events(task_res[constr[0]]['auth'], constr[0])
        res2 = map_resourses_names_to_task_events(task_res[constr[1]]['auth'], constr[1])
        # Compute all possible pairs using resources names
        all_pairs = compute_all_possible_pairs(res1.keys(), res2.keys())
        
        if constr[2] == 'EQUAL':
            pairs = filter_equal_property(all_pairs, constr[3])
        else:
            pairs = filter_custom_property(all_pairs, properties[constr[2]], constr[3])
        
        # Map the pair of tasks to the list of all the events that respects the property. A conversion
        # from the resource name to the event name is done, by using the previous dictionaries
        result[(constr[0], constr[1])] = [(res1[pair[0]], res2[pair[1]]) for pair in pairs]
    return result

def compute_req_names(constraints):
    res = {}
    for c in constraints:
        middle = 'NOT_' if c[3] else ''
        middle += c[2]

        res[(c[0], c[1])] = f"{c[0]}_{middle}_{c[1]}"
        res[(c[1], c[0])] = f"{c[1]}_{middle}_{c[0]}"
    return res

def map_resourses_names_to_task_events(resources_list, task_id):
    """
        The constraints works only on resources name, while
        the task has events, eg. Resource 'Alice', event 'c_Task1_Alice'.
        We map the resource name to the task name
    """
    result = {}
    for r in resources_list:
        extracted = r.split(f"_{task_id}_")[1]
        result[extracted] = r
    return result


def filter_equal_property(pairs, not_equal = False):
    """
        Filter the elements to satisfy (NOT) EQUAL property
    """
    return list(filter(lambda pair: pair[0] != pair[1] if not_equal else pair[0] == pair[1], pairs))

def filter_custom_property(pairs, property_pairs, not_in = False):
    """
        Given a list of pairs, and a pool of pairs, filter only those
        that are (or are not, depending on the not_in parameter) in the pool
    """
    # Map the pairs to allow constant check
    mapped = dict.fromkeys(property_pairs)
    # Filter the element from the list both  
    return list(filter(lambda pair: (pair in mapped) ^ not_in, pairs))

def compute_all_possible_pairs(first_l, second_l):
    """
        Compute all possibile pairs combination, with the 
        first element as the resource of the first task, and the second one
        of the second task
    """
    result = list()
    for res1 in first_l:
        for res2 in second_l:
            result.append((res1, res2))
    return result



def write_supervisor(base_dir):
    """
        Write the supervisor directory and tooldef file
    """
    sup_dir = os.path.join(base_dir, SUP_DIR)
    plant_dir = os.path.join(base_dir, PLANT_DIR)
    req_dir = os.path.join(base_dir, REQ_DIR)
    # Create supervisor dir
    if os.path.exists(sup_dir):
        os.system(f"rm -rf {sup_dir}")
    os.mkdir(sup_dir)

    # Get all the plant files
    plants = filter(lambda file: file != EVENTS_FILE, os.listdir(plant_dir))

    # Get all the requirement files
    requirements = os.listdir(req_dir)

    # Create the tooldef file
    fp = open(os.path.join(sup_dir, SYNTH_TOOLDEF), "w")
    fp.write("from \"lib:cif\" import *;\n\n")

    # Add the cifmerge instruction
    fp.write("cifmerge(\n")
    for plant in plants:
        fullpath = os.path.abspath(os.path.join(plant_dir, plant))
        fp.write(get_tab_space(2) + f"\"{fullpath}\",\n")
    
    for req in requirements:
        fullpath = os.path.abspath(os.path.join(req_dir, req))
        fp.write(get_tab_space(2) + f"\"{fullpath}\",\n")

    fullpath_merge_out = os.path.abspath(os.path.join(sup_dir, MERGE_OUT))
    fp.write(get_tab_space(2) + f"\"-o {fullpath_merge_out}\",\n")
    fp.write(");\n\n")

    # Add the cifsupsynth instruction
    fullpath_sup_out = os.path.abspath(os.path.join(sup_dir, SUPERVISOR))
    fp.write(f"cifdatasynth(\n")
    fp.write(f"{get_tab_space(2)}\"{fullpath_merge_out}\", \n")
    fp.write(f"{get_tab_space(2)}\"-n S\", \n")
    fp.write(f"{get_tab_space(2)}\"-o {fullpath_sup_out}\"\n")
    fp.write(");")

    fp.close()
