import re
from pathlib import Path
from typing import List


def find_regex_files_in_path(
    directory_path: str, regex_pattern: str
) -> List[Path]:
    """
    Search for files matching a given regex pattern in a specified path recursively.

    Args:
        directory_path (str): The path to the directory to search in.
        regex_pattern (str): The regex pattern to match file names.

    Returns:
        List[Path]: A list of Path objects representing the matching files.
    """

    # Compile the regex pattern
    pattern = re.compile(regex_pattern)

    # Convert the directory path to a Path object
    directory = Path(directory_path)

    # List to store matching files
    matching_files = []

    # Iterate over all files in the directory and subdirectories
    for file_path in directory.rglob('*'):
        if file_path.is_file() and pattern.search(file_path.name):
            matching_files.append(str(file_path))

    return matching_files


def find_regex_dirs_in_path(
    directory_path: str, regex_pattern: str
) -> List[Path]:
    """
    Search for files matching a given regex pattern in a specified path recursively.

    Args:
        directory_path (str): The path to the directory to search in.
        regex_pattern (str): The regex pattern to match file names.

    Returns:
        List[Path]: A list of Path objects representing the matching files.
    """
    # Compile the regex pattern
    pattern = re.compile(regex_pattern)

    # Convert the directory path to a Path object
    directory = Path(directory_path)

    # List to store matching files
    matching_files = []

    # Iterate over all files in the directory and subdirectories
    for path in directory.rglob('*'):
        if path.is_dir() and pattern.search(path.name):
            matching_files.append(str(path))

    return matching_files
