"""Conan setup and Conan-tools installation phases."""

from __future__ import annotations

import sys
import time
from datetime import datetime

from xc_ce_utils.conf_file_loader.conf_file_loader import (
    get_project_config_root,
)
from xc_ce_utils.core_engine.setup.phases.base import SetupContext, SetupPhase
from xc_ce_utils.rb_logger import logger


def _conan_enabled(ctx: SetupContext) -> bool:
    return bool(ctx.config.get('CONAN_ENABLED', True))


def _conan_artifactories_present(ctx: SetupContext) -> bool:
    return ctx.setup._has_conan_artifactories(ctx.config)


class ConanSetupPhase(SetupPhase):
    """Run Conan configuration setup when settings.yml changed or on first/forced setup."""

    name = 'conan_setup'

    def should_run(self, ctx: SetupContext) -> bool:
        if not _conan_enabled(ctx) or not _conan_artifactories_present(ctx):
            return False
        config_root = get_project_config_root(ctx.setup.repo_path)
        settings_file = config_root / 'conan' / 'config' / 'settings.yml'
        settings_changed = False
        if settings_file.exists():
            current_settings_hash = ctx.setup._compute_settings_hash()
            stored_settings_hash = ctx.state.get('conan_settings_hash')
            settings_changed = current_settings_hash != stored_settings_hash
            if settings_changed:
                logger.debug(' Conan settings.yml has changed - will update')
        ctx.extras['conan_settings_changed'] = settings_changed
        return ctx.first_time_setup or ctx.force or settings_changed

    def run(self, ctx: SetupContext) -> None:
        config_root = get_project_config_root(ctx.setup.repo_path)
        settings_file = config_root / 'conan' / 'config' / 'settings.yml'
        settings_changed = ctx.extras.get('conan_settings_changed', False)
        t0 = time.monotonic()
        logger.log_phase_header('SETUP - CONAN')
        if settings_changed and not ctx.first_time_setup and not ctx.force:
            logger.progress(
                'Updating Conan configuration (settings.yml changed)...'
            )
        else:
            logger.progress('Setting up Conan package manager...')
        sys.stdout.flush()
        if not ctx.setup.setup_conan(ctx.config):
            raise RuntimeError('setup_conan returned False')
        # Keep outer state dict in sync so the final _save_setup_state()
        # doesn't overwrite the hash that _conan_config_install() just persisted.
        if settings_file.exists():
            ctx.state['conan_settings_hash'] = (
                ctx.setup._compute_settings_hash()
            )
        logger.debug('Conan setup completed')
        ctx.state['setup_steps']['conan_setup'] = datetime.now().isoformat()
        sys.stdout.flush()
        logger.log_phase_header('SETUP - CONAN - END')
        logger.debug(f'  ⏱  Conan setup: {time.monotonic() - t0:.1f}s')


class ConanToolsPhase(SetupPhase):
    """Install Conan tools when ``conan_tools.yml`` changed or on first/forced setup."""

    name = 'conan_tools'

    def should_run(self, ctx: SetupContext) -> bool:
        if not _conan_enabled(ctx) or not _conan_artifactories_present(ctx):
            return False
        config_root = get_project_config_root(ctx.setup.repo_path)
        conan_tools_file = config_root / 'requirements' / 'conan_tools.yml'
        if not conan_tools_file.exists():
            return False
        return (
            ctx.first_time_setup
            or ctx.force
            or ctx.setup._check_file_hash_changed(conan_tools_file, ctx.state)
        )

    def run(self, ctx: SetupContext) -> None:
        config_root = get_project_config_root(ctx.setup.repo_path)
        conan_tools_file = config_root / 'requirements' / 'conan_tools.yml'
        t0 = time.monotonic()
        logger.log_phase_header('SETUP - CONAN TOOLS')
        logger.progress('Installing Conan tools (config changed)...')
        sys.stdout.flush()
        if not ctx.setup.install_conan_tools(force_install=ctx.force):
            raise RuntimeError('Conan tools installation failed.')
        logger.success(' Conan tools installed successfully')
        ctx.state['setup_steps']['conan_tools'] = datetime.now().isoformat()
        ctx.setup._update_file_hash(conan_tools_file, ctx.state)
        sys.stdout.flush()
        logger.log_phase_header('SETUP - CONAN TOOLS - END')
        logger.debug(f'  ⏱  Conan tools: {time.monotonic() - t0:.1f}s')
