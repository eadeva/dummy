Re-Use Concept — Variant Model for Reusable Components
======================================================

.. eng-method:: Re-Use Concept — Variant Model for Reusable Components
   :id: ENG_Method_software_019
   :lifecycle_status: draft
   :responsible: Florian Merkert (XC-CE/EMT1)
   :proxy: n/a
   :orga_contact: wom.50991320-mgt@bcn.bosch.com (PJ-PMT)

Short description
-----------------

This document describes a reuse concept focused on a variant model for components.
Goal: Make components reusable across repositories while supporting configurable
variants (build-time file selection, compile defines, or string/boolean options)
in a verifiable, discoverable and consistent way.

Audience
--------

- Component authors and integrators
- Build/CI engineers (CMake & Bazel)
- Architects and platform teams

Design principles (pillars)
---------------------------

- Each component declares its direct configuration, sources, tests and docs
  inside its build files (CMakeLists.txt / BUILD + .bzl).
- Dependencies are declared in those build files.
- Each component optionally ships a dedicated variant definition file
  next to its build file (recommended).
- Variants can:

  - include/exclude source files during build,
  - provide compile-time defines,
  - be strings or booleans.

- A Variant Analysis (collector) aggregates all component variant files and
  exposes a canonical list of features and options.
- The build system applies a consistent prefix for variant variables so
  top-level configuration is unambiguous.
- A validation component prevents typos and invalid option selections.

Terminology
-----------

- Variant: a named configuration point of a component (e.g. "DebugLevel"
  with options "standard" / "debug").
- Variant definition file: a file placed next to the component that declares variants, options, defaults and descriptions.
- **Configured Variant Variable:** The CMake variable that holds the user's selected option for a variant. This variable follows the `VARIANT_<ModuleName>_<FeatureName>` convention.

  - Example: `VARIANT_rbx_LoPwrHndlr_DebugLevel` would hold `standard` or `debug`.

Naming conventions for variant definition files
-----------------------------------------------

Mandatory file names:

- CMake: `variants.cmake` or `<prefix>_variants.cmake` (e.g., `LoPwrHndlr_variants.cmake`)
- Bazel/Starlark: `variants.star` (or `variants.bzl`)

.. _reuse_concept_define_variants:

Component Level: Define Variants (CMake example)
------------------------------------------------

Component authors declare their component's variants using the `create_variant_feature` helper function within their `variants.cmake` file.
This function simplifies the definition process by handling boilerplate.
The module name equals the directory name in which the `variants.cmake` file is located.
If the `MODULE_NAME` shall be different, it can be set explicitly by using the `<prefix>` attribute in the file name (e.g., `LoPwrHndlr_variants.cmake`).


.. code-block:: cmake

    # File: components/LoPwrHndlr/variants.cmake

    # Define Feature 1: Debug Level
    create_variant_feature(
        FEATURE_NAME "DebugLevel"
        OPTIONS "standard" "debug"
        DEFAULT "standard"
        DESCRIPTION "Debug level configuration for the module"
    )

    # Define Feature 2: Operating Mode
    create_variant_feature(
        FEATURE_NAME "Mode"
        OPTIONS "foo" "bar"
        DEFAULT "foo"
        DESCRIPTION "Operating mode selection for the module"
    )

.. code-block:: cmake

    # File: components/global_variants.cmake

    # Example for a specific chip type variant
    create_variant_feature(
        FEATURE_NAME "CHIP_TYPE"
        OPTIONS "4BF" "4BB"
        DEFAULT "4BF"
        DESCRIPTION "Traveo Chip Type"
        TARGET "test_lib"
    )

Component Level: Define Variants (Bazel / Starlark Example)
-----------------------------------------------------------

For Bazel, component variants are declared as structured dictionaries in a `variants.star` file. A Bazel-specific collector mechanism (e.g., repository rules or Starlark functions) would process these definitions to expose `config_settings` or equivalent structures to consuming targets.

.. note::
   The concept for Bazel integration is described here, but the actual implementation for the Bazel build system is not yet available. This documentation focuses on the implemented CMake solution.

.. code-block:: python

    # File: components/LoPwrHndlr/variants.star
    MODULE_NAME = "LoPwrHndlr"

    FEATURES = {
        "DebugLevel": {
            "available_options": ["standard", "debug"],
            "default": "standard",
            "description": "Debug level configuration for the module",
        },
        "Mode": {
            "available_options": ["foo", "bar"],
            "default": "foo",
            "description": "Operating mode selection for the module",
        },
        "CHIP_TYPE": {
            "available_options": ["4BF", "4BB"],
            "default": "4BF",
            "description": "Traveo Chip Type",
        },
    }

    # A repository rule or a helper Starlark function will collect these data
    # and expose config_settings or select() maps to consuming targets.

.. _reuse_concept_activate_variants:

Top-level: Activate Variants (CMake example)
--------------------------------------------

The build system or user configures active variants at the top-level by setting CMake cache variables. These variables follow the `VARIANT_<ModuleName>_<FeatureName>` convention.

.. code-block:: cmake

    # Set specific variant options for components.
    # from the component's variant definition if available.
    set_variant(VARIANT_NAME VARIANT_rbx_LoPwrHndlr_Mode VALUE "bar")
    set_variant(VARIANT_NAME VARIANT_global_CHIP_TYPE VALUE "4BF")


.. _reuse_concept_variant_helpers:

Functions available for dealing with variants
---------------------------------------------

discover_variants
~~~~~~~~~~~~~~~~~

.. literalinclude:: ../../tools/cmake/variant_handling/variant_handling-config.cmake
    :language: cmake
    :linenos:
    :lines: 1-44

display_variants
~~~~~~~~~~~~~~~~

.. literalinclude:: ../../tools/cmake/variant_handling/variant_handling-config.cmake
    :language: cmake
    :linenos:
    :lines: 210-227

write_variants_yaml
~~~~~~~~~~~~~~~~~~~

.. literalinclude:: ../../tools/cmake/variant_handling/variant_handling-config.cmake
    :language: cmake
    :linenos:
    :lines: 295-317

validate_variants
~~~~~~~~~~~~~~~~~

.. literalinclude:: ../../tools/cmake/variant_handling/variant_handling-config.cmake
    :language: cmake
    :linenos:
    :lines: 402-426

create_variant_feature
~~~~~~~~~~~~~~~~~~~~~~

.. literalinclude:: ../../tools/cmake/variant_handling/variant_handling-config.cmake
    :language: cmake
    :linenos:
    :lines: 524-565

set_variant
~~~~~~~~~~~

.. literalinclude:: ../../tools/cmake/variant_handling/variant_handling-config.cmake
    :language: cmake
    :linenos:
    :lines: 645-664

set_target_variants
~~~~~~~~~~~~~~~~~~~

.. literalinclude:: ../../tools/cmake/variant_handling/variant_handling-config.cmake
    :language: cmake
    :linenos:
    :lines: 748-765


.. _reuse_concept_component_implementation:

How Components Implement Variants
---------------------------------

Each component's build file (`CMakeLists.txt` or `BUILD`) uses the configured variant variables to adjust its behavior. This can involve:

-   **Compile-time defines:**

    -   CMake: `target_compile_definitions(target PRIVATE SOME_FLAG=1)`
    -   Bazel: `cc_library` with `copts`/`defines` or toolchain transformations

.. note::
    The compile-time definitions are automatically available and added to the compile steps in CMake based on their global nature or target association defined in the `create_variant_feature` call.

-   **Source selection:**

    -   CMake: `target_sources()` with generator expressions or `if`/`else`
    -   Bazel: `select()` on `srcs` using `config_setting` targets

-   **Runtime strings/configurations:**

    -   Generate a header or configuration file at configure time with chosen values.

`CMakeLists.txt` Usage Snippet example (Component)
--------------------------------------------------

Component authors access the configured variant value directly using the `VARIANT_<ModuleName>_<FeatureName>` variable.

.. code-block:: cmake

    get_filename_component(MODULE_NAME "${CMAKE_CURRENT_LIST_DIR}" NAME) # Derive module name if not explicitly set

    add_library(rbx_LoPwrHndlr OBJECT "")

    # Example 1: Source file selection based on DebugLevel
    if (VARIANT_${MODULE_NAME}_DebugLevel STREQUAL "debug")
        set(rbx_LoPwrHndlr_SRC_FILES
            ${CMAKE_CURRENT_LIST_DIR}/src/debug/rbx_LoPwrHndlr.c
        )
    else()
        set(rbx_LoPwrHndlr_SRC_FILES
            ${CMAKE_CURRENT_LIST_DIR}/src/release/rbx_LoPwrHndlr.c
        )
    endif()
    target_sources(rbx_LoPwrHndlr PRIVATE ${rbx_LoPwrHndlr_SRC_FILES})


Variant Placement and Function Tree Analysis
--------------------------------------------

The creation of variants should align with the functional decomposition derived from `Function Tree Analysis <ENG_Method_generic_003_>` method. This method provides a structured approach to breaking down system and domain functions.

A variant should ideally be introduced at a specific node (function) or leaf of the function tree. This means that any component corresponding to that node, or any node/leaf below it in the functional hierarchy, will have access to and be able to react to the configured variant variables. This approach ensures that configurable options are placed logically within the architecture and are available where needed.

For example, if a variant is defined for a "ProvideEngineSpeed" function, all sub-functions and the software components implementing them will implicitly have access to that variant's configuration. This allows for fine-grained control over specific functional areas.

Build Environment Integration (CMake)
-------------------------------------

The variant handling functionality for CMake is provided by a module, for example, named `variant_handling.cmake`. This module contains the `create_variant_feature` helper function used by component authors, as well as the `discover_variants`, `display_variants`, `validate_variants`, `set_variant`, `set_target_variants` and `write_variants_yaml` functions.

To integrate this system into the main project's `CMakeLists.txt`, typically at the top-level, the following steps are performed:

#.  **Include the variant handling module:** This makes the variant functions available. The exact path may vary per project setup.
#.  **Discover variants:** The `discover_variants()` function scans the project for all component `variants.cmake` files.
#.  **Include the active variants configuration:** This file (`active_variants.cmake` in the example below) contains the `set_variant` command that specify the chosen variant options for the current build.
#.  **Display variants:** `display_variants()` outputs a summary of all discovered and configured variants, which is useful for debugging and documentation.
#.  **Validate variants:** `validate_variants()` checks if the configured options are valid against the component definitions and raises errors for inconsistencies.
#.  **Write variants YAML:** `write_variants_yaml()` outputs a machine-readable summary of the active variants to a specified file, which can be consumed by other tools.

.. code-block:: cmake

    # In the project's top-level CMakeLists.txt

    # 1. Include the variant handling module (example path)
    # The actual path to variant_handling.cmake is project-specific.
    include(${REPOSITORY_MAIN_ENVIRONMENT}/cmake/cmake_modules/variant_handling.cmake)
    # Or when you use the pmt repository as part of the virtual monorepository
    # CMAKE_PREFIX_PATH must be set to <root_of_pmt_repo>/tools/cmake
    # find_package(variant_handling REQUIRED)

    # 2. Discover all variants defined across the project
    discover_variants(SEARCH_ROOT "${CMAKE_CURRENT_SOURCE_DIR}")

    # 3. Include the file that sets the chosen variant options (e.g., active_variants.cmake)
    # This file typically contains the `set_variant` or `set_target_variant` calls
    # important: the set_variant calls must be executed after discover_variants() so that the CMake Targets are known to the system and can be properly linked to the variants.
    include(active_variants.cmake)

    # 4. Target variants must be set after discover_variants() and before validate_variants() so that the validation component can check the configured variants against the discovered definitions.
    set_target_variants()

    # 5. Display a summary of all discovered variants and their current settings
    display_variants()

    # 6. Validate the configured variants against their definitions
    validate_variants()

    # 7. Output the active variants to a YAML file for external tools (e.g., CI, documentation generation)
    write_variants_yaml(FILEPATH "${CMAKE_CURRENT_BINARY_DIR}/active_variants.yaml")


Validation (Build Environment Component)
----------------------------------------

A validation component, typically part of the `variant_handling.cmake` module, ensures the integrity of variant selections:

-   It checks if a configured variant is actually defined by a component.
-   It verifies that the chosen option for a variant is among its `AVAILABLE_OPTIONS`.
-   On invalid input, it provides clear error messages, listing valid options, and will halt the build process early.
-   It can optionally enforce that all required variants are explicitly set or automatically apply default values where available.

Discoverability / Output Formats
--------------------------------

The variant handling module and collector tool provide outputs in various formats to aid discoverability and integration:

-   **Human-readable documentation:** For developers to easily understand available configurations (via `display_variants()`).
-   **Machine-readable artifacts:** JSON or YAML files for programmatic access by other tools or scripts (via `write_variants_yaml()`).
-   **CMake configuration:** The configured CMake variables are directly available for use in component `CMakeLists.txt` files.

Prefix & Variable Conventions
-----------------------------

-   **Configured Variant Variable:** `VARIANT_<ModuleName>_<FeatureName>`

    -   This is the CMake variable holding the user-selected option. Example: `VARIANT_LoPwrHndlr_DebugLevel` would hold `standard` or `debug`.

-   **Variant Definition Metadata:** The `create_variant_feature` helper and the collector use internal variables to store the properties of each variant. These are primarily for the collector's logic and not directly accessed by component build files.

     - `VARIANT_<ModuleName>_<FeatureName>_AVAILABLE_OPTIONS`
     - `VARIANT_<ModuleName>_<FeatureName>_DEFAULT`
     - `VARIANT_<ModuleName>_<FeatureName>_DESCRIPTION`

-   Use consistent capitalization and underscores for parseability.

Recommended Folder Structures
-----------------------------

.. code-block:: text

    repo-root/
    ├── components/
    │   ├── LoPwrHndlr/
    │   │   ├── CMakeLists.txt
    │   │   └── variants.cmake          <-- Defines component variants
    │   │   ├── src/
    │   │   ├── include/
    │   │   └── tests/
    |   └── global_variants.cmake       <-- Defines global variants. Note, that "global" is just a naming convention to indicate that the variants defined in this file are not specific to a single component but are intended to be used across multiple components. The actual name can be adjusted based on the project's organization and naming conventions.
    ├── active_variants.cmake           <-- User-defined or generated file for setting active variants
    ├── CMakeLists.txt                  <-- Main CMakeLists.txt, integrates the variant system

    pmt-root
    ├── tools/
    │   ├── cmake/
    │   │   └── variant_handling/       <-- CMake module for variant handling (create_variant_feature, discover_variants, etc.)
    └── ...

Bazel layout

.. code-block:: text

    repo-root/
    ├── components/
    │   ├── LoPwrHndlr/
    │   │   ├── BUILD
    │   │   └── variants.star           <-- Defines component variants
    │   │   └── src/
    └── .bazelrc                        <-- Or other global config to set Bazel config_settings (conceptual)

    pmt-root
    ├── tools/
    │   ├── bazel/
    │   │   └── variant_handling/       <-- Bazel module for variant handling (create_variant_feature, discover_variants, etc.)
    └── ...


PlantUML Placeholders
---------------------

Placeholders for diagrams to be created in step 2:

.. note::
   Placeholder PlantUML: component_dependency_tree.puml

.. note::
   Placeholder PlantUML: variant_aggregation_pipeline.puml

Operational Workflow
--------------------

**Author (Component Writer):**

-   Create a `variants.cmake` (or `variants.star`) file next to your component's build file.
-   Declare your component's configurable features and their properties (options, default, description) using the `create_variant_feature` helper function.
-   Implement the component's behavior in its `CMakeLists.txt` (or `BUILD` file), reacting to the selected variant values (e.g., `if (VARIANT_<ModuleName>_<FeatureName> STREQUAL "option_value")`).
-   Add unit tests to verify the component's functionality under different variant configurations.
-   Keep the `DESCRIPTION` fields in `variants.cmake` updated for clear documentation.

**Integrator / Consumer (Build System Engineer):**

-   In the top-level `CMakeLists.txt`, integrate the variant handling module and include the file defining active variants (e.g., `active_variants.cmake`).
-   Set active variants by modifying `active_variants.cmake` or through CMake cache variables (e.g., using `cmake -DVARIANT_rbx_LoPwrHndlr_DebugLevel=debug ...`).
-   Ensure the CI/build system runs the variant collector and validator early in the build process to detect configuration issues and provide discoverable documentation.

Benefits
--------

-   **Clear, Localized Variant Declarations:** Each component defines its own configurable points, improving modularity and understanding.
-   **Simplified Author Experience:** The `create_variant_feature` helper reduces boilerplate for component authors, making variant definition intuitive.
-   **Early Validation:** Prevents common configuration errors (typos, invalid options) at build time, saving development cycles.
-   **Enhanced Discoverability:** The collector tool automatically aggregates and exposes all available variant options, making it easy to understand and configure a complex system.
-   **Consistent Configuration:** Enforces a standardized approach to defining and consuming configurable options across the entire project.
-   **Cross-Build System Concept:** Provides a conceptual framework for both CMake and Bazel, with a fully implemented solution for CMake.

Risks & Trade-offs
------------------

-   **Convention and Tooling Reliance:** Effective adoption requires team discipline to follow conventions and relies on the collector/validator tools being consistently used and maintained.
-   **Initial Setup Effort:** Integrating the `variant_handling.cmake` module and setting up `active_variants.cmake` requires initial investment.
-   **Bazel Implementation Gap:** The Bazel concept is currently unimplemented, requiring manual porting or a separate development effort for Bazel projects.
-   **Migration Cost:** Existing components that don't follow this variant model will incur a cost to refactor their configuration mechanisms.

Variant Handling in reStructuredText Documentation
--------------------------------------------------

To enable conditional inclusion or exclusion of content in reStructuredText (RST) documentation based on active build variants, this concept integrates with Sphinx using two key extensions: `sphinxcontrib.ext.ifconfig <https://www.sphinx-doc.org/en/master/usage/extensions/ifconfig.html>`_ and a custom extension, `doc_variant`.

The Sphinx build process leverages the YAML file generated by CMake (e.g., `active_variants.yaml`) as its source of active variant values. This means that Sphinx should ideally be invoked after the CMake build process has generated this file. If wrapper scripts are used, the caller must ensure that the YAML output file is created *before* calling Sphinx.

**Integration Steps for Sphinx:**

#.  **Enable Extensions:** Both `sphinxcontrib.ext.ifconfig`_ and `doc_variant` must be enabled in your Sphinx project's `conf.py` file.

#.  **Provide Variant Configuration:** The `doc_variant` extension requires the path to the `active_variants.yaml` file. This can be specified in two ways:

    *   **Hardcoded in `conf.py`:**
        .. code-block:: python

            # conf.py
            app.config.variant_config_file = "../path/to/active_variants.yaml"

    *   **As a parameter during Sphinx build:**
        .. code-block:: bash

            sphinx-build -b html -D variant_config_file=/path/to/active_variants.yaml . _build/html

**Available Directives:**

Two directives become available for conditional content in RST files:

-   `.. ifconfig:: <python_expression>` (provided by `sphinxcontrib.ext.ifconfig`_)
-   `.. doc-ifconfig:: <python_expression>` (provided by `doc_variant`)

Both directives use a Python expression to decide whether a section of content (`ifconfig`) or an entire document (`doc-ifconfig`) should be included or excluded from the final output. The expression is evaluated against the variant values loaded from the YAML file.

**`.. ifconfig::` Directive:**

This directive conditionally includes or excludes a *section* of content within an RST file.

.. code-block:: rst

    .. ifconfig:: VARIANT_rbx_LoPwrHndlr_DebugLevel == "debug"

       This section describes debug-specific features.
       It will only appear in documentation builds where
       `VARIANT_rbx_LoPwrHndlr_DebugLevel` is set to "debug".

    .. ifconfig:: VARIANT_rbx_LoPwrHndlr_DebugLevel != "debug" and VARIANT_rbx_LoPwrHndlr_Mode == "foo"

       This section is for non-debug "foo" mode.

**`.. doc-ifconfig::` Directive:**

This directive is used at the top of an RST file to conditionally include or exclude the *entire document* from the Sphinx build output.

.. code-block:: rst

    .. doc-ifconfig:: VARIANT_rbx_LoPwrHndlr_CHIP_TYPE == "4BB"

    My 4BB Chip Type Specific Document
    ==================================

    This document contains detailed information relevant only for the 4BB chip type.

**Important Note on `doc-ifconfig` Processing:**

Even if the `doc-ifconfig` directive evaluates to `False` and decides that the document should not be included in the final HTML  output, the RST file itself is still *processed* by Sphinx. This is a deliberate design choice to allow the `doc-ifconfig` directive to execute and correctly mark the document for exclusion. This processing step also ensures that any internal needs or links within the excluded document are still registered with Sphinx's environment, maintaining data consistency.

.. _ENG_Method_generic_003: <URL to your Function Tree Analysis documentation>
