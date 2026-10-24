"""Adapter for shared execution-resource lifecycle management.

Extracted from the former ``adapters/execution/infra.py`` monolith. Manages
the shared resource pool (threads, Trace32, SSH, COM ports, Voltcraft, TFTP,
WinIDEA, CANoe) acquired during action execution and released at the end of
the run.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


def initialize_resource_pool(resources: dict[str, Any]) -> None:
    """Initialize the shared resource pool with standard group keys."""
    for key in (
        'lauterbachs',
        'artifactory_downloaders',
        'voltcrafts',
        'ssh_connections',
        'com_ports',
        'timers',
        'threads',
        'log_files',
        'tftp_servers',
        'winideas',
        'canoes',
    ):
        resources.setdefault(key, {})


def release_thread_resource(
    *,
    thread_id: Any,
    thread_info: Any,
    log_warning: Callable[[str], None],
    log_debug: Callable[[str], None],
) -> None:
    """Release one thread resource with cooperative stop and timeout."""
    stop_signal = thread_info.get('stop_signal')
    if stop_signal is not None:
        stop_signal.set()

    thread = thread_info.get('thread')
    if thread is None:
        return

    thread.join(timeout=5)
    if thread.is_alive():
        log_warning(f'[RELEASE] Thread {thread_id} did not stop within timeout')
    else:
        log_debug(f'[RELEASE] Thread {thread_id} stopped')


def release_lauterbach_resource(
    *,
    t32_id: Any,
    t32: Any,
    log_debug: Callable[[str], None],
) -> None:
    """Release one Trace32 resource respecting keep-open mode."""
    if getattr(t32, 'keep_open', False):
        log_debug(f'[RELEASE] Trace32 {t32_id} - keep_open set, skipping close')
        return
    t32.close()
    log_debug(f'[RELEASE] Trace32 {t32_id} closed')


def release_ssh_resource(
    *,
    ssh_ip: Any,
    ssh_info: Any,
    log_debug: Callable[[str], None],
) -> None:
    """Release one SSH connection resource when present."""
    ssh_connection = ssh_info.get('ssh_connection')
    if ssh_connection is None:
        return
    ssh_connection.close()
    log_debug(f'[RELEASE] SSH {ssh_ip} closed')


def release_com_resource(
    *,
    port_number: Any,
    port: Any,
    log_debug: Callable[[str], None],
) -> None:
    """Release one COM-port resource."""
    port.close_port()
    log_debug(f'[RELEASE] COM{port_number} closed')


def release_voltcraft_resource(
    *,
    vc_id: Any,
    power_supply: Any,
    log_debug: Callable[[str], None],
) -> None:
    """Release one Voltcraft resource by turning off output."""
    power_supply.turn_off()
    log_debug(f'[RELEASE] Voltcraft {vc_id} turned off')


def release_tftp_resource(
    *,
    tftp_ip: Any,
    tftp_info: Any,
    log_debug: Callable[[str], None],
) -> None:
    """Release one TFTP server resource and stop associated thread."""
    server = tftp_info.get('server')
    if server is not None:
        server.stop()

    thread = tftp_info.get('thread')
    if thread is not None:
        thread.join(timeout=5)

    log_debug(f'[RELEASE] TFTP server {tftp_ip} stopped')


def release_winidea_resource(
    *,
    wi_id: Any,
    wi: Any,
    log_debug: Callable[[str], None],
) -> None:
    """Release one WinIDEA resource respecting keep-open mode."""
    if getattr(wi, 'keep_open', False):
        log_debug(
            f'[RELEASE] WinIDEA {wi_id} - keep_open set, bringing to front and detaching'
        )
        wi.bring_to_front()
        wi.disconnect_keep()
        return
    wi.disconnect()
    log_debug(f'[RELEASE] WinIDEA {wi_id} disconnected')


def release_canoe_resource(
    *,
    canoe_id: Any,
    canoe: Any,
    log_debug: Callable[[str], None],
) -> None:
    """Release one CANoe resource respecting keep-open mode."""
    if getattr(canoe, 'keep_open', False):
        log_debug(f'[RELEASE] CANoe {canoe_id} - keep_open set, skipping close')
        return
    canoe.quit(save_cfg=False)
    log_debug(f'[RELEASE] CANoe {canoe_id} closed')


@dataclass(frozen=True)
class ResourceReleaseAdapter:
    """Dependency boundary for shared-resource release orchestration."""

    get_resources: Callable[[], dict[str, Any]]
    log_debug: Callable[[str], None]
    resource_release_specs: Callable[
        [],
        tuple[tuple[str, str, Callable[[Any, Any], None]], ...],
    ]
    release_resource_group: Callable[
        [str, str, Callable[[Any, Any], None]], None
    ]


@dataclass(frozen=True)
class ResourceReleaseCallbacks:
    """Callback payload for resource-release spec construction."""

    release_thread_resource: Callable[[Any, Any], None]
    release_lauterbach_resource: Callable[[Any, Any], None]
    release_ssh_resource: Callable[[Any, Any], None]
    release_com_resource: Callable[[Any, Any], None]
    release_voltcraft_resource: Callable[[Any, Any], None]
    release_tftp_resource: Callable[[Any, Any], None]
    release_winidea_resource: Callable[[Any, Any], None]
    release_canoe_resource: Callable[[Any, Any], None]


@dataclass(frozen=True)
class ResourceGroupReleaseInput:
    """Input payload for releasing one resource group."""

    resources: dict[str, Any]
    resource_key: str
    label: str
    releaser: Callable[[Any, Any], None]


@dataclass(frozen=True)
class ResourceReleaseAdapterFactoryInput:
    """Input payload for assembling ResourceReleaseAdapter."""

    resources: dict[str, Any]
    callbacks: ResourceReleaseCallbacks
    log_debug: Callable[[str], None]
    log_warning: Callable[[str], None]


def create_standard_resource_release_callbacks(
    *,
    log_debug: Callable[[str], None],
    log_warning: Callable[[str], None],
) -> ResourceReleaseCallbacks:
    """Create callbacks wired to adapter-side resource release functions."""
    return ResourceReleaseCallbacks(
        release_thread_resource=lambda thread_id,
        thread_info: release_thread_resource(
            thread_id=thread_id,
            thread_info=thread_info,
            log_warning=log_warning,
            log_debug=log_debug,
        ),
        release_lauterbach_resource=lambda t32_id,
        t32: release_lauterbach_resource(
            t32_id=t32_id,
            t32=t32,
            log_debug=log_debug,
        ),
        release_ssh_resource=lambda ssh_ip, ssh_info: release_ssh_resource(
            ssh_ip=ssh_ip,
            ssh_info=ssh_info,
            log_debug=log_debug,
        ),
        release_com_resource=lambda port_number, port: release_com_resource(
            port_number=port_number,
            port=port,
            log_debug=log_debug,
        ),
        release_voltcraft_resource=lambda vc_id,
        power_supply: release_voltcraft_resource(
            vc_id=vc_id,
            power_supply=power_supply,
            log_debug=log_debug,
        ),
        release_tftp_resource=lambda tftp_ip, tftp_info: release_tftp_resource(
            tftp_ip=tftp_ip,
            tftp_info=tftp_info,
            log_debug=log_debug,
        ),
        release_winidea_resource=lambda wi_id, wi: release_winidea_resource(
            wi_id=wi_id,
            wi=wi,
            log_debug=log_debug,
        ),
        release_canoe_resource=lambda canoe_id, canoe: release_canoe_resource(
            canoe_id=canoe_id,
            canoe=canoe,
            log_debug=log_debug,
        ),
    )


def create_resource_release_specs(
    *,
    callbacks: ResourceReleaseCallbacks,
) -> tuple[tuple[str, str, Callable[[Any, Any], None]], ...]:
    """Return ordered resource-release definitions for cleanup phase."""
    return (
        (
            'threads',
            'thread',
            callbacks.release_thread_resource,
        ),
        (
            'lauterbachs',
            'Trace32',
            callbacks.release_lauterbach_resource,
        ),
        (
            'ssh_connections',
            'SSH',
            callbacks.release_ssh_resource,
        ),
        (
            'com_ports',
            'COM',
            callbacks.release_com_resource,
        ),
        (
            'voltcrafts',
            'Voltcraft',
            callbacks.release_voltcraft_resource,
        ),
        (
            'tftp_servers',
            'TFTP server',
            callbacks.release_tftp_resource,
        ),
        (
            'winideas',
            'WinIDEA',
            callbacks.release_winidea_resource,
        ),
        (
            'canoes',
            'CANoe',
            callbacks.release_canoe_resource,
        ),
    )


def release_resource_group_entries(
    *,
    payload: ResourceGroupReleaseInput,
    log_warning: Callable[[str], None],
) -> None:
    """Release all entries from one resource group and reset it."""
    for resource_id, resource in list(
        payload.resources.get(payload.resource_key, {}).items()
    ):
        try:
            payload.releaser(resource_id, resource)
        except Exception as exc:
            log_warning(
                f'[RELEASE] Error releasing {payload.label} {resource_id}: {exc}'
            )
    payload.resources[payload.resource_key] = {}


def create_resource_release_adapter(
    *,
    payload: ResourceReleaseAdapterFactoryInput,
) -> ResourceReleaseAdapter:
    """Create ResourceReleaseAdapter from common release dependencies."""
    return ResourceReleaseAdapter(
        get_resources=lambda: payload.resources,
        log_debug=payload.log_debug,
        resource_release_specs=lambda: create_resource_release_specs(
            callbacks=payload.callbacks
        ),
        release_resource_group=lambda resource_key,
        label,
        releaser: release_resource_group_entries(
            payload=ResourceGroupReleaseInput(
                resources=payload.resources,
                resource_key=resource_key,
                label=label,
                releaser=releaser,
            ),
            log_warning=payload.log_warning,
        ),
    )


def release_all_resources(adapter: ResourceReleaseAdapter) -> None:
    """Release all registered resources through adapter boundary."""
    if not adapter.get_resources():
        return

    adapter.log_debug('Releasing shared resources...')
    for resource_key, label, releaser in adapter.resource_release_specs():
        adapter.release_resource_group(resource_key, label, releaser)
