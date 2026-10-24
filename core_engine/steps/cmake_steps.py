"""CMake build steps: setup, build, and test.
"""

import os
import re
import shutil
from pathlib import Path
from typing import Any, Optional

from pydantic import Field

from xc_ce_utils import logger
from xc_ce_utils.core_engine.domain.step_registry import StepRegistry
from xc_ce_utils.core_engine.generators.definitions_generator import (
    DefinitionsGenerator,
)
from xc_ce_utils.core_engine.steps.base import BaseStepParams, WrappedStep
from xc_ce_utils.core_engine.wrappers.ccache_utils import (
    setup_ccache_environment,
)
from xc_ce_utils.global_modules.aux_helper import run_command
from xc_ce_utils.global_modules.file_empty_line_remover import (
    process_directory,
)


def _generate_native_definitions(context, output_dir: Path) -> Path:
    """Generate native CMake definitions file and return its path."""
    gen = DefinitionsGenerator(context)
    defs_file = gen.write_cmake(output_dir)
    logger.debug(f'Using native definitions from {defs_file}')
    return defs_file


class ProjectCMakeFileGenerationStepParams(BaseStepParams):
    pass
    model_config = {'extra': 'forbid'}


@StepRegistry.register('project_cmake_file_generation')
class ProjectCMakeFileGenerationStep(WrappedStep):
    params_model = ProjectCMakeFileGenerationStepParams

    """Generate only the project CMake definitions include file."""

    def execute(self) -> None:
        """Generate xc_ce_definitions.cmake in the active build folder."""
        defs_file = _generate_native_definitions(self.context, self.context.build_folder)
        logger.info(
            'Generated CMake definitions for variant '
            f"'{self.context.variant.get_variant_alias()}' at {defs_file}"
        )


class CMakeSetupStepParams(BaseStepParams):
    cmake_args: Optional[Any] = Field(default=None)
    conan_toolchain: Optional[Any] = Field(default=None)
    preset: Optional[Any] = Field(default=None)
    source_dir: Optional[Any] = Field(default=None)
    toolchain_file: Optional[Any] = Field(default=None)
    model_config = {'extra': 'forbid'}


@StepRegistry.register('cmake_set-up')
class CMakeSetupStep(WrappedStep):
    params_model = CMakeSetupStepParams

    """CMake setup build step."""

    WRAPPER_NAME = 'cmake'

    def execute(self) -> None:
        """Execute CMake setup."""
        rb_cmake_wrapper = self.get_wrapper()

        # Set up ccache environment if enabled
        use_ccache = False
        if self.context.ccache and self.context.ccache_dir:
            setup_ccache_environment(cache_dir=Path(self.context.ccache_dir))
            use_ccache = True

        if self.context.bin_folder.exists():
            # Removing bin dir
            shutil.rmtree(self.context.bin_folder)

        step_log_folder = self.get_step_log_folder()
        source_dir = self.context.repo_root
        if 'source_dir' in self.config:
            source_dir = (self.context.repo_root / self.config['source_dir']).resolve()

        cmake_wrapper = rb_cmake_wrapper(
            log_folder=step_log_folder,
            source_dir=source_dir,
            build_dir=self.context.build_folder,
            options=rb_cmake_wrapper.build_options(
                build_type=self.context.build_type,
                use_ccache=use_ccache,
            ),
        )

        if 'preset' in self.config:
            cmake_wrapper.run_preset(
                self.config['preset'],
                'build',
                extra_args=self.config['cmake_args'],
            )
        else:
            cmake_args = []
            if 'cmake_args' in self.config:
                cmake_args = self.config['cmake_args']

            if 'conan_toolchain' in self.config:
                # Conan path: use Conan-generated toolchain file
                cmake_args = [
                    f"-DCMAKE_TOOLCHAIN_FILE={str(self.context.build_folder).replace(os.sep, '/')}/conan_install/conan_toolchain.cmake",
                    *cmake_args,
                ]
            else:
                # Native path: generate xc_ce_definitions.cmake
                defs_file = _generate_native_definitions(self.context, self.context.build_folder)
                cmake_args = [
                    f"-DCMAKE_PROJECT_INCLUDE={str(defs_file).replace(os.sep, '/')}",
                    *cmake_args,
                ]

            if 'toolchain_file' in self.config:
                cmake_args = [
                    f"-DCMAKE_TOOLCHAIN_FILE={self.config['toolchain_file']}",
                    *cmake_args,
                ]

            cmake_wrapper.setup(cmake_args)


class CMakeExecutionStepParams(BaseStepParams):
    preset: Optional[Any] = Field(default=None)
    model_config = {'extra': 'forbid'}


@StepRegistry.register('cmake_build')
class CMakeExecutionStep(WrappedStep):
    params_model = CMakeExecutionStepParams

    """CMake build step."""

    WRAPPER_NAME = 'cmake'

    def execute(self) -> None:
        """Execute CMake build."""
        rb_cmake_wrapper = self.get_wrapper()

        # Check for ccache option in variant build options
        use_ccache = None
        ccache_dir = None
        build_options = self.context.get_variant().get_build_options()
        if 'use_ccache' in build_options:
            use_ccache = build_options['use_ccache']
        if 'ccache_dir' in build_options:
            ccache_dir = build_options['ccache_dir']

        # Set up ccache environment if enabled
        if use_ccache and ccache_dir:
            setup_ccache_environment(cache_dir=Path(ccache_dir))

        step_log_folder = self.get_step_log_folder()
        cmake_wrapper = rb_cmake_wrapper(
            log_folder=step_log_folder,
            build_dir=self.context.build_folder,
            options=rb_cmake_wrapper.build_options(
                build_type=self.context.build_type,
                use_ccache=use_ccache,
            ),
        )

        if 'preset' in self.config:
            cmake_wrapper.run_preset(self.config['preset'], 'build')
        elif self.context.single_file:
            logger.info("Single-file mode: building CMake target 'compile_single_file'")
            cmake_wrapper.build(target='compile_single_file')
        else:
            cmake_wrapper.build()

        # Run empty line remover on .i files in dev or single-file mode
        if self.context.dev_mode or self.context.single_file:
            build_folder = self.context.get_build_folder()
            logger.info(f' Running empty line remover on .i files in {build_folder}')
            process_directory(build_folder, ['.i'])
            # Copy processed .i files to _reports
            reports_folder = self.get_step_reports_folder()
            for i_file in build_folder.rglob('*.i'):
                dest_file = reports_folder.parent / 'devmode' / i_file.name
                dest_file.parent.mkdir(parents=True, exist_ok=True)
                i_file.replace(dest_file)

            # Keep project-specific .inc_tree.txt artifacts in devmode reports.
            for i_file in build_folder.rglob('*.inc_tree.txt'):
                dest_file = reports_folder.parent / 'devmode' / i_file.name
                dest_file.parent.mkdir(parents=True, exist_ok=True)
                dest_file.write_text(
                    f'// Original file path: {i_file.resolve()}\n\n'
                    + i_file.read_text(encoding='utf-8'),
                    encoding='utf-8',
                )
                i_file.unlink()


class CTestStepParams(BaseStepParams):
    emit_ctest_junit: Optional[Any] = Field(default=None)
    emit_gtest_xml_per_binary: Optional[Any] = Field(default=None)
    gtest_binary_glob: Optional[Any] = Field(default=None)
    gtest_xml_subdir: Optional[Any] = Field(default=None)
    preset: Optional[Any] = Field(default=None)
    model_config = {'extra': 'forbid'}


@StepRegistry.register('ctest')
class CTestStep(WrappedStep):
    params_model = CTestStepParams

    """CTest build step."""

    WRAPPER_NAME = 'cmake'

    @staticmethod
    def _discover_gtest_binaries(build_dir: Path, binary_glob: str) -> list[Path]:
        binaries = []
        for path in sorted(build_dir.rglob(binary_glob)):
            if not path.is_file():
                continue
            if os.name == 'nt':
                if path.suffix.lower() != '.exe':
                    continue
            elif not os.access(path, os.X_OK):
                continue
            binaries.append(path)
        return binaries

    @staticmethod
    def _safe_log_name(name: str) -> str:
        return re.sub(r'[^A-Za-z0-9._-]+', '_', name)

    def _emit_gtest_xml_per_binary(
        self,
        build_dir: Path,
        reports_folder: Path,
        binary_glob: str,
        xml_subdir: str,
    ) -> None:
        binaries = self._discover_gtest_binaries(build_dir, binary_glob)
        if not binaries:
            logger.info(
                f"[{self.name}] No GTest binaries found for pattern '{binary_glob}' in {build_dir}"
            )
            return

        xml_root = reports_folder / xml_subdir
        xml_root.mkdir(parents=True, exist_ok=True)

        logger.info(
            f'[{self.name}] Generating per-binary GTest XML reports for {len(binaries)} binary/binaries'
        )

        log_folder = self.get_step_log_folder()
        for binary in binaries:
            binary_name = binary.name
            xml_target = xml_root / f'{binary_name}_report.xml'
            logger.info(f'[{self.name}] Running {binary_name} with GTest XML output: {xml_target}')

            try:
                run_command(
                    [
                        str(binary),
                        f'--gtest_output=xml:{xml_target}',
                    ],
                    log_file=log_folder / f'gtest_xml_{self._safe_log_name(binary_name)}.log',
                    cwd=str(build_dir),
                )
            except Exception as exc:
                # Continue on individual test binary failures; CTest remains the
                # authoritative verdict for the step.
                logger.warning(
                    f'[{self.name}] GTest XML generation failed for {binary_name}: {exc}'
                )

    def execute(self) -> None:
        """Execute CTest."""
        if not self.context.cmake_wrapper:
            rb_cmake_wrapper = self.get_wrapper()
            step_log_folder = self.get_step_log_folder()
            self.context.cmake_wrapper = rb_cmake_wrapper(
                log_folder=step_log_folder,
                build_dir=self.context.get_build_folder(),
                options=rb_cmake_wrapper.build_options(
                    build_type=self.context.build_type,
                ),
            )

        preset = self.config.get('preset', None)
        if preset:
            self.context.cmake_wrapper.run_preset(preset, 'test')
            return

        build_conf = getattr(self.context, 'build_conf', {}) or {}
        if 'PRESET' in build_conf:
            self.context.cmake_wrapper.run_preset(build_conf['PRESET'], 'test')
            return

        reports_folder = self.get_step_reports_folder()
        reports_folder.mkdir(parents=True, exist_ok=True)

        emit_gtest_xml_per_binary = self.config.get('emit_gtest_xml_per_binary', False)

        if emit_gtest_xml_per_binary:
            binary_glob = self.config.get('gtest_binary_glob', 'UT_*')
            xml_subdir = self.config.get('gtest_xml_subdir', 'gtest_individual')
            self._emit_gtest_xml_per_binary(
                build_dir=self.context.get_build_folder(),
                reports_folder=reports_folder,
                binary_glob=binary_glob,
                xml_subdir=xml_subdir,
            )

        junit_report = reports_folder / 'ctest-junit.xml'
        emit_ctest_junit = self.config.get('emit_ctest_junit', True)
        if emit_gtest_xml_per_binary and 'emit_ctest_junit' not in self.config:
            # Default to off in per-binary GTest XML mode to avoid duplicate
            # ingestion of the same tests from two XML sources.
            emit_ctest_junit = False

        if not emit_ctest_junit and junit_report.exists():
            junit_report.unlink()

        self.context.cmake_wrapper.test(output_junit=junit_report if emit_ctest_junit else None)
