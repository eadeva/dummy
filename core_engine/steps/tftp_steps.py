"""TFTP upload/download and server management steps.
"""

import threading
from typing import Any, Dict

from xc_ce_utils import logger
from xc_ce_utils.core_engine.domain.exceptions import (
    AbortError,
    ExecutionStepError,
    RuntimeConfigError,
)
from xc_ce_utils.core_engine.domain.step_registry import StepRegistry
from xc_ce_utils.core_engine.steps.base import (
    BaseStepParams,
    ExecutionStep,
    StepEvaluationStatus,
    StepExecutionStatus,
)


class TFTPStepParams(BaseStepParams):
    pass
    model_config = {'extra': 'forbid'}


@StepRegistry.register(
    'tftp_upload',
    'tftp_download',
    'tftp_server_setup',
    'tftp_server_close',
)
class TFTPStep(ExecutionStep):
    params_model = TFTPStepParams

    """Unified TFTP step for file transfer and server management.

    Handles all TFTP actions: uploading files to a TFTP server, downloading
    files from a TFTP server, setting up a local TFTP server (in a daemon
    thread), and closing a running TFTP server.

    The concrete action is determined by the ``step_type`` field in the step
    configuration and dispatched internally.

    Config parameters (vary per action):
        server_ip (str):            IP address of the TFTP server.
        server_port (int):          Port of the TFTP server.
        remote_path (str):          Remote file path on the TFTP server
                                    (upload/download).
        local_path (str):           Local file path (upload/download).
        server_directory (str):     Root directory for the TFTP server
                                    (server_setup).
    """

    def __init__(self, name: str, config: Dict[str, Any], context: Any):
        super().__init__(name, config, context)

    # ------------------------------------------------------------------
    # Main dispatch
    # ------------------------------------------------------------------

    def execute(self) -> None:
        """Execute the configured TFTP action."""
        # Lazy import -- avoid pulling in tftpy at module load time
        from tftpy import TftpClient, TftpException, TftpServer

        try:
            self.pre_processing()

            action = self.config.get('step_type', '')
            params = self.config.get('params', {})

            if action == 'tftp_upload':
                self._tftp_upload(params, TftpClient, TftpException)
            elif action == 'tftp_download':
                self._tftp_download(params, TftpClient, TftpException)
            elif action == 'tftp_server_setup':
                self._tftp_server_setup(params, TftpServer, TftpException)
            elif action == 'tftp_server_close':
                self._tftp_server_close(params, TftpException)
            else:
                message = (
                    f'[{self.name}] Runtime configuration error: '
                    f"action '{action}' not recognized!"
                )
                logger.critical(message)
                self.conf_status = StepExecutionStatus.EXECUTE_FAILED
                raise RuntimeConfigError(message, phase=self.name)

        except (RuntimeConfigError, AbortError):
            self.execution_status = StepExecutionStatus.EXECUTE_FAILED
            raise
        except (ExecutionStepError, AbortError):
            self.execution_status = StepExecutionStatus.EXECUTE_FAILED
            raise
        except KeyboardInterrupt:
            message = f'[{self.name}] Interrupted by user'
            self.execution_status = StepExecutionStatus.USER_INTERRUPTED
            self.abort(AbortError(message, phase=self.name), abort_execution=True)
        except Exception as e:
            message = f'[{self.name}] Unknown exception: {e!s}'
            self.execution_status = StepExecutionStatus.EXECUTE_FAILED
            self.test_status = StepEvaluationStatus.FAILED
            self.abort(
                ExecutionStepError(message, phase=self.name),
                abort_execution=self.game_stopper,
            )

    # ------------------------------------------------------------------
    # Action implementations
    # ------------------------------------------------------------------

    def _tftp_upload(self, params: Dict[str, Any], TftpClient, TftpException) -> None:
        """Upload a file to a TFTP server.

        Creates a ``TftpClient`` connected to the configured server and
        uploads the local file to the specified remote path.
        """
        try:
            logger.info(f'[{self.name}] Uploading file to TFTP server')
            tftp_client = TftpClient(params['server_ip'], params['server_port'])
            tftp_client.upload(params['remote_path'], params['local_path'])
        except TftpException as e:
            message = f'[{self.name}] TFTP upload failed: {e!s}'
            raise ExecutionStepError(message, phase=self.name)
        except Exception as e:
            message = f'[{self.name}] TFTP upload failed: {e!s}'
            raise ExecutionStepError(message, phase=self.name)

        self.execution_status = StepExecutionStatus.EXECUTE_SUCCESS
        logger.success(f"[{self.name}] File uploaded to TFTP server: {params['remote_path']}")

    def _tftp_download(self, params: Dict[str, Any], TftpClient, TftpException) -> None:
        """Download a file from a TFTP server.

        Creates a ``TftpClient`` connected to the configured server and
        downloads the remote file to the specified local path.
        """
        try:
            logger.info(f'[{self.name}] Downloading file from TFTP server')
            tftp_client = TftpClient(params['server_ip'], params['server_port'])
            tftp_client.download(params['remote_path'], params['local_path'])
        except TftpException as e:
            message = f'[{self.name}] TFTP download failed: {e!s}'
            raise ExecutionStepError(message, phase=self.name)
        except Exception as e:
            message = f'[{self.name}] TFTP download failed: {e!s}'
            raise ExecutionStepError(message, phase=self.name)

        self.execution_status = StepExecutionStatus.EXECUTE_SUCCESS
        logger.success(f"[{self.name}] File downloaded from TFTP server: {params['remote_path']}")

    def _tftp_server_setup(self, params: Dict[str, Any], TftpServer, TftpException) -> None:
        """Set up a local TFTP server in a daemon thread.

        If a server is already running on the configured IP, it is reused.
        Otherwise a new ``TftpServer`` is created, started in a daemon
        thread, and stored in ``self.resources['tftp_servers']``.
        """
        try:
            logger.info(f'[{self.name}] Setting up TFTP server')

            if params['server_ip'] in self.resources['tftp_servers']:
                logger.warning(
                    f"[{self.name}] TFTP server on IP {params['server_ip']} "
                    f"already set-up. Already set-up instance will be used. "
                    f"Be aware: config differences were not checked"
                )
                self.add_to_report = False
                return
            else:
                tftp_server = TftpServer(params['server_directory'])
                server_port = params.get('server_port', 69)

                # Run the TFTP server in a separate daemon thread
                server_thread = threading.Thread(
                    target=tftp_server.listen,
                    args=(params['server_ip'], server_port),
                )
                server_thread.daemon = True
                server_thread.start()

                # Store the server and thread in resources
                self.resources['tftp_servers'][params['server_ip']] = {
                    'server': tftp_server,
                    'thread': server_thread,
                }
        except TftpException as e:
            message = f'[{self.name}] TFTP server setup failed: {e!s}'
            raise ExecutionStepError(message, phase=self.name)
        except Exception as e:
            message = f'[{self.name}] TFTP server setup failed: {e!s}'
            raise ExecutionStepError(message, phase=self.name)

        self.execution_status = StepExecutionStatus.EXECUTE_SUCCESS
        logger.success(
            f"[{self.name}] TFTP server set up at " f"{params['server_ip']}:{params['server_port']}"
        )

    def _tftp_server_close(self, params: Dict[str, Any], TftpException) -> None:
        """Close a running TFTP server and join its thread.

        Pops the server entry from ``self.resources['tftp_servers']``,
        stops the server, and waits for the daemon thread to finish.
        Raises ``RuntimeConfigError`` if no server is found for the
        configured IP.
        """
        try:
            logger.info(f'[{self.name}] Closing TFTP server')
            server_info = self.resources['tftp_servers'].pop(params['server_ip'], None)
            if server_info is None:
                message = f"[{self.name}] TFTP server not found: " f"{params['server_ip']}"
                raise RuntimeConfigError(message, phase=self.name)

            tftp_server = server_info['server']
            server_thread = server_info['thread']

            # Stop the TFTP server
            tftp_server.stop()

            # Wait for the thread to finish
            server_thread.join()
        except (RuntimeConfigError, AbortError):
            raise
        except TftpException as e:
            message = f'[{self.name}] TFTP server close failed: {e!s}'
            raise ExecutionStepError(message, phase=self.name)
        except Exception as e:
            message = f'[{self.name}] TFTP server close failed: {e!s}'
            raise ExecutionStepError(message, phase=self.name)

        self.execution_status = StepExecutionStatus.EXECUTE_SUCCESS
        logger.success(
            f"[{self.name}] TFTP server closed at " f"{params['server_ip']}:{params['server_port']}"
        )
