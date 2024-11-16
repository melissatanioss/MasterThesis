import subprocess
import os


def read_file(file_path):
    with open(file_path, 'r') as file:
        return file.read()


def write_file(file_path, content, mode='w'):
    with open(file_path, mode) as file:
        file.write(content)


def run_subprocess(command, errors, success_message):
    try:
        subprocess.run(command, stderr=subprocess.PIPE, check=True)
        print(success_message)
        return True, errors
    except subprocess.CalledProcessError as e:
        print(f"Error running {command[0]}: {e.stderr.decode()}")
        errors.append(e.stderr.decode())
        return False, errors


def process_synthesis_file(synth_file, index, supervisor_header):
    lines = read_file(synth_file).splitlines()
    read_line = False
    supervisor_lines = []
    for line in lines:
        if line.startswith("supervisor automaton") and f"supervisor automaton S{index}:" not in supervisor_header:
            read_line = True
            line = f"supervisor automaton S{index}:"
            supervisor_header.append(line)
        if read_line:
            supervisor_lines.append(line)
    return supervisor_lines


def run_verification_steps_synthesis(indices, verification_path, events_path, trim_check_error):
    print("Index: ", indices)
    synthall = os.path.abspath(os.path.join(verification_path, f"synthesis{indices}.cif"))
    parallel_comp = os.path.abspath(os.path.join(verification_path, f"productsynch{indices}.cif"))
    trim_check_out = os.path.join(verification_path, f"trimcheck{indices}.txt")
    trim_check = False
    event_content = read_file(events_path)
    write_file(synthall, event_content + "\n")

    supervisor_header = []

    splitindex = [s for s in indices.strip().split("-") if s]
    for ind in splitindex:
        synth_out = os.path.abspath(os.path.join(verification_path, f"synthesis{ind}.cif"))
        if os.path.exists(synth_out):
            synth_content = process_synthesis_file(synth_out, ind, supervisor_header)
            write_file(synthall, '\n'.join(synth_content) + '\n', mode='a')
        else:
            trim_check_error.append(f"No File Found {synth_out}")

    cifparallelcomp, trim_check_error = run_cifparallelcomposition(indices, synthall, parallel_comp, trim_check_error)
    if cifparallelcomp:
        trim_check, trim_check_error = run_ciftrimcheck(indices, trim_check_out, parallel_comp, trim_check_error)

    #if trim_check_error:
    #    print("Errors in run_verification_steps_synthesis: ", trim_check_error)

    return trim_check, trim_check_error


def run_verification_steps(index, verification_path, plants_req):
    merge_out_path = os.path.abspath(os.path.join(verification_path, f"merge{index}.cif"))
    synth_out = os.path.abspath(os.path.join(verification_path, f"synthesis{index}.cif"))
    parallel_comp_out = os.path.join(verification_path, f"productsynch{index}.cif")
    trim_check_out = os.path.join(verification_path, f"trimcheck{index}.txt")
    errors = []
    trim_check = False
    cifsynthi = False
    if run_cifmerge(index, plants_req, merge_out_path, errors):
        cifsynthi, errors = run_cifsupsynth(index, synth_out, merge_out_path, errors)
        if cifsynthi:
            cifparallelcomp, errors = run_cifparallelcomposition(index, synth_out, parallel_comp_out, errors)
            if cifparallelcomp:
                trim_check, errors = run_ciftrimcheck(index, trim_check_out, parallel_comp_out, errors)

    return cifsynthi, trim_check, errors


def run_cifmerge(index, fullpath_plants_req, fullpath_merge_out, errors):
    command = [
        r'C:\Users\User\eclipse-escet-v2.0-win32.win32.x86_64\eclipse-escet-v2.0\bin\cifmerge.cmd',
        *fullpath_plants_req,
        '--output-mode=error',
        '-o', fullpath_merge_out
    ]
    return run_subprocess(command, errors, f"cifmerge{index} done successfully")


def run_cifparallelcomposition(index, fullpath_merg_out, fullpath_file_out, errors):
    command = [
        r'C:\Users\User\eclipse-escet-v2.0-win32.win32.x86_64\eclipse-escet-v2.0\bin\cifprod.cmd',
        fullpath_merg_out,
        '--output-mode=error',
        '-o', fullpath_file_out
    ]
    return run_subprocess(command, errors, f"cifprod {index} done successfully")


def run_ciftrimcheck(index, fullpath_trimcheck, cifparallelcompositioni, errors):
    command = [
        r'C:\Users\User\eclipse-escet-v2.0-win32.win32.x86_64\eclipse-escet-v2.0\bin\ciftrimchk.cmd',
        cifparallelcompositioni,
        '--output-mode=error',
        '-r', fullpath_trimcheck
    ]
    return run_subprocess(command, errors, f"run_cifTrimcheck {index} done successfully")


def run_cifsupsynth(index, fullpath_sup_out, fullpath_merge_out, errors):
    command = [
        r'C:\Users\User\eclipse-escet-v2.0-win32.win32.x86_64\eclipse-escet-v2.0\bin\cifsupsynth.cmd',
        fullpath_merge_out,
        '--output-mode=error',
        '-n', 'S',
        '-o', fullpath_sup_out
    ]
    return run_subprocess(command, errors, f"run_cifsupsynth {index} done successfully")
