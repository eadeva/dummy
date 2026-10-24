"""Execution orchestration collaborators.

This package decomposes the former monolithic ``execution_engine.py`` into
focused collaborators composed by :class:`ExecutionAction`
(``action_orchestrator.py``):

- ``step_executor``: step/execution-set creation and execution dispatch.
- ``error_recovery``: recovery-strategy classification and retry/abort logic.
- ``tool_requires_installer``: platform tool-requires installation.
- ``debug_artifact_uploader``: CI debug-artifact upload on failure.
"""
