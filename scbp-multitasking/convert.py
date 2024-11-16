import argparse
import sys
import parser_structure
import writer_cif
import os

DEFAULT_PATH_STRUCTURE = 'workspace/scbp-main-edited/structure.xml'
DEFAULT_PATH_PLANT = 'plant.cif'
DEFAULT_TOOLDEF = 'tmp.tooldef'

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
        default= 'bin/tooldef.cmd',
        help = "Path to tooldef script"
    )
    
    return parser.parse_args()
    

if __name__ == "__main__":
    args = parse_args()

    # Check if the input is a valid file
    if not os.path.isfile(args.input):
        sys.exit(f"{args.input} is not a valid file")


    print(f"- Verifying XML structure at path {args.input}. . .")

    # Parse the structure
    (process, properties, constraints, counter_constraints) = parser_structure.parse(args.input)
    print("- XML document looks ok!!\n")
    
    # Write the CIF file
    (process_block, base_dir) = writer_cif.write_structure(process)
    writer_cif.write_requirements(process_block, properties, constraints, base_dir)
    writer_cif.write_count_requirements(counter_constraints, base_dir)

    writer_cif.write_supervisor(base_dir)

    # Apply supervisor synthesis in needed
    if args.sup_synth:
        if len(args.tooldef) == 0:
            sys.exit("INPUT ERROR: Specify the path to the tooldef script")

        print("Applying supervisor synthesis . . .")

        # Execute tooldef
        os.system(f"sh {args.tooldef} {os.path.join(base_dir, writer_cif.SUP_DIR, writer_cif.SYNTH_TOOLDEF)}")


    print("Script finished.")
