"""TACO (Test as Code Orchestration) steps.

The steps call the ``taco`` CLI of the project's own TACO adapter (e.g.
``tools/taco_project``, installed by the TACO setup phase) - runners, variants
and test selection rules stay in the project repository.
"""

import glob
import json
import os
import re
import shutil
import subprocess
import sys
from collections import Counter
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

from pydantic import Field

from xc_ce_utils import logger
from xc_ce_utils.core_engine.domain.exceptions import ExecutionStepError
from xc_ce_utils.core_engine.domain.step_registry import StepRegistry
from xc_ce_utils.core_engine.steps.base import (
    BaseStepParams,
    ExecutionStep,
    StepEvaluationStatus,
    StepExecutionStatus,
)
from xc_ce_utils.global_modules.aux_helper import run_command

SUMMARY_FILE_NAME = 'taco_summary.json'
DEFAULT_RESULTS_DIR_NAME = 'taco_results'
ECU_ARTIFACTS_FILE_NAME = 'ecu_artifacts.json'
# Exit code of the adapter runners when selected test cases failed or were not executed.
TESTS_NOT_PASSED_RETURN_CODE = 1


@contextmanager
def external_python_env() -> Iterator[Optional[Dict[str, str]]]:
    """Yield the environment for running another Python program (``None``: inherit).

    A frozen (PyInstaller) xc-ce-utils puts its bundle on the DLL search path
    (``SetDllDirectory``), which child processes inherit: the project's Python then
    loads the bundled DLLs and crashes (0xC0000005). The DLL directory is reset for the
    call, and environment variables pointing into the bundle are dropped.
    """
    bundle = getattr(sys, '_MEIPASS', None)
    if not getattr(sys, 'frozen', False) or not bundle:
        yield None
        return
    bundle_norm = os.path.normcase(os.path.abspath(bundle))
    env = {}
    for key, value in os.environ.items():
        if key.startswith(('_PYI_', '_MEI')):
            continue
        if key in {'PYTHONPATH', 'PYTHONHOME'}:
            entries = [
                entry
                for entry in value.split(os.pathsep)
                if entry and not os.path.normcase(os.path.abspath(entry)).startswith(bundle_norm)
            ]
            if entries:
                env[key] = os.pathsep.join(entries)
            continue
        env[key] = value
    kernel32 = None
    if os.name == 'nt':
        import ctypes  # noqa: PLC0415

        kernel32 = ctypes.windll.kernel32
        kernel32.SetDllDirectoryW(None)
    try:
        yield env
    finally:
        if kernel32 is not None:
            kernel32.SetDllDirectoryW(bundle)


def find_taco_cli() -> Path:
    """Return the ``taco`` CLI of the running Python environment."""
    # TODO: ship the taco CLI with the frozen executable; projects using it have no venv.
    scripts_dir = Path(sys.executable).parent
    for name in ('taco.exe', 'taco'):
        if (scripts_dir / name).is_file():
            return scripts_dir / name
    on_path = shutil.which('taco')
    if on_path:
        return Path(on_path)
    raise ExecutionStepError(
        "The TACO CLI 'taco' is not installed. Configure TACO.adapter_path in main_conf.yml "
        'so the setup installs the project adapter (e.g. tools/taco_project).'
    )


def load_result_verdicts(result_file: Path) -> Dict[str, str]:
    """Return ``{test case id: verdict}`` of a TACO result JSON (empty if it is none)."""
    try:
        data = json.loads(result_file.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {}
    results = data.get('results') if isinstance(data, dict) else None
    if not isinstance(results, dict):
        return {}
    verdicts = {}
    for test_id, entry in results.items():
        if not isinstance(entry, dict):
            continue
        result = entry.get('result') if isinstance(entry.get('result'), dict) else entry
        verdict = result.get('verdict')
        if verdict:
            verdicts[str(test_id)] = str(verdict)
    return verdicts


def collect_results(source_dir: Path, target_dir: Path, prefix: str) -> List[Path]:
    """Copy TACO result JSONs found below ``source_dir`` flat into ``target_dir``.

    Earlier copies with the same ``prefix`` are replaced, so the target holds the
    latest results of each test selection (the layout ``verdict_overlay`` reads).
    """
    target_dir.mkdir(parents=True, exist_ok=True)
    for old in target_dir.glob(f'{prefix}__*.json'):
        old.unlink()
    copied = []
    for result_file in sorted(source_dir.rglob('*.json')):
        if result_file.name == SUMMARY_FILE_NAME or not load_result_verdicts(result_file):
            continue
        flat_name = '_'.join(result_file.relative_to(source_dir).parts)
        target = target_dir / f'{prefix}__{flat_name}'
        shutil.copyfile(result_file, target)
        copied.append(target)
    return copied


def collect_ecu_artifacts(repo_root: Path, patterns: List[str]) -> List[Dict[str, Any]]:
    """Return one entry per file matching the glob ``patterns`` (relative to ``repo_root``)."""
    artifacts: List[Dict[str, Any]] = []
    seen = set()
    for pattern in patterns:
        for match in sorted(glob.glob(str(repo_root / pattern), recursive=True)):
            path = Path(match).resolve()
            if not path.is_file() or path in seen:
                continue
            seen.add(path)
            artifacts.append(
                {
                    'name': path.name,
                    'type': path.suffix.lstrip('.').lower(),
                    'path': str(path),
                    'size_bytes': path.stat().st_size,
                    'pattern': pattern,
                }
            )
    return artifacts


def build_summary(selection: str, variant: str, result_files: List[Path]) -> Dict[str, Any]:
    """Merge the verdicts of all result files into the step summary."""
    verdicts: Dict[str, str] = {}
    for result_file in result_files:
        verdicts.update(load_result_verdicts(result_file))
    return {
        'selection': selection,
        'variant': variant,
        'counts': dict(Counter(verdicts.values())),
        'results': [
            {'test_case': test_id, 'verdict': verdict}
            for test_id, verdict in sorted(verdicts.items())
        ],
    }


class TacoStepParams(BaseStepParams):
    test_list: Optional[Any] = Field(default=None)
    variant: Optional[Any] = Field(default=None)
    output: Optional[Any] = Field(default=None)
    needs_file: Optional[Any] = Field(default=None)
    model_config = {'extra': 'forbid'}


class _TacoStep(ExecutionStep):
    """Run one ``taco`` command from the repository root."""

    command = ''
    accepted_return_codes = (0,)

    def validate(self) -> None:
        super().validate()
        if not self.config.get('test_list'):
            raise ExecutionStepError(
                f"[{self.name}] '{self.command}' requires 'test_list'", phase=self.name
            )

    @property
    def repo_root(self) -> Path:
        return Path(self.context.repo_root)

    @property
    def test_list(self) -> Path:
        return self.repo_root / self.config['test_list']

    @property
    def variant(self) -> str:
        return str(self.config.get('variant') or self.context.variant.get_variant_alias())

    @property
    def needs_file(self) -> Optional[Path]:
        """Configured needs.json, else the one of a ``builder: needs`` docascode step here."""
        configured = self.config.get('needs_file')
        if configured:
            return self.repo_root / configured
        action_needs = Path(self.context.get_build_folder()) / 'needs' / 'needs.json'
        return action_needs if action_needs.is_file() else None

    def command_args(self) -> List[str]:
        raise NotImplementedError

    def after_command(self) -> None:
        """Hook run after the command, also when it failed."""

    def evaluate(self, return_code: int) -> Optional[str]:
        """Return the failure message for ``return_code``, or ``None`` if the step passed."""
        if return_code == 0:
            return None
        return f'[{self.name}] taco {self.command} failed with return code {return_code}'

    def _fail(self, error: ExecutionStepError) -> None:
        self.execution_status = StepExecutionStatus.EXECUTE_FAILED
        self.test_status = StepEvaluationStatus.FAILED
        self.abort(error, abort_execution=self.game_stopper)

    def execute(self) -> None:
        self.pre_processing()
        try:
            taco = find_taco_cli()
        except ExecutionStepError as exc:
            self._fail(exc)
            return
        cmd = [str(taco), self.command, '-tl', str(self.test_list), '-v', self.variant]
        if self.needs_file is not None:
            cmd += ['--needs-file', str(self.needs_file)]
        cmd += self.command_args()
        logger.info(f'[{self.name}] Running: {" ".join(cmd)}')
        try:
            with external_python_env() as env:
                status = run_command(
                    cmd,
                    cwd=self.repo_root,
                    return_success_codes=list(self.accepted_return_codes),
                    env=env,
                )
            match = re.fullmatch(r'Success: (\d+)', str(status))
            return_code = int(match.group(1)) if match else 0
        except subprocess.CalledProcessError as exc:
            return_code = exc.returncode
        self.after_command()
        failure = self.evaluate(return_code)
        if failure is None:
            self.execution_status = StepExecutionStatus.EXECUTE_SUCCESS
            self.test_status = StepEvaluationStatus.PASSED
            logger.success(f'[{self.name}] taco {self.command} finished successfully')
            return
        self._fail(ExecutionStepError(failure, phase=self.name))


@StepRegistry.register('taco_filter', category='Testing')
class TacoFilterStep(_TacoStep):
    """Resolve a ``.tl.yaml`` test selection to its test case IDs (``taco filter``).

    Config parameters:
        test_list (str): Test selection file, relative to the repository root.
        variant (str):   TACO variant; defaults to the variant alias.
        output (str):    Result YAML; defaults to ``<step reports>/<selection>.yaml``.
    """

    params_model = TacoStepParams
    command = 'filter'

    def command_args(self) -> List[str]:
        output = self.config.get('output')
        if output:
            output_file = self.repo_root / output
        else:
            output_file = (
                self.get_step_reports_folder() / f'{self.test_list.name.split(".")[0]}.yaml'
            )
        output_file.parent.mkdir(parents=True, exist_ok=True)
        return ['--output', str(output_file)]


class TacoRunStepParams(TacoStepParams):
    taco_results_dir: Optional[Any] = Field(default=None)
    model_config = {'extra': 'forbid'}


class _TacoRunStep(_TacoStep):
    """Execute a test selection through an adapter runner and collect its TACO results."""

    output_option = '-o'
    accepted_return_codes = (0, TESTS_NOT_PASSED_RETURN_CODE)
    summary: Optional[Dict[str, Any]] = None

    @property
    def output_dir(self) -> Path:
        output = self.config.get('output')
        return self.repo_root / output if output else self.get_step_reports_folder()

    def runner_args(self) -> List[str]:
        return []

    def command_args(self) -> List[str]:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        return [self.output_option, str(self.output_dir), *self.runner_args()]

    def after_command(self) -> None:
        configured = self.config.get('taco_results_dir')
        results_dir = (
            self.repo_root / configured
            if configured
            else Path(self.context.reports_folder).parent / DEFAULT_RESULTS_DIR_NAME
        )
        selection = self.test_list.name.split('.')[0]
        copied = collect_results(self.output_dir, results_dir, selection)
        summary = build_summary(selection, self.variant, copied)
        self.summary = summary
        (self.output_dir / SUMMARY_FILE_NAME).write_text(
            json.dumps(summary, indent=2), encoding='utf-8'
        )
        logger.info(
            f'[{self.name}] {len(summary["results"])} verdict(s) {summary["counts"]} '
            f'collected in {results_dir}'
        )

    def evaluate(self, return_code: int) -> Optional[str]:
        if return_code != TESTS_NOT_PASSED_RETURN_CODE or not (self.summary or {}).get('results'):
            return super().evaluate(return_code)
        not_passed = {
            verdict: count
            for verdict, count in sorted(self.summary['counts'].items())
            if verdict.lower() != 'passed'
        }
        return (
            f'[{self.name}] {sum(not_passed.values())} of {len(self.summary["results"])} '
            f'selected test case(s) did not pass: {not_passed}'
        )


class TacoCTestStepParams(TacoRunStepParams):
    build_dir: Optional[Any] = Field(default=None)
    model_config = {'extra': 'forbid'}


@StepRegistry.register('taco_ctest', category='Testing')
class TacoCTestStep(_TacoRunStep):
    """Run the GoogleTest cases of a test selection through CTest (``taco unit-tests``).

    The adapter checks the CTest discovery (``ctest -N``) and runs only the
    selected tests (``ctest -R``); unknown selected tests are NOT EXECUTED.

    Config parameters:
        test_list (str):        Test selection file, relative to the repository root.
        variant (str):          TACO variant; defaults to the variant alias.
        output (str):           TACO output folder; defaults to the step reports folder.
        build_dir (str):        CTest build directory; defaults to the action build folder.
        taco_results_dir (str): Folder collecting the TACO result JSONs for the docs
                                (``docascode`` ``taco_results_dir``); defaults to
                                ``_reports/<variant>/taco_results``.
    """

    params_model = TacoCTestStepParams
    command = 'unit-tests'

    def runner_args(self) -> List[str]:
        configured = self.config.get('build_dir')
        build_dir = self.repo_root / configured if configured else self.context.get_build_folder()
        return ['--build-dir', str(build_dir)]


class TacoRobotFrameworkStepParams(TacoRunStepParams):
    ecu_artifacts: Optional[Any] = Field(default=None)
    model_config = {'extra': 'forbid'}


@StepRegistry.register('taco_robotfw', category='Testing')
class TacoRobotFrameworkStep(_TacoRunStep):
    """Run the Robot Framework test cases of a test selection (``taco robotfw``).

    Config parameters:
        test_list (str):        Test selection file, relative to the repository root.
        variant (str):          TACO variant; defaults to the variant alias.
        output (str):           Robot/TACO output folder; defaults to the step reports folder.
        ecu_artifacts (str | list[str]): Glob patterns (relative to the repository root) of
                                the ECU artifacts. They are compiled into one JSON
                                (``ecu_artifacts.json`` in the output folder) and passed
                                to the adapter with ``--ecu-artifacts``.
        taco_results_dir (str): Folder collecting the TACO result JSONs for the docs;
                                defaults to ``_reports/<variant>/taco_results``.
    """

    params_model = TacoRobotFrameworkStepParams
    command = 'robotfw'
    output_option = '--output'

    def runner_args(self) -> List[str]:
        patterns = self.config.get('ecu_artifacts')
        if not patterns:
            return []
        if isinstance(patterns, str):
            patterns = [patterns]
        artifacts = collect_ecu_artifacts(self.repo_root, patterns)
        for pattern in patterns:
            if not any(artifact['pattern'] == pattern for artifact in artifacts):
                logger.warning(f'[{self.name}] No ECU artifact matches {pattern!r}')
        ecu_file = self.output_dir / ECU_ARTIFACTS_FILE_NAME
        ecu_file.write_text(
            json.dumps({'variant': self.variant, 'artifacts': artifacts}, indent=2),
            encoding='utf-8',
        )
        logger.info(f'[{self.name}] {len(artifacts)} ECU artifact(s) listed in {ecu_file}')
        return ['--ecu-artifacts', str(ecu_file)]
