import os
import zipfile
import shutil
import argparse
import re
import subprocess

# The exact list of files from simde-0.8.4-example/simde
# excluding the _BACKUP_, _BASE_, _LOCAL_, _REMOTE_ files which look like git conflict artifacts.
EXPECTED_FILES = [
    "arm/neon.h",
    "arm/sve.h",
    "mips/msa.h",
    "wasm/relaxed-simd.h",
    "wasm/simd128.h",
    "x86/aes.h",
    "x86/avx.h",
    "x86/avx2.h",
    "x86/avx512.h",
    "x86/clmul.h",
    "x86/f16c.h",
    "x86/fma.h",
    "x86/gfni.h",
    "x86/mmx.h",
    "x86/sse.h",
    "x86/sse2.h",
    "x86/sse3.h",
    "x86/sse4.1.h",
    "x86/sse4.2.h",
    "x86/ssse3.h",
    "x86/svml.h",
    "x86/xop.h"
]

amalgamate_include = re.compile(r'^\s*#\s*include\s+\"([^)]+)\"\s$')

def get_git_id(srcdir):
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=srcdir).decode().strip()
    except:
        return "unknown"

def amalgamate(filename, stream, already_included, src_root, git_id):
    full_path = os.path.realpath(filename)
    srcdir = os.path.dirname(full_path)

    # Replicate behavior of original amalgamate.py: print header at start of every call
    stream.write('/* AUTOMATICALLY GENERATED FILE, DO NOT MODIFY */\n')
    stream.write(f'/* {git_id} */\n')

    if full_path not in already_included:
        already_included.append(full_path)
        try:
            with open(filename, 'r', encoding='utf-8') as input_file:
                # Normalize path separators to forward slash for consistency
                rel_path_str = os.path.relpath(full_path, start=src_root).replace('\\', '/')
                stream.write('/* :: Begin ' + rel_path_str + ' :: */\n')
                for source_line in input_file:
                    a9e_inc_m = amalgamate_include.match(source_line)
                    if a9e_inc_m:
                        inc_path = os.path.join(srcdir, a9e_inc_m.group(1))
                        if os.path.exists(inc_path):
                            amalgamate(inc_path, stream, already_included, src_root, git_id)
                        else:
                             # If file doesn't exist (maybe system header or error), write original line
                            stream.write(source_line)
                    else:
                        stream.write(source_line)
                stream.write('/* :: End ' + rel_path_str + ' :: */\n')
        except FileNotFoundError:
             print(f"Warning: Could not find file to amalgamate: {filename}")
             stream.write(f"/* ERROR: Could not find file {filename} */\n")

def main():
    parser = argparse.ArgumentParser(description='Package SIMDe headers into a zip archive matching example structure with amalgamation.')
    parser.add_argument('version', help='The version string to use (e.g., 0.8.4).')
    parser.add_argument('--source', '-s', default='simde', help='The source directory containing SIMDe headers (default: simde).')
    parser.add_argument('--output-dir', '-o', help='The output directory for the archive (default: current directory).')
    parser.add_argument('--git-hash', help='Override the git hash embedded in the files (for testing/reproducibility).')

    args = parser.parse_args()

    version = args.version
    source_dir = os.path.abspath(args.source)
    output_dir = args.output_dir if args.output_dir else '.'
    
    base_dir_name = f'simde-{version}'
    base_dir = os.path.join(output_dir, base_dir_name)
    output_simde_dir = os.path.join(base_dir, 'simde')
    archive_name = os.path.join(output_dir, f'simde-{version}.zip')

    if os.path.exists(base_dir):
        shutil.rmtree(base_dir)
    if os.path.exists(archive_name):
        os.remove(archive_name)

    os.makedirs(output_simde_dir)

    git_id = args.git_hash if args.git_hash else get_git_id(source_dir)

    print(f"Amalgamating {len(EXPECTED_FILES)} specific headers from '{source_dir}'...")
    
    # We use the current working directory as the root for relative paths in comments,
    # assuming the script is run from the repo root.
    repo_root = os.getcwd() 

    for rel_path in EXPECTED_FILES:
        source_path = os.path.join(source_dir, rel_path)
        dest_path = os.path.join(output_simde_dir, rel_path)
        dest_dir = os.path.dirname(dest_path)
        
        if not os.path.exists(dest_dir):
            os.makedirs(dest_dir)
            
        if os.path.exists(source_path):
            # Enforce LF line endings for consistency
            with open(dest_path, 'w', encoding='utf-8', newline='\n') as outfile:
                # We start amalgamation with an empty 'already_included' list for each top-level file
                # so that they are self-contained.
                amalgamate(source_path, outfile, [], repo_root, git_id)
        else:
            print(f"Warning: Source file '{source_path}' not found. Skipping.")

    if os.path.exists('COPYING'):
        shutil.copy('COPYING', os.path.join(base_dir, 'COPYING'))

    print(f"Creating archive {archive_name}...")
    with zipfile.ZipFile(archive_name, 'w', zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(base_dir):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, start=output_dir)
                zf.write(file_path, arcname)

    print(f"Successfully created {archive_name}")

if __name__ == '__main__':
    main()
