import argparse
import concurrent.futures
import os
from pathlib import Path


def remove_empty_lines_from_file(file_path):
    """
    Remove empty lines from a given file.

    Args:
        file_path (Path): Path to the file to be processed.
    """
    try:
        with file_path.open('r', encoding='utf-8') as file:
            lines = file.readlines()

        if (
            not lines[0]
            .strip()
            .startswith(
                '// This file is automatically processed by the script i_file_empty_line_remover.py'
            )
        ):
            with file_path.open('w', encoding='utf-8') as file:
                file.write(
                    '// This file is automatically processed by the script i_file_empty_line_remover.py\n'
                )
                file.write(f'// Original file path: {file_path.resolve()}\n\n')
                for line in lines:
                    if line.strip():
                        file.write(line)

            print(f'Processed file: {file_path}')
    except Exception as e:
        print(f'Error processing file {file_path}: {e}')


def process_directory(directory_path, extensions):
    """
    Process all files with specified extensions in a given directory by removing empty lines.

    Args:
        directory_path (Path): Path to the directory to be processed.
        extensions (list): List of file extensions to process.
    """
    try:
        files = []
        for ext in extensions:
            files.extend(directory_path.rglob(f'*{ext}'))

        num_cores = os.cpu_count() or 4
        print(
            f'[EMPTY_LINE_REMOVER] Processing {len(files)} files using {num_cores} workers...'
        )
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=num_cores
        ) as executor:
            futures = [
                executor.submit(remove_empty_lines_from_file, file_path)
                for file_path in files
            ]
            for future in concurrent.futures.as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    print(f'Error processing file: {e}')
    except Exception as e:
        print(f'Error processing directory {directory_path}: {e}')


def main():
    """
    Main function to parse command-line arguments and initiate processing.
    """
    parser = argparse.ArgumentParser(
        description='Remove empty lines from all files with specified extensions in a given folder path.'
    )
    parser.add_argument(
        '-f',
        '--folder_path',
        type=str,
        help='Path to the folder containing files.',
    )
    parser.add_argument(
        '-e',
        '--extensions',
        nargs='*',
        default=['.i'],
        help='List of file extensions to process (default: .i).',
    )

    args = parser.parse_args()
    folder_path = Path(args.folder_path)

    if not folder_path.is_dir():
        print(f'Error: {folder_path} is not a valid directory.')
        return

    process_directory(folder_path, args.extensions)


if __name__ == '__main__':
    """
    Entry point of the script.
    """
    main()
