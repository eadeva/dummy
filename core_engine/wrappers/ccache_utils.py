"""
Utilities for ccache integration with the XC-CE build system.

This module provides helper functions to configure, manage, and optimize
ccache usage in the build process.
"""

import os
import shutil
import subprocess
from pathlib import Path
from typing import Dict, Optional, Tuple

from xc_ce_utils import logger
from xc_ce_utils.conf_file_loader.conf_file_loader import (
    get_project_config_root,
)


class CcacheManager:
    """Manager class for ccache configuration and statistics."""

    def __init__(self):
        """Initialize ccache manager."""
        self.ccache_path = shutil.which('ccache')
        self.available = self.ccache_path is not None

    def is_available(self) -> bool:
        """Check if ccache is available on the system."""
        return self.available

    def get_stats(self) -> Dict[str, str]:
        """
        Get ccache statistics.

        Returns:
            Dict[str, str]: Dictionary containing ccache statistics.
        """
        if not self.available:
            return {}

        try:
            result = subprocess.run(
                [self.ccache_path, '-s'],
                capture_output=True,
                text=True,
                check=True,
            )

            stats = {}
            for line in result.stdout.splitlines():
                if line.strip() and ':' in line:
                    key, value = line.split(':', 1)
                    stats[key.strip()] = value.strip()

            logger.info(' ccache Statistics:')
            logger.info(result.stdout)

            return stats
        except subprocess.CalledProcessError as e:
            logger.warning(f'Failed to get ccache stats: {e}')
            return {}

    def get_cache_size(self) -> Tuple[str, str]:
        """
        Get current cache size and maximum size.

        Returns:
            Tuple[str, str]: (current_size, max_size)
        """
        stats = self.get_stats()
        current_size = stats.get('cache size', '0 B')
        max_size = stats.get('max cache size', '5.0 GB')
        return current_size, max_size

    def get_hit_rate(self) -> float:
        """
        Calculate ccache hit rate percentage.

        Returns:
            float: Hit rate percentage (0-100).
        """
        stats = self.get_stats()

        try:
            hits = int(stats.get('cache hit (direct)', '0'))
            misses = int(stats.get('cache miss', '0'))

            if hits + misses == 0:
                return 0.0

            return (hits / (hits + misses)) * 100
        except (ValueError, KeyError):
            return 0.0

    def clear_cache(self) -> bool:
        """
        Clear ccache.

        Returns:
            bool: True if successful, False otherwise.
        """
        if not self.available:
            logger.warning('ccache not available, cannot clear cache')
            return False

        try:
            subprocess.run([self.ccache_path, '-C'], check=True)
            logger.info(' ccache cleared successfully')
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f'Failed to clear ccache: {e}')
            return False

    def set_max_size(self, size: str) -> bool:
        """
        Set ccache maximum size.

        Args:
            size (str): Maximum size (e.g., "10G", "500M").

        Returns:
            bool: True if successful, False otherwise.
        """
        if not self.available:
            logger.warning('ccache not available, cannot set max size')
            return False

        try:
            subprocess.run([self.ccache_path, '-M', size], check=True)
            logger.info(f' ccache max size set to {size}')
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f'Failed to set ccache max size: {e}')
            return False

    def show_config(self) -> Dict[str, str]:
        """
        Show ccache configuration.

        Returns:
            Dict[str, str]: Configuration settings.
        """
        if not self.available:
            return {}

        try:
            result = subprocess.run(
                [self.ccache_path, '-p'],
                capture_output=True,
                text=True,
                check=True,
            )

            config = {}
            for line in result.stdout.split('\n'):
                if line.strip() and '=' in line:
                    key, value = line.split('=', 1)
                    config[key.strip()] = value.strip()

            return config
        except subprocess.CalledProcessError as e:
            logger.warning(f'Failed to get ccache config: {e}')
            return {}

    def has_recent_activity(self) -> bool:
        """
        Check if ccache has recent activity (hits + misses > 0).

        Returns:
            bool: True if ccache has been used recently, False otherwise.
        """
        if not self.available:
            return False

        stats = self.get_stats()
        try:
            hits = int(stats.get('cache hit (direct)', '0'))
            misses = int(stats.get('cache miss', '0'))
            return (hits + misses) > 0
        except (ValueError, KeyError):
            return False

    def log_stats(self) -> None:
        """Log ccache statistics for build summary."""
        if not self.available:
            logger.info('ccache not available')
            return

        # Only show stats if ccache was actually used
        # if not self.has_recent_activity():
        #     logger.info("ccache available but no recent activity detected")
        #     return

        stats = self.get_stats()
        # TODO
        # current_size, max_size = self.get_cache_size()
        # hit_rate = self.get_hit_rate()

        # logger.info(" ccache Statistics:")
        # logger.info(f"  Cache size: {current_size} / {max_size}")
        # logger.info(f"  Hit rate: {hit_rate:.1f}%")
        # logger.info(f"  Cache hits: {stats.get('cache hit (direct)', '0')}")
        # logger.info(f"  Cache misses: {stats.get('cache miss', '0')}")


def setup_ccache_environment(
    cache_dir: Optional[Path] = None, max_size: Optional[str] = None
) -> bool:
    """
    Set up ccache environment variables and configuration.

    Args:
        cache_dir (Optional[Path]): Custom cache directory.
        max_size (Optional[str]): Maximum cache size (e.g., "10G").

    Returns:
        bool: True if setup was successful, False otherwise.
    """
    manager = CcacheManager()

    if not manager.is_available():
        logger.debug('ccache not available, skipping environment setup')
        return False

    # Set cache directory if specified
    if cache_dir:
        cache_dir.mkdir(parents=True, exist_ok=True)
        os.environ['CCACHE_DIR'] = str(cache_dir)
        logger.info(f' ccache directory set to: {cache_dir}')

    # Set maximum cache size if specified
    if max_size:
        manager.set_max_size(max_size)

    # Set recommended ccache options for build performance
    repo_root = Path(os.getenv('REPO_PATH', str(Path.cwd())))
    config_root = get_project_config_root(repo_root)
    os.environ['CCACHE_CONFIGPATH'] = str(
        config_root / 'ccache' / 'ccache.conf'
    )
    return True


def get_ccache_cmake_args(ccache_path: Optional[str] = None) -> Dict[str, str]:
    """
    Get CMake arguments for ccache integration.

    Args:
        ccache_path (Optional[str]): Path to ccache executable.

    Returns:
        Dict[str, str]: CMake variable definitions for ccache.
    """
    if not ccache_path:
        ccache_path = shutil.which('ccache')

    if not ccache_path:
        return {}

    return {
        'CMAKE_C_COMPILER_LAUNCHER': 'ccache.exe',
        'CMAKE_CXX_COMPILER_LAUNCHER': 'ccache.exe',
    }
