"""
Configuration management for tockerdui.

This module provides configuration file support with YAML format,
user preferences, and default settings.

Features:
- YAML configuration file at ~/.config/tockerdui/config.yaml
- Default values with user overrides
- Keybinding customization
- Color theme support
- Auto-update toggle
- Log location override

Architecture:
- ConfigManager: Main configuration interface
- Merges user config with defaults
- Provides typed access to settings
- Handles missing/invalid config gracefully
"""

import os
import yaml
import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

@dataclass
class KeyBindings:
    """Customizable key bindings."""
    quit: str = "q"
    help: str = "?"
    filter: str = "/"
    tab_focus: str = "tab"
    bulk_mode: str = "b"
    select_toggle: str = "space"
    select_all: str = "a"
    select_none: str = "d"
    enter: str = "enter"
    up: str = "up"
    down: str = "down"
    page_up: str = "pgup"
    page_down: str = "pgdn"

@dataclass
class ColorTheme:
    """Color theme configuration."""
    name: str = "default"
    foreground: str = "white"
    background: str = "black"
    accent: str = "cyan"
    success: str = "green"
    warning: str = "yellow"
    error: str = "red"
    selected: str = "white_on_cyan"

@dataclass
class UIConfig:
    """UI-related configuration."""
    color_theme: ColorTheme = field(default_factory=ColorTheme)
    show_usage: bool = True
    auto_scroll_logs: bool = True
    refresh_interval: int = 100  # milliseconds

@dataclass
class DockerConfig:
    """Docker-related configuration."""
    auto_update: bool = True
    prune_interval_days: int = 30
    default_shell: str = "/bin/bash"
    fallback_shell: str = "/bin/sh"

@dataclass
class LogConfig:
    """Logging configuration."""
    level: str = "INFO"
    file_path: Optional[str] = None  # None for default
    max_size_mb: int = 10
    backup_count: int = 5

@dataclass
class AppConfig:
    """Main application configuration."""
    keybindings: KeyBindings = field(default_factory=KeyBindings)
    ui: UIConfig = field(default_factory=UIConfig)
    docker: DockerConfig = field(default_factory=DockerConfig)
    logging: LogConfig = field(default_factory=LogConfig)

class ConfigManager:
    """Configuration manager with YAML file support."""
    
    def __init__(self):
        self.config_dir = Path.home() / ".config" / "tockerdui"
        self.config_file = self.config_dir / "config.yaml"
        self._config: AppConfig = AppConfig()
        
        # Ensure config directory exists
        self.config_dir.mkdir(parents=True, exist_ok=True)
        
        # Load configuration
        self.load_config()
    
    def load_config(self) -> None:
        """Load configuration from YAML file."""
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r') as f:
                    user_config = yaml.safe_load(f) or {}
                
                # Merge with defaults
                self._config = self._merge_configs(AppConfig(), user_config)
                logger.debug(f"Loaded configuration from {self.config_file}")
            else:
                # Create default config file
                self.save_config()
                logger.info(f"Created default configuration at {self.config_file}")
        except Exception as e:
            logger.error(f"Failed to load config: {e}, using defaults")
            self._config = AppConfig()
    
    def save_config(self) -> None:
        """Save current configuration to YAML file."""
        try:
            config_dict = self._config_to_dict(self._config)
            with open(self.config_file, 'w') as f:
                yaml.dump(config_dict, f, default_flow_style=False, indent=2)
            logger.debug(f"Saved configuration to {self.config_file}")
        except Exception as e:
            logger.error(f"Failed to save config: {e}")
    
    def get_config(self) -> AppConfig:
        """Get current configuration."""
        return self._config
    
    def _merge_configs(self, default: AppConfig, user: Dict[str, Any]) -> AppConfig:
        """Merge user config with defaults."""
        # Simple recursive merge for our nested structure
        if 'keybindings' in user:
            self._merge_dataclass(default.keybindings, user['keybindings'])
        if 'ui' in user:
            self._merge_dataclass(default.ui, user['ui'])
            if 'color_theme' in user['ui']:
                self._merge_dataclass(default.ui.color_theme, user['ui']['color_theme'])
        if 'docker' in user:
            self._merge_dataclass(default.docker, user['docker'])
        if 'logging' in user:
            self._merge_dataclass(default.logging, user['logging'])
        
        return default
    
    def _merge_dataclass(self, obj: Any, updates: Dict[str, Any]) -> None:
        """Merge updates into dataclass object."""
        for key, value in updates.items():
            if hasattr(obj, key):
                setattr(obj, key, value)
    
    def _config_to_dict(self, config: AppConfig) -> Dict[str, Any]:
        """Convert config dataclass to dictionary."""
        return {
            'keybindings': {
                'quit': config.keybindings.quit,
                'help': config.keybindings.help,
                'filter': config.keybindings.filter,
                'tab_focus': config.keybindings.tab_focus,
                'bulk_mode': config.keybindings.bulk_mode,
                'select_toggle': config.keybindings.select_toggle,
                'select_all': config.keybindings.select_all,
                'select_none': config.keybindings.select_none,
                'enter': config.keybindings.enter,
                'up': config.keybindings.up,
                'down': config.keybindings.down,
                'page_up': config.keybindings.page_up,
                'page_down': config.keybindings.page_down,
            },
            'ui': {
                'color_theme': {
                    'name': config.ui.color_theme.name,
                    'foreground': config.ui.color_theme.foreground,
                    'background': config.ui.color_theme.background,
                    'accent': config.ui.color_theme.accent,
                    'success': config.ui.color_theme.success,
                    'warning': config.ui.color_theme.warning,
                    'error': config.ui.color_theme.error,
                    'selected': config.ui.color_theme.selected,
                },
                'show_usage': config.ui.show_usage,
                'auto_scroll_logs': config.ui.auto_scroll_logs,
                'refresh_interval': config.ui.refresh_interval,
            },
            'docker': {
                'auto_update': config.docker.auto_update,
                'prune_interval_days': config.docker.prune_interval_days,
                'default_shell': config.docker.default_shell,
                'fallback_shell': config.docker.fallback_shell,
            },
            'logging': {
                'level': config.logging.level,
                'file_path': config.logging.file_path,
                'max_size_mb': config.logging.max_size_mb,
                'backup_count': config.logging.backup_count,
            }
        }
    
    def get_key_binding(self, action: str) -> str:
        """Get key binding for action."""
        return getattr(self._config.keybindings, action, '')
    
    def is_key_binding(self, key: str, action: str) -> bool:
        """Check if key matches the binding for action."""
        binding = self.get_key_binding(action)
        return key.lower() == binding.lower()
    
    def get_log_level(self) -> str:
        """Get configured log level."""
        return self._config.logging.level.upper()
    
    def get_custom_log_path(self) -> Optional[str]:
        """Get custom log file path if configured."""
        return self._config.logging.file_path
    
    def should_auto_update(self) -> bool:
        """Check if auto-update is enabled."""
        return self._config.docker.auto_update
    
    def get_refresh_interval(self) -> int:
        """Get UI refresh interval in milliseconds."""
        return self._config.ui.refresh_interval
    
    def get_default_shell(self) -> str:
        """Get default shell for container exec."""
        return self._config.docker.default_shell

# Global config instance
config_manager = ConfigManager()