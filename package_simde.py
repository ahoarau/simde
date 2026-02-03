import os
import zipfile
import shutil
import argparse
import re
import subprocess
import glob

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
    parser.add_argument('--output', '-o', required=True, help='The output archive path (e.g., simde-v0.8.0.zip).')
    parser.add_argument('--source', '-s', default='simde', help='The source directory containing SIMDe headers (default: simde).')
    parser.add_argument('--git-hash', help='Override the git hash embedded in the files (for testing/reproducibility).')
    parser.add_argument('--format', '-f', help='The archive format to create (default: auto-detect from extension). parameters are passed to shutil.make_archive.')

    args = parser.parse_args()

    source_dir = os.path.abspath(args.source)
    output_path = os.path.abspath(args.output)
    output_dir = os.path.dirname(output_path)
    output_filename = os.path.basename(output_path)

    # Determine format
    archive_format = args.format
    if not archive_format:
        if output_filename.endswith('.zip'):
            archive_format = 'zip'
        elif output_filename.endswith('.tar.gz') or output_filename.endswith('.tgz'):
            archive_format = 'gztar'
        elif output_filename.endswith('.tar.bz2') or output_filename.endswith('.tbz2'):
            archive_format = 'bztar'
        elif output_filename.endswith('.tar.xz') or output_filename.endswith('.txz'):
            archive_format = 'xztar'
        elif output_filename.endswith('.tar'):
            archive_format = 'tar'
        else:
             # Default to zip if unknown, or maybe raise error? Let's default to zip for safety and warn
             print(f"Warning: Could not detect format from extension '{output_filename}', defaulting to zip.")
             archive_format = 'zip'

    # Determine base_dir_name (internal root) from filename stem
    # This is a bit tricky because shutil.make_archive appends the extension.
    # If output is 'foo.zip', we want the archive to be named 'foo.zip' and contain 'foo/'?
    # Or usually if output is 'simde-1.0.zip', we want it to contain 'simde-1.0/'.
    # Let's extract the stem.
    
    stem = output_filename
    for ext in ['.zip', '.tar.gz', '.tgz', '.tar.bz2', '.tbz2', '.tar.xz', '.txz', '.tar']:
        if output_filename.endswith(ext):
            stem = output_filename[:-len(ext)]
            break
    
    base_dir_name = stem
    temp_build_dir = os.path.join(output_dir, f".tmp_{base_dir_name}") # Use a temp path for building
    
    # We construct the desired structure in a temporary directory
    # temp_build_dir/
    #   <base_dir_name>/  (this becomes the root inside the archive)
    #     simde/
    #     COPYING

    if os.path.exists(temp_build_dir):
        shutil.rmtree(temp_build_dir)
    
    base_dir = os.path.join(temp_build_dir, base_dir_name)
    output_simde_dir = os.path.join(base_dir, 'simde')
    
    os.makedirs(output_simde_dir)

    git_id = args.git_hash if args.git_hash else get_git_id(source_dir)

    # Dynamic discovery of header files: simde/*/*.h
    # Note: glob pattern matches simde/ subdirectory headers, not top-level simde/*.h,
    # consistent with previous behavior as top-level headers are not standalone targets for this package.
    search_pattern = os.path.join(source_dir, '*', '*.h')
    found_files = glob.glob(search_pattern)
    
    # Sort files for deterministic order (optional but good practice)
    found_files.sort()

    print(f"Amalgamating {len(found_files)} headers from '{source_dir}'...")
    
    # We use the current working directory as the root for relative paths in comments,
    # assuming the script is run from the repo root.
    repo_root = os.getcwd() 

    for source_path in found_files:
        # Calculate relative path from source_dir to preserve structure (e.g. arm/neon.h)
        rel_path = os.path.relpath(source_path, start=source_dir)

        dest_path = os.path.join(output_simde_dir, rel_path)
        dest_dir = os.path.dirname(dest_path)
        
        if not os.path.exists(dest_dir):
            os.makedirs(dest_dir)
            
        # Enforce LF line endings for consistency
        with open(dest_path, 'w', encoding='utf-8', newline='\n') as outfile:
            # We start amalgamation with an empty 'already_included' list for each top-level file
            # so that they are self-contained.
            amalgamate(source_path, outfile, [], repo_root, git_id)

    if os.path.exists('COPYING'):
        shutil.copy('COPYING', os.path.join(base_dir, 'COPYING'))

    print(f"Creating archive {output_path}...")
    
    output_path_no_ext = os.path.splitext(output_path)[0]

    temp_archive_base = os.path.join(temp_build_dir, "archive")
    final_archive_actual_path = shutil.make_archive(
        base_name=temp_archive_base,
        format=archive_format,
        root_dir=temp_build_dir,
        base_dir=base_dir_name
    )
    
    # Now move it to the requested location
    if os.path.exists(output_path):
        os.remove(output_path)
    shutil.move(final_archive_actual_path, output_path)
    
    # Check if we should cleanup temp build
    shutil.rmtree(temp_build_dir)

    print(f"Successfully created {output_path}")

if __name__ == '__main__':
    main()
