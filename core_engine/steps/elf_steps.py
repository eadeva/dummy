"""ELF analysis execution steps.

Provides steps for:
- Reading symbol addresses/values from ELF files and storing them as global variables
- Listing ELF sections with memory usage information
"""

import os

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
    StepConfStatus,
    StepExecutionStatus,
)


class ElfReadSymbolsStepParams(BaseStepParams):
    pass
    model_config = {'extra': 'forbid'}


@StepRegistry.register('elf_read_symbols')
class ElfReadSymbolsStep(ExecutionStep):
    params_model = ElfReadSymbolsStepParams

    """Read symbols from an ELF file and store their address/value as global variables.

    For each symbol listed in ``parameters.symbols``, this step reads the
    symbol's address and value from the ELF and stores them in
    ``global_variables`` with configurable naming.

    Config example::

        type: elf_read_symbols
        parameters:
            elf_path: _bin/pl9/build/GW_2WP.elf
            symbols:
                rbx_vilib_BoschApp_InternalBoschAppSwVersion:
                    interpret_as: version_u16
                    store_address_as: APP_VERSION_ADDR
                    store_value_as: APP_VERSION
                rbx_vilib_BoschApp_BoschAppCommitHash:
                    interpret_as: string
                    store_value_as: APP_COMMIT_HASH
                rbx_vilib_BoschApp_FblSwVersion:
                    interpret_as: version_u16
                    store_value_as: FBL_VERSION

    Struct decomposition example::

        type: elf_read_symbols
        parameters:
            elf_path: _bin/pl9/build/GW_2WP.elf
            symbols:
                rbx_vilib_BoschApp_InternalBoschAppSwVersion:
                    interpret_as: struct
                    store_members_as:
                        major: APP_VERSION_MAJOR
                        minor: APP_VERSION_MINOR
                        bugfix: APP_VERSION_BUGFIX

    Parameters:
        elf_path (str): Path to the ELF file (relative to project root or absolute).
        symbols (dict): Mapping of symbol names to extraction config:
            - interpret_as (str): "auto", "string", "version_u16", "u8", "u16", "u32", "hex", "struct", "none"
            - store_address_as (str, optional): Global variable name for the address (hex string).
            - store_value_as (str, optional): Global variable name for the interpreted value.
            - store_members_as (dict, optional): Map of struct_member_name ’ variable_name.
              When provided with interpret_as: struct, each named member is stored individually.
              Use "*" as key to store all members with an auto-generated prefix.
            - set_env (bool, optional): Also export as environment variable (default: False).
    """

    def execute(self) -> None:
        """Execute the elf_read_symbols step."""
        try:
            self.pre_processing()
            parameters = self.config.get('params', {})
            elf_path = parameters.get('elf_path')
            symbols_config = parameters.get('symbols', {})

            if not elf_path:
                raise RuntimeConfigError(f"[{self.name}] 'elf_path' is required in parameters")

            # Resolve relative path against project root
            if not os.path.isabs(elf_path):
                project_root = getattr(self.context, 'project_root', os.getcwd())
                elf_path = os.path.join(project_root, elf_path)

            if not os.path.isfile(elf_path):
                raise ExecutionStepError(
                    f'[{self.name}] ELF file not found: {elf_path}',
                    phase=self.name,
                )

            # Lazy import to avoid import errors when pyelftools is not installed
            from xc_ce_utils.elf_utils import get_symbols

            # Collect all symbol names and do a single-pass lookup
            symbol_names = list(symbols_config.keys())
            interpret_default = parameters.get('interpret_as', 'auto')

            results = get_symbols(elf_path, symbol_names, interpret_as='none')

            # Process each symbol
            stored_count = 0
            for sym_name, sym_conf in symbols_config.items():
                if not isinstance(sym_conf, dict):
                    sym_conf = {}

                interpret_as = sym_conf.get('interpret_as', interpret_default)
                store_addr = sym_conf.get('store_address_as')
                store_val = sym_conf.get('store_value_as')
                set_env = sym_conf.get('set_env', False)

                elf_sym = results.get(sym_name)
                if elf_sym is None:
                    logger.warning(f"[{self.name}] Symbol '{sym_name}' not found â€” skipping")
                    continue

                # Re-read with proper interpretation if needed
                if interpret_as != 'none' and elf_sym.raw_bytes is None:
                    from xc_ce_utils.elf_utils import get_symbol

                    elf_sym = get_symbol(elf_path, sym_name, interpret_as=interpret_as)
                    if elf_sym is None:
                        continue

                # If we already have raw_bytes from 'none' mode, interpret now
                if elf_sym.value_str is None and interpret_as != 'none' and elf_sym.size > 0:
                    from xc_ce_utils.elf_utils.elf_utils import (
                        _interpret_bytes,
                        _read_symbol_bytes,
                        _try_import_elftools,
                    )

                    ELFFile = _try_import_elftools()
                    with open(elf_path, 'rb') as f:
                        elf = ELFFile(f)
                        raw = _read_symbol_bytes(elf, elf_sym.address, elf_sym.size)
                    if raw:
                        elf_sym = type(elf_sym)(
                            name=elf_sym.name,
                            address=elf_sym.address,
                            size=elf_sym.size,
                            type=elf_sym.type,
                            bind=elf_sym.bind,
                            section=elf_sym.section,
                            raw_bytes=raw,
                            value_str=_interpret_bytes(raw, elf_sym.size, interpret_as),
                        )

                # Store address
                if store_addr:
                    addr_str = f'0x{elf_sym.address:08X}'
                    self.global_variables[store_addr] = addr_str
                    if set_env:
                        os.environ[store_addr] = addr_str
                    logger.info(f'[{self.name}] {store_addr} = {addr_str}')
                    stored_count += 1

                # Store value
                if store_val:
                    value = elf_sym.value_str if elf_sym.value_str else elf_sym.address_hex
                    self.global_variables[store_val] = value
                    if set_env:
                        os.environ[store_val] = value
                    logger.info(f'[{self.name}] {store_val} = {value}')
                    stored_count += 1

                # Store struct members (interpret_as: struct)
                store_members = sym_conf.get('store_members_as')
                if store_members and interpret_as == 'struct':
                    from xc_ce_utils.elf_utils import get_symbol_members

                    members = get_symbol_members(elf_path, sym_name)
                    if members:
                        if store_members == '*' or (
                            isinstance(store_members, dict) and '*' in store_members
                        ):
                            # Auto-store all members with prefix
                            prefix = (
                                store_members.get('*', sym_name)
                                if isinstance(store_members, dict)
                                else sym_name
                            )
                            for member in members:
                                var_name = f'{prefix}_{member.name.upper()}'
                                self.global_variables[var_name] = member.value_str or ''
                                if set_env:
                                    os.environ[var_name] = member.value_str or ''
                                logger.info(f'[{self.name}] {var_name} = {member.value_str}')
                                stored_count += 1
                        elif isinstance(store_members, dict):
                            # Explicit mapping: member_name ’ variable_name
                            members_by_name = {m.name: m for m in members}
                            for member_name, var_name in store_members.items():
                                if member_name in members_by_name:
                                    m = members_by_name[member_name]
                                    self.global_variables[var_name] = m.value_str or ''
                                    if set_env:
                                        os.environ[var_name] = m.value_str or ''
                                    logger.info(f'[{self.name}] {var_name} = {m.value_str}')
                                    stored_count += 1
                                else:
                                    logger.warning(
                                        f"[{self.name}] Struct member '{member_name}' not found in "
                                        f"'{sym_name}'. Available: {[m.name for m in members]}"
                                    )
                    else:
                        logger.warning(
                            f"[{self.name}] Could not decompose '{sym_name}' as struct â€” "
                            f'no DWARF type info found or not a struct type'
                        )

            self.execution_status = StepExecutionStatus.EXECUTE_SUCCESS
            logger.success(
                f'[{self.name}] Read {len(symbol_names)} symbols, '
                f'stored {stored_count} variables from {os.path.basename(elf_path)}'
            )

        except RuntimeConfigError as e:
            self.execution_status = StepConfStatus.CONFIGURE_FAILED
            self.abort(e, abort_execution=True)
        except (ExecutionStepError, AbortError):
            self.execution_status = StepExecutionStatus.EXECUTE_FAILED
            raise
        except KeyboardInterrupt:
            message = f'[{self.name}] Interrupted by user'
            self.execution_status = StepExecutionStatus.USER_INTERRUPTED
            self.abort(AbortError(message, phase=self.name), abort_execution=True)
        except Exception as e:
            message = f'[{self.name}] ELF symbol read failed: {e!s}'
            self.execution_status = StepExecutionStatus.EXECUTE_FAILED
            self.abort(
                ExecutionStepError(message, phase=self.name),
                abort_execution=self.game_stopper,
            )


class ElfListSectionsStepParams(BaseStepParams):
    pass
    model_config = {'extra': 'forbid'}


@StepRegistry.register('elf_list_sections')
class ElfListSectionsStep(ExecutionStep):
    params_model = ElfListSectionsStepParams

    """List ELF sections with memory usage summary.

    Logs all allocated sections with their addresses and sizes, and
    optionally stores the memory usage summary in global variables.

    Config example::

        type: elf_list_sections
        parameters:
            elf_path: _bin/pl9/build/GW_2WP.elf
            allocated_only: true
            store_flash_used_as: FLASH_USED
            store_ram_used_as: RAM_USED

    Parameters:
        elf_path (str): Path to the ELF file.
        allocated_only (bool): Only show sections that occupy runtime memory (default: True).
        store_flash_used_as (str, optional): Variable name for total flash usage (bytes).
        store_ram_used_as (str, optional): Variable name for total RAM usage (bytes).
        store_total_as (str, optional): Variable name for total allocated memory (bytes).
    """

    def execute(self) -> None:
        """Execute the elf_list_sections step."""
        try:
            self.pre_processing()
            parameters = self.config.get('params', {})
            elf_path = parameters.get('elf_path')
            allocated_only = parameters.get('allocated_only', True)

            if not elf_path:
                raise RuntimeConfigError(f"[{self.name}] 'elf_path' is required in parameters")

            if not os.path.isabs(elf_path):
                project_root = getattr(self.context, 'project_root', os.getcwd())
                elf_path = os.path.join(project_root, elf_path)

            if not os.path.isfile(elf_path):
                raise ExecutionStepError(
                    f'[{self.name}] ELF file not found: {elf_path}',
                    phase=self.name,
                )

            from xc_ce_utils.elf_utils import get_memory_usage, list_sections

            sections = list_sections(elf_path, allocated_only=allocated_only)

            # Log sections table
            logger.info(
                f"[{self.name}] ELF sections ({len(sections)} {'allocated' if allocated_only else 'total'}):"
            )
            logger.info(f"  {'Name':<40} {'Address':<12} {'Size':>10}  {'Flags':<5} {'Type'}")
            logger.info(f"  {'-'*40} {'-'*12} {'-'*10}  {'-'*5} {'-'*12}")
            for sec in sections:
                size_str = f'{sec.size:,}'
                logger.info(
                    f'  {sec.name:<40} {sec.address_hex:<12} {size_str:>10}  {sec.flags:<5} {sec.type}'
                )

            # Memory usage summary
            usage = get_memory_usage(elf_path)
            logger.info(f'[{self.name}] Memory usage summary:')
            logger.info(f"  Flash (read-only): {usage['flash']['used']:,} bytes")
            logger.info(f"  RAM (read-write):  {usage['ram']['used']:,} bytes")
            logger.info(f"  Total allocated:   {usage['total_allocated']:,} bytes")

            # Store variables if requested
            store_flash = parameters.get('store_flash_used_as')
            store_ram = parameters.get('store_ram_used_as')
            store_total = parameters.get('store_total_as')

            if store_flash:
                self.global_variables[store_flash] = str(usage['flash']['used'])
                logger.info(f"[{self.name}] {store_flash} = {usage['flash']['used']}")
            if store_ram:
                self.global_variables[store_ram] = str(usage['ram']['used'])
                logger.info(f"[{self.name}] {store_ram} = {usage['ram']['used']}")
            if store_total:
                self.global_variables[store_total] = str(usage['total_allocated'])
                logger.info(f"[{self.name}] {store_total} = {usage['total_allocated']}")

            self.execution_status = StepExecutionStatus.EXECUTE_SUCCESS
            logger.success(f'[{self.name}] Section listing complete')

        except RuntimeConfigError as e:
            self.execution_status = StepConfStatus.CONFIGURE_FAILED
            self.abort(e, abort_execution=True)
        except (ExecutionStepError, AbortError):
            self.execution_status = StepExecutionStatus.EXECUTE_FAILED
            raise
        except KeyboardInterrupt:
            message = f'[{self.name}] Interrupted by user'
            self.execution_status = StepExecutionStatus.USER_INTERRUPTED
            self.abort(AbortError(message, phase=self.name), abort_execution=True)
        except Exception as e:
            message = f'[{self.name}] ELF section listing failed: {e!s}'
            self.execution_status = StepExecutionStatus.EXECUTE_FAILED
            self.abort(
                ExecutionStepError(message, phase=self.name),
                abort_execution=self.game_stopper,
            )
