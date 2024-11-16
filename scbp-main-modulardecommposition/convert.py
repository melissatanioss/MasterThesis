import argparse
import sys
import networkx as nx
import parser_structure
import writer_cif
import os
import modular_composition

DEFAULT_PATH_STRUCTURE = 'workspace/scbp-main-edited/hospitaladmission.xml'
DEFAULT_PATH_PLANT = 'plant.cif'
DEFAULT_TOOLDEF = 'tmp.tooldef'
MODEL_VERIFICATION = "ModelVerification"

def parse_args():
    parser = argparse.ArgumentParser(description='Convert an XML document into CIF.')
    parser.add_argument(
        '--input',
        type = str,
        default = DEFAULT_PATH_STRUCTURE,
        help = "Path to the file containing the XML structure"
    )

    parser.add_argument(
        '--sup-synth',
        action="store_true",
        help = "Apply supervisor synthesis"
    )

    parser.add_argument(
        '--tooldef',
        type = str,
        default = 'bin/tooldef.cmd',
        help = "Path to tooldef script"
    )

    return parser.parse_args()


def update_requirements(requirements, count_requirements):
    """
    Update the requirements based on count_requirements.

    Args:
        requirements (dict): A dictionary where keys are sets of requirements and values are tuples.
        count_requirements (list): A list of sets, each set representing a count requirement.

    Returns:
        dict: Updated requirements after merging based on count requirements.
    """
    # Step 1: Reverse the requirements dictionary to use tuples of values as keys and sets of keys as values
    reversed_requirements = {tuple(values): set(key) for key, values in requirements.items()}

    # Step 2: Update the reversed requirements based on count_requirements
    for req in count_requirements:
        req_set = set(req)
        updated_keys = list(reversed_requirements.keys())
        for key in updated_keys:
            value = reversed_requirements[key]
            if value.intersection(req_set):
                reversed_requirements[key] = value.union(req_set)

    # Step 3: Merge values of reversed_requirements
    common_keys = []

    # Convert items to a list to avoid RuntimeError due to dictionary size change during iteration
    items = list(reversed_requirements.items())

    for i, (key, val) in enumerate(items):
        merged = False
        for j, (key2, val2) in enumerate(items[i + 1:], start=i + 1):
            if val.intersection(val2):
                merged = True
                common_keys.append([i, j])
        if not merged:
            common_keys.append([i])
    print("common_keys: ", common_keys)

    # Build the graph to find connected components
    G = nx.Graph()
    for sublist in common_keys:
        for i in range(len(sublist)):
            for j in range(i + 1, len(sublist)):
                G.add_edge(sublist[i], sublist[j])
        if len(sublist) == 1:
            G.add_node(sublist[0])

    # Find connected components
    merged = [list(c) for c in nx.connected_components(G)]
    print("merged: ", merged)

    # Create a list of reversed_requirements keys
    reversed_keys = list(reversed_requirements.keys())

    new_requirements = {}

    for group in merged:
        key = set()
        val = set()
        for idx in group:
            k = reversed_keys[idx]
            key = key.union(k)
            val = val.union(reversed_requirements[k])
        new_requirements[tuple(val)] = key
    print("Updated reversed requirements:", new_requirements)

    return new_requirements

if __name__ == "__main__":
    args = parse_args()

    # Check if the input is a valid file
    if not os.path.isfile(args.input):
        sys.exit(f"{args.input} is not a valid file")

    print(f"- Verifying XML structure at path {args.input}. . .")

    # Parse the structure
    (process, properties, constraints) = parser_structure.parse(args.input)
    print("- XML document looks ok!!\n")

    # Write the CIF file
    process_block, cif_content = writer_cif.form_structure(process)
    task_map, requirements = writer_cif.write_requirements(process_block, properties, constraints)

    # Write events to file
    writer_cif.write_events(process_block)

    # Perform Modular decomposition
    verifier = modular_composition.ComponentVerifier()
    connected_components, errors = verifier.modular_decomposition([], cif_content, process_block, task_map, constraints,requirements)

    verifier.print_connected_components(connected_components)
    #verifier.write_tooldef(connected_components)
    # Check for synthesis errors
    if errors:
        print("Synthesis resulting in livelock/deadlock.")
        for er in errors:
            print(f"Error in synthesis for component: {er}")
    else:
        print(f"No livelock/deadlock. {len(connected_components)} supervisors are synthesized.")


    print("Script finished.")
