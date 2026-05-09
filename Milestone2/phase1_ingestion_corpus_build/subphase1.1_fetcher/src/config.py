"""
Configuration Module
Centralized configuration management for the fetcher.
"""

import os
import yaml
from typing import Dict, List, Any
from dataclasses import dataclass
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class FetcherConfig:
    """Configuration data class for the fetcher."""
    urls: List[str]
    request_delay: float
    timeout: int
    user_agent: str
    output_dir: str
    download_dir: str
    enable_checksum_validation: bool


class ConfigManager:
    """Manages configuration loading and validation."""
    
    DEFAULT_CONFIG = {
        'request_delay': 2.0,
        'timeout': 30,
        'user_agent': (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
            'AppleWebKit/537.36 (KHTML, like Gecko) '
            'Chrome/91.0.4472.124 Safari/537.36'
        ),
        'output_dir': r'c:\Users\paree\OneDrive\Desktop\Milestone2\data\html',
        'download_dir': r'c:\Users\paree\OneDrive\Desktop\Milestone2\data\documents',
        'enable_checksum_validation': True
    }
    
    def __init__(self, config_dir: str = None):
        """
        Initialize the configuration manager.
        
        Args:
            config_dir: Directory containing configuration files
        """
        if config_dir is None:
            # Default to config directory relative to this file
            config_dir = os.path.join(os.path.dirname(__file__), '..', 'config')
        
        self.config_dir = config_dir
        self.urls_config_file = os.path.join(config_dir, 'urls.yaml')
        self.settings_config_file = os.path.join(config_dir, 'settings.yaml')
    
    def load_config(self) -> FetcherConfig:
        """
        Load configuration from YAML files.
        
        Returns:
            FetcherConfig object
        """
        # Load URLs
        urls = self._load_urls()
        
        # Load settings
        settings = self._load_settings()
        
        # Merge with defaults
        merged_settings = {**self.DEFAULT_CONFIG, **settings}
        
        # Create config object
        config = FetcherConfig(
            urls=urls,
            request_delay=merged_settings['request_delay'],
            timeout=merged_settings['timeout'],
            user_agent=merged_settings['user_agent'],
            output_dir=merged_settings['output_dir'],
            download_dir=merged_settings['download_dir'],
            enable_checksum_validation=merged_settings['enable_checksum_validation']
        )
        
        logger.info("Configuration loaded successfully")
        return config
    
    def _load_urls(self) -> List[str]:
        """
        Load URLs from configuration file.
        
        Returns:
            List of URLs (strings)
        """
        if not os.path.exists(self.urls_config_file):
            logger.warning(f"URLs config file not found: {self.urls_config_file}")
            logger.warning("Using empty URL list")
            return []
        
        try:
            with open(self.urls_config_file, 'r') as f:
                config = yaml.safe_load(f)
            
            url_entries = config.get('urls', [])
            # Extract just the URL string from each dictionary
            urls = [entry['url'] if isinstance(entry, dict) else entry for entry in url_entries]
            logger.info(f"Loaded {len(urls)} URLs from configuration")
            return urls
            
        except Exception as e:
            logger.error(f"Error loading URLs: {str(e)}")
            return []
    
    def _load_settings(self) -> Dict[str, Any]:
        """
        Load settings from configuration file.
        
        Returns:
            Dictionary of settings
        """
        if not os.path.exists(self.settings_config_file):
            logger.warning(f"Settings config file not found: {self.settings_config_file}")
            logger.warning("Using default settings")
            return {}
        
        try:
            with open(self.settings_config_file, 'r') as f:
                settings = yaml.safe_load(f)
            
            logger.info("Settings loaded from configuration")
            return settings or {}
            
        except Exception as e:
            logger.error(f"Error loading settings: {str(e)}")
            return {}
    
    def validate_config(self, config: FetcherConfig) -> bool:
        """
        Validate configuration.
        
        Args:
            config: FetcherConfig object
            
        Returns:
            True if valid, False otherwise
        """
        if not config.urls:
            logger.error("Configuration validation failed: No URLs provided")
            return False
        
        if config.request_delay < 0:
            logger.error("Configuration validation failed: Invalid request delay")
            return False
        
        if config.timeout <= 0:
            logger.error("Configuration validation failed: Invalid timeout")
            return False
        
        logger.info("Configuration validation passed")
        return True
    
    def save_urls(self, urls: List[Dict[str, str]]) -> None:
        """
        Save URLs to configuration file.
        
        Args:
            urls: List of URL dictionaries with 'url' and 'name' keys
        """
        os.makedirs(self.config_dir, exist_ok=True)
        
        config = {'urls': urls}
        
        with open(self.urls_config_file, 'w') as f:
            yaml.dump(config, f, default_flow_style=False)
        
        logger.info(f"Saved {len(urls)} URLs to configuration")
    
    def save_settings(self, settings: Dict[str, Any]) -> None:
        """
        Save settings to configuration file.
        
        Args:
            settings: Dictionary of settings
        """
        os.makedirs(self.config_dir, exist_ok=True)
        
        with open(self.settings_config_file, 'w') as f:
            yaml.dump(settings, f, default_flow_style=False)
        
        logger.info("Settings saved to configuration")


def get_config(config_dir: str = None) -> FetcherConfig:
    """
    Convenience function to load configuration.
    
    Args:
        config_dir: Directory containing configuration files
        
    Returns:
        FetcherConfig object
    """
    manager = ConfigManager(config_dir)
    config = manager.load_config()
    
    if not manager.validate_config(config):
        raise ValueError("Invalid configuration")
    
    return config


if __name__ == "__main__":
    # Example usage
    config = get_config()
    print(f"Loaded {len(config.urls)} URLs")
    print(f"Request delay: {config.request_delay}s")
    print(f"Timeout: {config.timeout}s")
    print(f"Output directory: {config.output_dir}")
