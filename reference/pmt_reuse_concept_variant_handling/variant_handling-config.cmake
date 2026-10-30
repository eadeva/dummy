# ============================================================================
# Function to discover all variants
# ============================================================================
#
# Recursively searches for variant declaration files (variants.cmake or
# <prefix>_variants.cmake) starting from the given search roots, includes
# each file, and collects all variant metadata into the parent scope.
#
# After the function is called the following variables will be set:
#
#   DISCOVERED_VARIANT_FILES                      - List of variant file paths found
#   ALL_AVAILABLE_VARIANTS                         - List of all variant names collected
#   <variant>_DESCRIPTION                          - Description of each variant
#   <variant>_AVAILABLE_OPTIONS                    - Available options for each variant
#   <variant>_DEFAULT                              - Default value for each variant
#   <variant>_DEFINES                              - Preprocessor defines for each variant
#   <variant>_TARGET                               - Associated CMake target (if any)
#   VARIANT_<MODULE>_<FEATURE>_<OPTION> (uppercase) - Numeric constant per option
#
# Directories named build, _build, .git, and external are excluded from
# the search automatically.
#
# Parameters:
#   SEARCH_ROOT  - One or more root directories to search (optional, multi-value).
#                  Defaults to CMAKE_CURRENT_SOURCE_DIR or CMAKE_SOURCE_DIR.
#   VARIANT_FILES - Explicit list of variant files to include (optional, multi-value).
#                   When provided, recursive search is skipped.
#                   Hint: On Windows file systems during development, this can
#                   avoid scanning the entire worktree and improve configure time.
#   FOLLOW_SYMLINKS - Optional flag to traverse symlinked directories during
#                     recursive globbing. When omitted, symlinked directories
#                     are not traversed.
#   COMPONENT_TESTS - Option flag. When set, the same convention-based recursive
#                   search is reused to discover the GoogleTest unit-/component-
#                   test projects that ship with the compositions instead of the
#                   variant declaration files. Each
#                       <component>/test/unitTest/<name>/CMakeLists.txt
#                       <component>/test/componentTest/<name>/CMakeLists.txt
#                   is add_subdirectory()'d and every target it defines is
#                   attached to the orchestration target (see TEST_TARGET). The
#                   component's standalone <component>/test/CMakeLists.txt is
#                   deliberately not matched: it uses find_package(GTest CONFIG)
#                   and would not resolve against the FetchContent GoogleTest
#                   used in the unit-test build. Must be called after the
#                   orchestration target already exists.
#   TEST_TARGET  - Name of the orchestration target the discovered tests are
#                  attached to when COMPONENT_TESTS is set (optional, defaults to
#                  'unit_tests').
#
# Example:
#   discover_variants(SEARCH_ROOT "${CMAKE_SOURCE_DIR}/modules" "${CMAKE_SOURCE_DIR}/libs")
#   discover_variants(VARIANT_FILES "${CMAKE_SOURCE_DIR}/components/foo/variants.cmake")
#   discover_variants(
#       VARIANT_FILES
#           "${CMAKE_SOURCE_DIR}/components/foo/variants.cmake"
#           "${CMAKE_SOURCE_DIR}/components/bar/bar_variants.cmake"
#   )
#   discover_variants()  # uses default search root without following symlinks
#   discover_variants(FOLLOW_SYMLINKS)
#   discover_variants(COMPONENT_TESTS SEARCH_ROOT "${CMAKE_CURRENT_SOURCE_DIR}/composition")
#
# ============================================================================
function(discover_variants)
    # Parse optional arguments
    set(options COMPONENT_TESTS FOLLOW_SYMLINKS)
    set(oneValueArgs TEST_TARGET)
    set(multiValueArgs SEARCH_ROOT VARIANT_FILES)
    cmake_parse_arguments(DISCOVER_OPTS "${options}" "${oneValueArgs}" "${multiValueArgs}" ${ARGN})

    # Define the root directories to start searching from
    if(DISCOVER_OPTS_SEARCH_ROOT)
        set(SEARCH_ROOTS "${DISCOVER_OPTS_SEARCH_ROOT}")
    elseif(CMAKE_CURRENT_SOURCE_DIR)
        set(SEARCH_ROOTS "${CMAKE_CURRENT_SOURCE_DIR}")
    else()
        set(SEARCH_ROOTS "${CMAKE_SOURCE_DIR}")
    endif()

    # List of directories to ignore during the search (optional)
    set(EXCLUDE_DIRS
        "${CMAKE_CURRENT_SOURCE_DIR}/build"
        "${CMAKE_CURRENT_SOURCE_DIR}/_build"
        "${CMAKE_CURRENT_SOURCE_DIR}/_builds"
        "${CMAKE_CURRENT_SOURCE_DIR}/.git"
        "${CMAKE_CURRENT_SOURCE_DIR}/external"
        "${CMAKE_SOURCE_DIR}/build"
        "${CMAKE_SOURCE_DIR}/_build"
        "${CMAKE_SOURCE_DIR}/_builds"
        "${CMAKE_SOURCE_DIR}/.git"
        "${CMAKE_SOURCE_DIR}/external"
    )

    # ------------------------------------------------------------------------
    # Component-test discovery mode
    #
    # Reuses the recursive, exclude-aware search above to find the GoogleTest
    # unit-/component-test projects that ship with the compositions and attach
    # them to the orchestration target, instead of listing each component test
    # by hand.
    # ------------------------------------------------------------------------
    if(DISCOVER_OPTS_COMPONENT_TESTS)
        if(DISCOVER_OPTS_TEST_TARGET)
            set(_test_target "${DISCOVER_OPTS_TEST_TARGET}")
        else()
            set(_test_target "unit_tests")
        endif()

        message(STATUS "Searching for component tests...")

        set(_candidate_files)
        foreach(SEARCH_ROOT IN LISTS SEARCH_ROOTS)
            set(_glob_args)
            if(DISCOVER_OPTS_FOLLOW_SYMLINKS)
                list(APPEND _glob_args FOLLOW_SYMLINKS)
            endif()
            file(GLOB_RECURSE ROOT_TEST_FILES ${_glob_args}
                "${SEARCH_ROOT}/*/CMakeLists.txt"
                "${SEARCH_ROOT}/**/*/CMakeLists.txt"
            )
            list(APPEND _candidate_files ${ROOT_TEST_FILES})
        endforeach()

        if(_candidate_files)
            list(REMOVE_DUPLICATES _candidate_files)
        endif()

        set(_test_dirs)
        foreach(file_path IN LISTS _candidate_files)
            # Keep only the convention-based test projects.
            if(NOT file_path MATCHES "/test/(unitTest|componentTest)/[^/]+/CMakeLists.txt$")
                continue()
            endif()
            set(is_excluded FALSE)
            foreach(exclude_dir IN LISTS EXCLUDE_DIRS)
                if(file_path MATCHES "^${exclude_dir}/")
                    set(is_excluded TRUE)
                    break()
                endif()
            endforeach()
            if(NOT is_excluded)
                get_filename_component(_dir "${file_path}" DIRECTORY)
                list(APPEND _test_dirs "${_dir}")
            endif()
        endforeach()

        if(_test_dirs)
            list(REMOVE_DUPLICATES _test_dirs)
        endif()

        if(NOT _test_dirs)
            message(STATUS "No component tests found under: ${SEARCH_ROOTS}")
            return()
        endif()

        foreach(_dir IN LISTS _test_dirs)
            # Derive a unique, filesystem-safe binary directory from the test path.
            file(RELATIVE_PATH _rel "${CMAKE_CURRENT_SOURCE_DIR}" "${_dir}")
            string(REGEX REPLACE "[^A-Za-z0-9_]" "_" _bindir "${_rel}")
            message(STATUS "  Adding component test: ${_dir}")
            add_subdirectory("${_dir}" "${CMAKE_CURRENT_BINARY_DIR}/component_tests/${_bindir}")

            # Attach every target the test project defined to the orchestration
            # target, via the BUILDSYSTEM_TARGETS property so no target name has
            # to be hard-coded here.
            get_directory_property(_dir_targets DIRECTORY "${_dir}" BUILDSYSTEM_TARGETS)
            foreach(_t IN LISTS _dir_targets)
                if(TARGET ${_test_target} AND TARGET ${_t})
                    add_dependencies(${_test_target} ${_t})
                endif()
            endforeach()
        endforeach()

        return()
    endif()

    message(STATUS "Searching for variant declarations...")

    set(FILTERED_VARIANT_FILES)
    if(DISCOVER_OPTS_VARIANT_FILES)
        # Use explicitly provided variant files and skip recursive search.
        foreach(file_path IN LISTS DISCOVER_OPTS_VARIANT_FILES)
            if(EXISTS "${file_path}")
                list(APPEND FILTERED_VARIANT_FILES "${file_path}")
            else()
                message(WARNING "Explicit variant file does not exist and will be ignored: ${file_path}")
            endif()
        endforeach()
    else()
        # Find all files named 'variants.cmake' or '<prefix>_variants.cmake' recursively across all search roots.
        set(SEARCHED_VARIANT_FILES)
        set(_glob_symlink_args)
        if(DISCOVER_OPTS_FOLLOW_SYMLINKS)
            list(APPEND _glob_symlink_args FOLLOW_SYMLINKS)
        endif()

        cmake_policy(PUSH)
        if(NOT DISCOVER_OPTS_FOLLOW_SYMLINKS)
            # CMP0009 NEW keeps GLOB_RECURSE from traversing symlinked
            # directories unless FOLLOW_SYMLINKS is explicitly requested.
            cmake_policy(SET CMP0009 NEW)
        endif()
        foreach(SEARCH_ROOT IN LISTS SEARCH_ROOTS)
            file(GLOB_RECURSE ROOT_VARIANT_FILES ${_glob_symlink_args}
                "${SEARCH_ROOT}/*/variants.cmake"
                "${SEARCH_ROOT}/**/*/variants.cmake"
                "${SEARCH_ROOT}/*/*_variants.cmake"
                "${SEARCH_ROOT}/**/*/*_variants.cmake"
            )
            list(APPEND SEARCHED_VARIANT_FILES ${ROOT_VARIANT_FILES})
        endforeach()
        cmake_policy(POP)

        # Filter out files in excluded directories.
        foreach(file_path IN LISTS SEARCHED_VARIANT_FILES)
            set(is_excluded FALSE)
            foreach(exclude_dir IN LISTS EXCLUDE_DIRS)
                if (file_path MATCHES "^${exclude_dir}/")
                    set(is_excluded TRUE)
                    break()
                endif()
            endforeach()

            if (NOT is_excluded)
                list(APPEND FILTERED_VARIANT_FILES "${file_path}")
            endif()
        endforeach()
    endif()

    # Store the discovered variant files
    set(DISCOVERED_VARIANT_FILES "${FILTERED_VARIANT_FILES}")

    message(STATUS "DISCOVERED_VARIANT_FILES: ${FILTERED_VARIANT_FILES}")


    # Create a list of all available variants across all modules
    set(ALL_AVAILABLE_VARIANTS)

    if (NOT FILTERED_VARIANT_FILES)
        message(STATUS "No 'variants.cmake' files found.")
    else()
        list(LENGTH FILTERED_VARIANT_FILES NUM_VARIANT_FILES)
        message(STATUS "Found ${NUM_VARIANT_FILES} 'variants.cmake' files")
        foreach(variant_file IN LISTS FILTERED_VARIANT_FILES)
            # Extract the directory name as a fallback module name
            message(STATUS "  Including variant file: ${variant_file}")
            get_filename_component(variant_dir "${variant_file}" DIRECTORY)
            get_filename_component(CURRENT_MODULE_NAME "${variant_dir}" NAME)

            # If the file is named <prefix>_variants.cmake, use the prefix as module name
            get_filename_component(variant_filename "${variant_file}" NAME)
            string(REGEX MATCH "^(.+)_variants\\.cmake$" _match "${variant_filename}")
            if(_match)
                set(CURRENT_MODULE_NAME "${CMAKE_MATCH_1}")
            endif()

            message(STATUS "    Module name: ${CURRENT_MODULE_NAME}")

            # Include the variant file to populate variables in this scope
            include("${variant_file}")

            # Collect variant information using the module name
            if(DEFINED VARIANT_${CURRENT_MODULE_NAME}_AVAILABLE_VARIANTS)
                foreach(variant IN LISTS VARIANT_${CURRENT_MODULE_NAME}_AVAILABLE_VARIANTS)
                    list(FIND ALL_AVAILABLE_VARIANTS "${variant}" _variant_index)
                    if(_variant_index EQUAL -1)
                        message(STATUS "    Variant: ${variant}")
                        list(APPEND ALL_AVAILABLE_VARIANTS "${variant}")
                        # Push variant-specific variables to parent scope
                        if(DEFINED ${variant}_DESCRIPTION)
                            set(${variant}_DESCRIPTION "${${variant}_DESCRIPTION}" PARENT_SCOPE)
                        endif()
                        if(DEFINED ${variant}_AVAILABLE_OPTIONS)
                            set(${variant}_AVAILABLE_OPTIONS "${${variant}_AVAILABLE_OPTIONS}" PARENT_SCOPE)
                        endif()
                        if(DEFINED ${variant}_DEFAULT)
                            set(${variant}_DEFAULT "${${variant}_DEFAULT}" PARENT_SCOPE)
                        endif()
                        if(DEFINED ${variant}_DEFINES)
                            set(${variant}_DEFINES "${${variant}_DEFINES}" PARENT_SCOPE)
                        endif()
                        if(DEFINED ${variant}_TARGET)
                            set(${variant}_TARGET "${${variant}_TARGET}" PARENT_SCOPE)
                        endif()
                        # Push individual option constants to parent scope
                        if(DEFINED ${variant}_AVAILABLE_OPTIONS)
                            string(TOUPPER "${variant}" _variant_upper)
                            foreach(_opt IN LISTS ${variant}_AVAILABLE_OPTIONS)
                                string(TOUPPER "${_opt}" _opt_upper)
                                set(_opt_var "${_variant_upper}_${_opt_upper}")
                                if(DEFINED ${_opt_var})
                                    set(${_opt_var} "${${_opt_var}}" PARENT_SCOPE)
                                endif()
                            endforeach()
                        endif()
                    endif()
                endforeach()
            endif()
        endforeach()
    endif()

    list(LENGTH ALL_AVAILABLE_VARIANTS NUM_TOTAL_VARIANTS)
    message(STATUS "${ALL_AVAILABLE_VARIANTS}")
    message(STATUS "Variant discovery complete. Total variants: ${NUM_TOTAL_VARIANTS}")

    # Push results to parent scope
    set(DISCOVERED_VARIANT_FILES "${DISCOVERED_VARIANT_FILES}" PARENT_SCOPE)
    set(ALL_AVAILABLE_VARIANTS "${ALL_AVAILABLE_VARIANTS}" PARENT_SCOPE)
endfunction()

# ============================================================================
# Function to display all discovered variants
# ============================================================================
#
# Prints all discovered variants and their metadata (description, available
# options, default value) to the CMake status output. Supports two output
# formats: a human-readable table (default) and YAML.
#
# Must be called after discover_variants().
#
# Parameters:
#   YAML  - Optional flag. When present, output is formatted as YAML.
#           When absent, output uses a human-readable table format.
#
# Example:
#   display_variants()        # human-readable table
#   display_variants(YAML)    # YAML format
#
# ============================================================================
function(display_variants)
    # Parse optional arguments
    set(options YAML)
    cmake_parse_arguments(DISPLAY_OPTS "${options}" "" "" ${ARGN})

    if(NOT DEFINED ALL_AVAILABLE_VARIANTS OR "${ALL_AVAILABLE_VARIANTS}" STREQUAL "")
        return()
    endif()

    if(DISPLAY_OPTS_YAML)
        # YAML format output
        message(STATUS "")
        message(STATUS "variants:")

        foreach(variant IN LISTS ALL_AVAILABLE_VARIANTS)
            message(STATUS "  ${variant}:")

            if(DEFINED ${variant}_DESCRIPTION)
                message(STATUS "    description: \"${${variant}_DESCRIPTION}\"")
            endif()

            if(DEFINED ${variant}_AVAILABLE_OPTIONS)
                message(STATUS "    available_options:")
                foreach(option IN LISTS ${variant}_AVAILABLE_OPTIONS)
                    message(STATUS "      - \"${option}\"")
                endforeach()
            endif()

            if(DEFINED ${variant}_DEFAULT)
                message(STATUS "    default: \"${${variant}_DEFAULT}\"")
            endif()
        endforeach()

        message(STATUS "")
    else()
        # Original format output
        message(STATUS "")
        message(STATUS "========================================")
        message(STATUS "Available Variants")
        message(STATUS "========================================")

        foreach(variant IN LISTS ALL_AVAILABLE_VARIANTS)
            message(STATUS "")
            message(STATUS "Variant: ${variant}")

            if(DEFINED ${variant}_DESCRIPTION)
                message(STATUS "  Description: ${${variant}_DESCRIPTION}")
            endif()

            if(DEFINED ${variant}_AVAILABLE_OPTIONS)
                message(STATUS "  Available Options: ${${variant}_AVAILABLE_OPTIONS}")
            endif()

            if(DEFINED ${variant}_DEFAULT)
                message(STATUS "  Default: ${${variant}_DEFAULT}")
            endif()
        endforeach()

        message(STATUS "")
        message(STATUS "========================================")
        list(LENGTH ALL_AVAILABLE_VARIANTS NUM_TOTAL_VARIANTS)
        message(STATUS "Total variants: ${NUM_TOTAL_VARIANTS}")
        message(STATUS "========================================")
    endif()
endfunction()

# ============================================================================
# Function to write YAML configuration to a file via a custom target
# ============================================================================
#
# Creates a CMake custom target that generates a YAML file containing the
# active (configured) variant values. The target runs during every build
# so the YAML file stays up to date.
#
# Must be called after discover_variants() and after all set_variant() calls
# have been made, so that the current variant values are captured.
#
# Parameters:
#   FILEPATH     - (required) Absolute or relative path of the YAML file to
#                  generate.
#   TARGET_NAME  - (optional) Name of the custom target. Defaults to
#                  "generate_variants_yaml".
#
# Example:
#   write_variants_yaml(
#       FILEPATH "${CMAKE_BINARY_DIR}/variants.yaml"
#       TARGET_NAME "generate_variants_yaml"
#   )
#
# ============================================================================
function(write_variants_yaml)
    # Parse arguments
    set(options "")
    set(oneValueArgs FILEPATH TARGET_NAME)
    set(multiValueArgs "")
    cmake_parse_arguments(WRITE_OPTS "${options}" "${oneValueArgs}" "${multiValueArgs}" ${ARGN})

    # Validate that required parameters are provided
    if(NOT DEFINED WRITE_OPTS_FILEPATH OR "${WRITE_OPTS_FILEPATH}" STREQUAL "")
        message(FATAL_ERROR "FILEPATH parameter is required for write_variants_yaml()")
    endif()

    if(NOT DEFINED WRITE_OPTS_TARGET_NAME OR "${WRITE_OPTS_TARGET_NAME}" STREQUAL "")
        set(WRITE_OPTS_TARGET_NAME "generate_variants_yaml")
    endif()

    if(NOT DEFINED ALL_AVAILABLE_VARIANTS OR "${ALL_AVAILABLE_VARIANTS}" STREQUAL "")
        message(WARNING "No variants available to write. Call discover_variants() first.")
        return()
    endif()

    # Create a CMake script that will be executed as a custom target
    set(SCRIPT_FILE "${CMAKE_BINARY_DIR}/.cmake_scripts/${WRITE_OPTS_TARGET_NAME}.cmake")

    # Ensure script directory exists
    file(MAKE_DIRECTORY "${CMAKE_BINARY_DIR}/.cmake_scripts")

    # Generate the script content with all variant data
    set(SCRIPT_CONTENT "# Auto-generated CMake script to write variant configuration\n")
    string(APPEND SCRIPT_CONTENT "# Target: ${WRITE_OPTS_TARGET_NAME}\n")
    string(APPEND SCRIPT_CONTENT "# Output: ${WRITE_OPTS_FILEPATH}\n\n")

    # Generate YAML content as a string in the script
    set(YAML_CONTENT "# Active Variant Configuration\n")
    string(APPEND YAML_CONTENT "# Generated on: \${CMAKE_CURRENT_TIMESTAMP}\n")
    string(APPEND YAML_CONTENT "# This file contains the actual active/validated variant values\n")
    string(APPEND YAML_CONTENT "\n")
    string(APPEND YAML_CONTENT "variants:\n")

    foreach(variant IN LISTS ALL_AVAILABLE_VARIANTS)
        if(DEFINED ${variant})
            string(APPEND YAML_CONTENT "  ${variant}: \"${${variant}}\"\n")
        else()
            string(APPEND YAML_CONTENT "  ${variant}: null  # Not configured\n")
        endif()
    endforeach()

    get_filename_component(WRITE_OPTS_OUTPUT_DIR "${WRITE_OPTS_FILEPATH}" DIRECTORY)
    file(MAKE_DIRECTORY "${WRITE_OPTS_OUTPUT_DIR}")
    file(WRITE "${WRITE_OPTS_FILEPATH}" "${YAML_CONTENT}")
    message(STATUS "Active variants YAML configuration written to: ${WRITE_OPTS_FILEPATH}")

    # Write the YAML content into the script
    string(APPEND SCRIPT_CONTENT "set(YAML_CONTENT \"")
    # Escape the YAML content for CMake
    string(REPLACE "\\" "\\\\" YAML_CONTENT "${YAML_CONTENT}")
    string(REPLACE "\"" "\\\"" YAML_CONTENT "${YAML_CONTENT}")
    string(REPLACE "\n" "\\n" YAML_CONTENT "${YAML_CONTENT}")
    string(APPEND SCRIPT_CONTENT "${YAML_CONTENT}")
    string(APPEND SCRIPT_CONTENT "\")\n\n")

    string(APPEND SCRIPT_CONTENT "file(WRITE \"${WRITE_OPTS_FILEPATH}\" \"\${YAML_CONTENT}\")\n")
    string(APPEND SCRIPT_CONTENT "message(STATUS \"Active variants YAML configuration written to: ${WRITE_OPTS_FILEPATH}\")\n")

    # Write the script file
    file(WRITE "${SCRIPT_FILE}" "${SCRIPT_CONTENT}")

    # Create the custom target, unless a target with this name was already
    # created by another module/subdirectory configured in the same build
    # tree (e.g. app + fbl both configured together for unit testing).
    if(TARGET ${WRITE_OPTS_TARGET_NAME})
        message(STATUS "Target '${WRITE_OPTS_TARGET_NAME}' already exists (created by another directory) - skipping re-creation")
    else()
        add_custom_target(${WRITE_OPTS_TARGET_NAME} ALL
            COMMAND ${CMAKE_COMMAND} -P "${SCRIPT_FILE}"
            COMMENT "Generating active variants YAML configuration..."
            VERBATIM
        )

        message(STATUS "Created target '${WRITE_OPTS_TARGET_NAME}' to generate variants YAML at: ${WRITE_OPTS_FILEPATH}")
    endif()
endfunction()

# ============================================================================
# Function to validate variant settings
# ============================================================================
#
# Iterates over all discovered variants and checks that:
#   - Each variant name carries the VARIANT_ prefix.
#   - Each variant has been assigned a value (not undefined).
#   - The assigned value is among the variant's AVAILABLE_OPTIONS.
#
# When a variant's value is the special keyword "default", it is
# automatically reset to the variant's default value.
#
# If any variant is missing or has an invalid value the function emits
# a FATAL_ERROR after printing a summary of all issues.
#
# Must be called after discover_variants() and all set_variant() calls.
#
# Parameters:
#   (none)
#
# Example:
#   discover_variants()
#   set_variant(VARIANT_NAME VARIANT_global_ChipFamily VALUE "TraveoII")
#   validate_variants()
#
# ============================================================================
function(validate_variants)
    # Check if variants were already discovered
    if(NOT DEFINED ALL_AVAILABLE_VARIANTS)
        message(STATUS "No variants discovered. Call discover_variants() first before validate_variants().")
        return()
    endif()

    message(STATUS "")
    message(STATUS "========================================")
    message(STATUS "Validating Variant Settings")
    message(STATUS "========================================")

    set(VALIDATION_ERRORS)
    set(MISSING_VARIANTS)
    set(INVALID_VALUES)

    foreach(variant IN LISTS ALL_AVAILABLE_VARIANTS)
        # Verify variant has VARIANT_ prefix
        if(NOT variant MATCHES "^VARIANT_")
            message(WARNING "⚠ ${variant}: Variant name should start with VARIANT_ prefix")
        endif()

        # Check if variant is set
        if(NOT DEFINED ${variant})
            list(APPEND MISSING_VARIANTS "${variant}")
            message(STATUS "❌ ${variant}: NOT SET")
            if(DEFINED ${variant}_DEFAULT)
                message(STATUS "   → Suggested: set(${variant} \"${${variant}_DEFAULT}\" CACHE STRING \"\")")
            endif()
        else()
            # Check if value is "default" keyword - reset to default value
            if("${${variant}}" STREQUAL "default")
                if(DEFINED ${variant}_DEFAULT)
                    set(${variant} "${${variant}_DEFAULT}" CACHE STRING "${${variant}_DESCRIPTION}" FORCE)
                    message(STATUS "✓ ${variant}: RESET TO DEFAULT → '${${variant}_DEFAULT}'")
                    # Push updated value to parent scope
                    set(${variant} "${${variant}_DEFAULT}" PARENT_SCOPE)
                else()
                    message(WARNING "⚠ ${variant}: 'default' keyword used but no default value defined")
                endif()
            else()
                # Validate against available options
                if(DEFINED ${variant}_AVAILABLE_OPTIONS)
                    list(FIND ${variant}_AVAILABLE_OPTIONS "${${variant}}" option_index)
                    if(option_index EQUAL -1)
                        list(APPEND INVALID_VALUES "${variant}")
                        message(STATUS "❌ ${variant}: INVALID VALUE '${${variant}}'")
                        message(STATUS "   → Available options: ${${variant}_AVAILABLE_OPTIONS}")
                        if(DEFINED ${variant}_DEFAULT)
                            message(STATUS "   → Default: ${${variant}_DEFAULT}")
                        endif()
                    else()
                        message(STATUS "✓ ${variant}: '${${variant}}' (valid)")
                    endif()
                else()
                    # No options defined, just report the value
                    message(STATUS "✓ ${variant}: '${${variant}}' (no validation rules)")
                endif()
            endif()
        endif()
    endforeach()

    message(STATUS "")
    message(STATUS "========================================")
    message(STATUS "Validation Summary")
    message(STATUS "========================================")

    list(LENGTH MISSING_VARIANTS num_missing)
    list(LENGTH INVALID_VALUES num_invalid)

    if(num_missing GREATER 0)
        message(STATUS "Missing variants: ${num_missing}")
        foreach(missing IN LISTS MISSING_VARIANTS)
            message(STATUS "  - ${missing}")
        endforeach()
        list(APPEND VALIDATION_ERRORS "Missing variants: ${num_missing}")
    endif()

    if(num_invalid GREATER 0)
        message(STATUS "Invalid values: ${num_invalid}")
        foreach(invalid IN LISTS INVALID_VALUES)
            message(STATUS "  - ${invalid} = '${${invalid}}'")
        endforeach()
        list(APPEND VALIDATION_ERRORS "Invalid values: ${num_invalid}")
    endif()

    if(num_missing EQUAL 0 AND num_invalid EQUAL 0)
        message(STATUS "✓ All variants are properly configured!")
    else()
        message(FATAL_ERROR "Variant validation failed. Please fix the issues above.")
    endif()

    message(STATUS "========================================")
endfunction()


# ============================================================================
# Function to create variant variables
# ============================================================================
#
# After the function is called following variables will be set.
#
#   <MODULE_NAME>_<FEATURE_NAME>                            - Name of the feature
#   VARIANT_<MODULE_NAME>_<FEATURE_NAME>_NAME               - Name of the variant
#   VARIANT_<MODULE_NAME>_<FEATURE_NAME>_AVAILABLE_OPTIONS  - List of available options
#   VARIANT_<MODULE_NAME>_<FEATURE_NAME>_DEFAULT            - Default option
#   VARIANT_<MODULE_NAME>_<FEATURE_NAME>_DESCRIPTION        - Description of the variant
#   VARIANT_<MODULE_NAME>_<FEATURE_NAME>_DEFINES            - List of preprocessor define constants
#   VARIANT_<MODULE_NAME>_<FEATURE_NAME>_TARGET              - CMake target (if specified)
#
# For each option, a preprocessor define constant is created:
#   VARIANT_<MODULE_NAME>_<FEATURE_NAME>_<OPTION_NAME> = <index>  (0, 1, 2, ...)
#
# These can be used in C code as:
#   #if VARIANT_<MODULE_NAME>_<FEATURE_NAME> == VARIANT_<MODULE_NAME>_<FEATURE_NAME>_<OPTION_NAME>
#
# The module name is derived automatically from the calling file's name:
#   If the file is named <prefix>_variants.cmake, the prefix is used.
#   Otherwise, the parent directory name is used as fallback.
#
# Parameters:
#   FEATURE_NAME    - Name of the feature
#   OPTIONS         - List of available options
#   DESCRIPTION     - Description of the variant
#   DEFAULT         - Default option value (optional, defaults to first option)
#   TARGET          - CMake target to associate with this variant (optional)
#
# ============================================================================
# Example usage of the function
# ============================================================================
#
#   create_variant_feature(
#       FEATURE_NAME "DebugLevel"
#       OPTIONS "standard" "debug"
#       DEFAULT "standard"
#       DESCRIPTION "Debug level configuration for the module"
#   )
#
# ============================================================================
function(create_variant_feature)
    set(options)
    set(oneValueArgs FEATURE_NAME DESCRIPTION DEFAULT TARGET)
    set(multiValueArgs OPTIONS)

    cmake_parse_arguments(ARG "${options}" "${oneValueArgs}" "${multiValueArgs}" ${ARGN})

    # Validate required arguments
    if(NOT DEFINED ARG_FEATURE_NAME)
        message(FATAL_ERROR "FEATURE_NAME is required")
    endif()

    if(NOT DEFINED ARG_OPTIONS OR NOT ARG_OPTIONS)
        message(FATAL_ERROR "OPTIONS list is required and cannot be empty")
    endif()
    if(NOT DEFINED ARG_DESCRIPTION)
        message(FATAL_ERROR "DESCRIPTION is required")
    endif()

    # Use first option as default if not specified
    if(NOT DEFINED ARG_DEFAULT)
        list(GET ARG_OPTIONS 0 ARG_DEFAULT)
    endif()

    # Derive module name from the calling file's name
    # If file is <prefix>_variants.cmake, use the prefix; otherwise use directory name
    get_filename_component(_calling_filename "${CMAKE_CURRENT_LIST_FILE}" NAME)
    string(REGEX MATCH "^(.+)_variants\\.cmake$" _prefix_match "${_calling_filename}")
    if(_prefix_match)
        set(MODULE_NAME "${CMAKE_MATCH_1}")
    else()
        get_filename_component(MODULE_NAME "${CMAKE_CURRENT_LIST_DIR}" NAME)
    endif()

    # Generate variable names
    set(VARIANT_NAME "VARIANT_${MODULE_NAME}_${ARG_FEATURE_NAME}")

    set(_module_available_variants "${VARIANT_${MODULE_NAME}_AVAILABLE_VARIANTS}")
    list(FIND _module_available_variants "${VARIANT_NAME}" _variant_index)
    if(_variant_index GREATER -1)
        message(WARNING "Variant '${VARIANT_NAME}' is already defined.")
    else()
        message(STATUS "create_variant_feature:  ${VARIANT_NAME}")

        # Set the variables
        set(${MODULE_NAME}_${ARG_FEATURE_NAME} "${ARG_FEATURE_NAME}")
        set(${VARIANT_NAME}_NAME "${VARIANT_NAME}" PARENT_SCOPE)
        set(${VARIANT_NAME}_AVAILABLE_OPTIONS "${ARG_OPTIONS}" PARENT_SCOPE)
        set(${VARIANT_NAME}_DEFAULT "${ARG_DEFAULT}" PARENT_SCOPE)
        set(${VARIANT_NAME}_DESCRIPTION "${ARG_DESCRIPTION}" PARENT_SCOPE)

        # Store associated CMake target if specified
        if(DEFINED ARG_TARGET AND NOT "${ARG_TARGET}" STREQUAL "")
            set(${VARIANT_NAME}_TARGET "${ARG_TARGET}" PARENT_SCOPE)
        endif()

        # Generate preprocessor define constants for each option
        # Each option gets an incremental index: VARIANT_NAME_OPTION = 0, 1, 2, ...
        # All define names are uppercase
        string(TOUPPER "${VARIANT_NAME}" _variant_upper)
        set(_option_index 0)
        set(_defines_list)
        foreach(_option IN LISTS ARG_OPTIONS)
            string(TOUPPER "${_option}" _option_upper)
            set(_define_name "${_variant_upper}_${_option_upper}")
            set(${_define_name} ${_option_index} PARENT_SCOPE)
            list(APPEND _defines_list "${_define_name}=${_option_index}")
            math(EXPR _option_index "${_option_index} + 1")
        endforeach()
        set(${VARIANT_NAME}_DEFINES "${_defines_list}" PARENT_SCOPE)

        list(APPEND VARIANT_${MODULE_NAME}_AVAILABLE_VARIANTS "${VARIANT_NAME}")
        set(VARIANT_${MODULE_NAME}_AVAILABLE_VARIANTS "${VARIANT_${MODULE_NAME}_AVAILABLE_VARIANTS}" PARENT_SCOPE)
    endif()

endfunction()


# ============================================================================
# Function to set the active variant value
# ============================================================================
#
# Sets the variant to the given value (or to its default if VALUE is "default"),
# validates it against the available options, stores it in the CMake cache,
# and adds the corresponding compile definitions globally.
#
# The following compile definitions are set:
#   - All option constants:  VARIANT_NAME_<OPTION> = <index>  (for every option)
#   - The active value:      VARIANT_NAME = <index of selected option>
#
# Parameters:
#   VARIANT_NAME  - Full variant variable name (e.g. VARIANT_global_ChipFamily)
#   VALUE         - The value to set (must be one of the available options,
#                   or "default" to use the default value)
#
# Example:
#   set_variant(VARIANT_NAME VARIANT_global_ChipFamily VALUE "TraveoII")
#
# ============================================================================
function(set_variant)
    set(options)
    set(oneValueArgs VARIANT_NAME VALUE)
    set(multiValueArgs)
    cmake_parse_arguments(ARG "${options}" "${oneValueArgs}" "${multiValueArgs}" ${ARGN})

    # Validate required arguments
    if(NOT DEFINED ARG_VARIANT_NAME)
        message(FATAL_ERROR "set_variant: VARIANT_NAME is required")
    endif()
    if(NOT DEFINED ARG_VALUE)
        message(FATAL_ERROR "set_variant: VALUE is required")
    endif()

    set(_variant "${ARG_VARIANT_NAME}")
    set(_value "${ARG_VALUE}")

    # Check that the variant was previously created
    if(NOT DEFINED ${_variant}_AVAILABLE_OPTIONS)
        message(FATAL_ERROR "set_variant: ${_variant} is not a known variant (no AVAILABLE_OPTIONS found). Call create_variant_feature() first.")
    endif()

    # Handle the special "default" keyword
    if("${_value}" STREQUAL "default")
        if(DEFINED ${_variant}_DEFAULT)
            set(_value "${${_variant}_DEFAULT}")
            message(STATUS "set_variant: ${_variant} using default value '${_value}'")
        else()
            message(FATAL_ERROR "set_variant: ${_variant} set to 'default' but no default value is defined")
        endif()
    endif()

    # Validate the value against available options
    list(FIND ${_variant}_AVAILABLE_OPTIONS "${_value}" _option_index)
    if(_option_index EQUAL -1)
        message(FATAL_ERROR "set_variant: '${_value}' is not a valid option for ${_variant}. Available options: ${${_variant}_AVAILABLE_OPTIONS}")
    endif()

    # Store the value in the cache
    set(${_variant} "${_value}" CACHE STRING "${${_variant}_DESCRIPTION}" FORCE)
    # Also propagate to parent scope
    set(${_variant} "${_value}" PARENT_SCOPE)

    message(STATUS "set_variant: ${_variant} = '${_value}'")

    # Build the list of compile definitions:
    # 1) All option constants (VARIANT_NAME_OPTION=index) - all uppercase
    # 2) The active variant value (VARIANT_NAME=index_of_selected_option) - uppercase
    string(TOUPPER "${_variant}" _variant_upper)
    set(_compile_defs)
    foreach(_def IN LISTS ${_variant}_DEFINES)
        list(APPEND _compile_defs "${_def}")
    endforeach()

    # Add the active value define: VARIANT_NAME = numeric index of selected option
    string(TOUPPER "${_value}" _value_upper)
    set(_active_define_name "${_variant_upper}_${_value_upper}")
    if(DEFINED ${_active_define_name})
        list(APPEND _compile_defs "${_variant_upper}=${${_active_define_name}}")
    else()
        # Fallback: use the list index directly
        list(APPEND _compile_defs "${_variant_upper}=${_option_index}")
    endif()

    # Apply compile definitions globally only if no target is associated.
    # Standalone script mode (cmake -P ...) does not provide project-level
    # compile-definition commands, but discovery still needs to evaluate the
    # variant files and populate the metadata without failing.
    if(NOT DEFINED ${_variant}_TARGET OR "${${_variant}_TARGET}" STREQUAL "")
        if(COMMAND add_compile_definitions)
            add_compile_definitions(${_compile_defs})
            message(STATUS "set_variant: Compile definitions added globally")
            message(STATUS "  Definitions: ${_compile_defs}")
        else()
            message(STATUS "set_variant: add_compile_definitions is unavailable in script mode; skipping global definitions for ${_variant}")
        endif()
    else()
        message(STATUS "set_variant: Skipping global definitions for ${_variant} (target '${${_variant}_TARGET}' specified, use set_target_variants())")
    endif()
endfunction()


# ============================================================================
# Function to apply variant compile definitions to associated targets
# ============================================================================
#
# Iterates over all discovered variants and, for each variant that has an
# associated TARGET (set via create_variant_feature()), adds the variant
# compile definitions to that target via target_compile_definitions().
#
# This function takes no parameters. It relies on the variant values already
# set by prior calls to set_variant().
#
# Must be called after:
#   1. All relevant targets have been created (e.g. via add_library/add_executable)
#   2. All set_variant() calls have been made
#
# Example:
#   set_target_variants()
#
# ============================================================================
function(set_target_variants)
    if(NOT DEFINED ALL_AVAILABLE_VARIANTS)
        message(STATUS "set_target_variants: No variants discovered. Nothing to do.")
        return()
    endif()

    foreach(_variant IN LISTS ALL_AVAILABLE_VARIANTS)
        # Skip variants without an associated target
        if(NOT DEFINED ${_variant}_TARGET OR "${${_variant}_TARGET}" STREQUAL "")
            continue()
        endif()

        set(_target "${${_variant}_TARGET}")

        # Skip if the variant has not been set yet
        if(NOT DEFINED ${_variant})
            message(WARNING "set_target_variants: ${_variant} has a target '${_target}' but no value has been set. Skipping.")
            continue()
        endif()

        if(NOT TARGET ${_target})
            message(FATAL_ERROR "set_target_variants: Target '${_target}' associated with ${_variant} does not exist. Ensure the target is created before calling set_target_variants().")
        endif()

        set(_value "${${_variant}}")

        # Build the list of compile definitions
        string(TOUPPER "${_variant}" _variant_upper)
        set(_compile_defs)
        foreach(_def IN LISTS ${_variant}_DEFINES)
            list(APPEND _compile_defs "${_def}")
        endforeach()

        # Add the active value define
        string(TOUPPER "${_value}" _value_upper)
        set(_active_define_name "${_variant_upper}_${_value_upper}")
        if(DEFINED ${_active_define_name})
            list(APPEND _compile_defs "${_variant_upper}=${${_active_define_name}}")
        else()
            list(FIND ${_variant}_AVAILABLE_OPTIONS "${_value}" _option_index)
            list(APPEND _compile_defs "${_variant_upper}=${_option_index}")
        endif()

        target_compile_definitions(${_target} PUBLIC ${_compile_defs})
        message(STATUS "set_target_variants: Compile definitions for ${_variant} added to target '${_target}'")
        message(STATUS "  Definitions: ${_compile_defs}")
    endforeach()
endfunction()
