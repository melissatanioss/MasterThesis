from collections import defaultdict, Counter
import verify_cif
import writer_cif
import convert

import os
import shutil


def check_file_exists(file_path):
    if not os.path.isfile(file_path):
        print(f"File not found: {file_path}")
        return False
    return True


class ComponentVerifier:
    def __init__(self):
        # Initialize call stack and any other attributes your class needs
        self.latest_call_token = None
        self.call_stack = set()  # This tracks active function calls to prevent recursion

    def generate_new_token(self):
        import uuid
        return str(uuid.uuid4())

    def write_tooldef(self, connected_components):
        for index, (component, req_filenames) in connected_components.items():
            writer_cif.write_tooldef(index, req_filenames)

    def print_connected_components(self, connected_components):
        print("merged_connected_components:")
        for key, value in connected_components.items():
            print(f"{key}: {value}")

    def merge_components(self, indices, connected_components, only_check):
        combined_component = set()
        combined_values = []
        tobe_deleted = []
        ind_list = sorted(list(indices))
        for index in ind_list:
            combined_component.update(connected_components[index][0])
            combined_values.extend(connected_components[index][1])
            if index not in tobe_deleted:
                tobe_deleted.append(index)
        if only_check:
            merge_key = "-".join(str(index) for index in indices)
            connected_components[merge_key] = (tuple(combined_component), combined_values)
            del connected_components[str(ind_list[0])]
        else:
            connected_components[ind_list[0]] = (tuple(combined_component), combined_values)
        for index in sorted(ind_list[1:], reverse=True):
            if str(index) in connected_components:
                del connected_components[str(index)]
        return connected_components

    def find_and_transform_common_components(self, indexed_connected_components, full_path):
        components_list = list(indexed_connected_components.keys())
        common_counts = defaultdict(lambda: defaultdict(int))
        if common_counts:
            print("Empty common comp: ",common_counts)
            return dict
        absolute_path_components = []

        if full_path:
            for index in components_list:
                component, _ = indexed_connected_components[index]
                absolute_path_component = set(os.path.basename(path) for path in component)
                absolute_path_components.append((index, absolute_path_component))
        else:
            for index in components_list:
                component, _ = indexed_connected_components[index]
                absolute_path_components.append((index, set(component)))

        for i, (index_i, component) in enumerate(absolute_path_components):
            for j in range(i + 1, len(absolute_path_components)):
                index_j, other_component = absolute_path_components[j]
                common_elements = component.intersection(other_component)
                count = len(common_elements)
                if count > 2:
                    sorted_indices = tuple(sorted((index_i, index_j)))
                    common_counts[sorted_indices] = count
        print("common_counts: ", dict(common_counts))
        return dict(sorted(dict(common_counts).items(), key=lambda item: item[1], reverse=True))


    def parallel_composition_check(self, indexed_connected_components, directory_path):
        plants_path, events_path, verification_path = self.get_paths(directory_path)
        merge_key = "-".join(str(index) for index in indexed_connected_components.keys())
        errors = []
        trim_check, error_res = verify_cif.run_verification_steps_synthesis(merge_key, verification_path,
                                                                            events_path, errors)
        return error_res

    def get_paths(self, directory_path):
        verification_path = os.path.join(directory_path, convert.MODEL_VERIFICATION)
        plants_path = os.path.join(directory_path, writer_cif.PLANT_DIR)
        events_path = os.path.join(plants_path, writer_cif.EVENTS_FILE)
        return plants_path, events_path, verification_path

    def clear_directory(self, verification_path, count):
        writer_cif.delete_plant_dir(count)
        if os.path.exists(verification_path):
            shutil.rmtree(verification_path)
        if not os.path.exists(verification_path):
            os.mkdir(verification_path)  # Create the directory

    def modular_decomposition(self, connected_components, cif_content, process_block, task_map, constraints,
                              requirements):
            # Step 1: Initial Component Setup
            if not connected_components:
                connected_components = writer_cif.write_initial_composition(
                    process_block, task_map, constraints, cif_content, requirements
                )

            # Step 2: Directory Path Setup
            directory_path = os.path.join(os.getcwd(), process_block.id)
            plants_path, events_path, verification_path = self.get_paths(directory_path)

            # Step 3: Directory Preparation
            self.clear_directory(verification_path, len(connected_components))
            self.print_connected_components(connected_components)

            errors = []
            # Step 4: Compute a supervisor for each component
            for index, (component, req_filenames) in connected_components.items():
                writer_cif.write_structure(index, cif_content, component)
                full_req_paths = writer_cif.getReqPath(req_filenames)
                plants_paths = writer_cif.getFullPath(index, connected_components)
                combined_paths = list(plants_paths) + list(full_req_paths.values())
                synthesis_check, trim_check, error_res = verify_cif.run_verification_steps(index, verification_path,
                                                                                           combined_paths)

                # If any supervisor is empty, no control is possible. Stop here.
                if not synthesis_check:
                    print(f"Supervisor at index {index} is empty. Return")
                    print("connected_components: ", connected_components)
                    return connected_components, error_res

            # Step 5: Compute the parallel composition of all the supervisors found
            errors = self.parallel_composition_check(connected_components, directory_path)

            if errors:  # If errors are found, it means the composition is not trim. Handle and merge components.
                # Find most common components
                common_components = self.find_and_transform_common_components(connected_components, False)
                print("common_components:", common_components)
                if not common_components or len(connected_components) < 2:
                    print("no more possible merges")
                    return connected_components, errors

                if common_components:
                    errors = []
                    for (c1, c2), val in common_components.items():
                        new_dict = {c1: connected_components[c1], c2: connected_components[c2]}
                        print("connected_com: ", connected_components, "\nc1: ", c1, " c2: " , c2)
                        errors = self.parallel_composition_check(new_dict, directory_path)
                        if errors:
                            connected_components = self.merge_components((c1, c2), connected_components, False)
                            errors = []
                            return self.modular_decomposition(connected_components, cif_content, process_block,
                                                              task_map, constraints, requirements)

                    if not errors:
                        checked_indices = []
                        for (c1, c2), val in common_components.items():
                            if c1 not in checked_indices and c2 not in checked_indices:
                                checked_indices.append(c1)
                                checked_indices.append(c2)
                                connected_components = self.merge_components((c1, c2), connected_components, False)
                        return self.modular_decomposition(connected_components, cif_content, process_block, task_map,
                                                          constraints, requirements)
                    else:
                        return connected_components, errors
            else:
                # Trim check passed for parallel composition. The composition is correct, no further actions needed.
                return connected_components, errors  # Return final components and errors


    """
    
       if not trim_check:  # If verification fails, handle errors and merge components
                errors.extend(error_res)
                print(f"Trim check failed for component {index}.")
                connected_components, indices = self.handle_errors_and_merge(connected_components, index)
                if indices:
                    errors.extend([item for sublist in indices for item in sublist])
                    return self.modular_decomposition(connected_components, cif_content, process_block, task_map,
                                                      constraints, requirements)
    
        def final_check(self, connected_components, cif_content, process_block, task_map, constraints, requirements):
        # Step 1: Directory Path Setup
        directory_path = os.path.join(os.getcwd(), process_block.id)
        # Step 2: Parallel Composition Check
        errors = self.parallel_composition_check(connected_components, directory_path)

        if errors:  # If errors are found, handle and merge components
            connected_components, indices = self.handle_errors_and_merge(connected_components)
            if indices:
                return self.modular_decomposition(connected_components, cif_content, process_block, task_map,
                                                  constraints, requirements)
        return connected_components, errors
    
    def iterative_step(self, connected_components, cif_content, process_block, task_map, constraints,requirements):
        self.latest_call_token = self.generate_new_token()
        current_token = self.latest_call_token
        error_handling = []
        directory_path = os.path.join(os.getcwd(), process_block.id)
        plants_path, events_path, verification_path = self.get_paths(directory_path)
        verification_errors = []

        print("iterative step:")
        plants_path, events_path, verification_path = self.get_paths(directory_path)
        while len(connected_components) > 1:
            common_components = self.find_and_transform_common_components(connected_components, False)
            if common_components:
                graph_common_components = writer_cif.create_comp_graph(list(common_components.keys()))
                print("graph_common_components:", graph_common_components)
            else:
                print("len(common_components)", len(common_components))
                break

            for indices in graph_common_components:
                merge_key = "-".join(str(index) for index in indices)
                trim_check, verification_errors = verify_cif.run_verification_steps_synthesis(merge_key,
                                                                                              verification_path,
                                                                                              events_path, [])
                if not trim_check:
                    print(f"Trim check failed for components {merge_key}.")
                    connected_components = self.merge_components(indices, connected_components, False)
                    return self.modular_decomposition(connected_components, cif_content, process_block, task_map,
                                                      constraints, requirements)

                else:
                    connected_components = self.merge_components(indices, connected_components, True)

        error_handling.extend([err for err in verification_errors])
        return connected_components, error_handling
    """
