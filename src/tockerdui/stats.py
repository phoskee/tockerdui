"""
Statistics collection and dashboard functionality for tockerdui.

This module provides Docker resource statistics collection, aggregation,
and visualization helpers for the stats dashboard tab.

Features:
- Real-time resource usage statistics
- Container state distribution
- Image and volume analysis
- ASCII chart generation
- Performance metrics collection

Architecture:
- StatsCollector: Main statistics interface
- ChartRenderer: ASCII chart generation
- Data aggregation and formatting helpers
"""

import time
import math
from typing import Dict, List, Any, Tuple
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)

class StatsCollector:
    """Collects and aggregates Docker resource statistics."""
    
    def __init__(self):
        self.last_update = 0
        self.update_interval = 5.0  # Update every 5 seconds
        
    def collect_stats(self, containers, images, volumes, networks, composes, self_usage: str) -> Dict[str, Any]:
        """Collect comprehensive statistics from all resources."""
        current_time = time.time()
        
        # Cache stats collection to avoid excessive computation
        if current_time - self.last_update < self.update_interval and hasattr(self, '_cached_stats'):
            return self._cached_stats
            
        stats = {
            'containers': self._analyze_containers(containers),
            'images': self._analyze_images(images),
            'volumes': self._analyze_volumes(volumes),
            'networks': self._analyze_networks(networks),
            'compose': self._analyze_composes(composes),
            'system': self._parse_self_usage(self_usage),
            'timestamp': current_time
        }
        
        self._cached_stats = stats
        self.last_update = current_time
        return stats
    
    def _analyze_containers(self, containers) -> Dict[str, Any]:
        """Analyze container statistics."""
        if not containers:
            return {
                'total': 0,
                'running': 0,
                'stopped': 0,
                'paused': 0,
                'total_cpu': 0.0,
                'total_memory': 0.0,
                'projects': {}
            }
        
        status_counts = defaultdict(int)
        projects = defaultdict(int)
        total_cpu = 0.0
        total_memory = 0.0
        cpu_valid_count = 0
        memory_valid_count = 0
        
        for container in containers:
            status_counts[container.status] += 1
            projects[container.project] += 1
            
            # Parse CPU and memory usage
            try:
                if container.cpu_percent != "--":
                    cpu_val = float(container.cpu_percent.rstrip('%'))
                    total_cpu += cpu_val
                    cpu_valid_count += 1
                
                if container.ram_usage != "--":
                    mem_val = float(container.ram_usage.rstrip('MB'))
                    total_memory += mem_val
                    memory_valid_count += 1
            except (ValueError, AttributeError):
                continue
        
        avg_cpu = total_cpu / cpu_valid_count if cpu_valid_count > 0 else 0.0
        avg_memory = total_memory / memory_valid_count if memory_valid_count > 0 else 0.0
        
        return {
            'total': len(containers),
            'running': status_counts['running'],
            'stopped': status_counts.get('exited', 0) + status_counts.get('created', 0),
            'paused': status_counts['paused'],
            'total_cpu': total_cpu,
            'total_memory': total_memory,
            'avg_cpu': avg_cpu,
            'avg_memory': avg_memory,
            'projects': dict(projects)
        }
    
    def _analyze_images(self, images) -> Dict[str, Any]:
        """Analyze image statistics."""
        if not images:
            return {
                'total': 0,
                'total_size_mb': 0.0,
                'tagged': 0,
                'untagged': 0,
                'size_distribution': {}
            }
        
        total_size = 0.0
        tagged_count = 0
        untagged_count = 0
        size_ranges = {'<10MB': 0, '10-100MB': 0, '100MB-1GB': 0, '>1GB': 0}
        
        for image in images:
            total_size += image.size_mb
            
            # Check if tagged
            if image.tags and image.tags != ['<none>']:
                tagged_count += 1
            else:
                untagged_count += 1
            
            # Size distribution
            size_mb = image.size_mb
            if size_mb < 10:
                size_ranges['<10MB'] += 1
            elif size_mb < 100:
                size_ranges['10-100MB'] += 1
            elif size_mb < 1000:
                size_ranges['100MB-1GB'] += 1
            else:
                size_ranges['>1GB'] += 1
        
        return {
            'total': len(images),
            'total_size_mb': total_size,
            'total_size_gb': total_size / 1024,
            'tagged': tagged_count,
            'untagged': untagged_count,
            'avg_size_mb': total_size / len(images) if images else 0,
            'size_distribution': size_ranges
        }
    
    def _analyze_volumes(self, volumes) -> Dict[str, Any]:
        """Analyze volume statistics."""
        if not volumes:
            return {
                'total': 0,
                'drivers': {},
                'locations': {}
            }
        
        drivers = defaultdict(int)
        mount_locations = defaultdict(int)
        
        for volume in volumes:
            drivers[volume.driver] += 1
            
            # Classify mount points
            mountpoint = volume.mountpoint.lower()
            if '/var/lib/docker' in mountpoint:
                mount_locations['docker'] += 1
            elif '/data' in mountpoint or '/app' in mountpoint:
                mount_locations['application'] += 1
            else:
                mount_locations['other'] += 1
        
        return {
            'total': len(volumes),
            'drivers': dict(drivers),
            'locations': dict(mount_locations)
        }
    
    def _analyze_networks(self, networks) -> Dict[str, Any]:
        """Analyze network statistics."""
        if not networks:
            return {
                'total': 0,
                'drivers': {},
                'subnet_ranges': {}
            }
        
        drivers = defaultdict(int)
        subnet_classes = defaultdict(int)
        
        for network in networks:
            drivers[network.driver] += 1
            
            # Classify subnet ranges
            subnet = network.subnet.lower()
            if subnet == 'n/a':
                subnet_classes['none'] += 1
            elif subnet.startswith('172.'):
                subnet_classes['172.16/12'] += 1
            elif subnet.startswith('192.168'):
                subnet_classes['192.168/16'] += 1
            elif subnet.startswith('10.'):
                subnet_classes['10.0/8'] += 1
            else:
                subnet_classes['other'] += 1
        
        return {
            'total': len(networks),
            'drivers': dict(drivers),
            'subnet_ranges': dict(subnet_classes)
        }
    
    def _analyze_composes(self, composes) -> Dict[str, Any]:
        """Analyze compose project statistics."""
        if not composes:
            return {
                'total': 0,
                'status_distribution': {}
            }
        
        status_counts = defaultdict(int)
        
        for compose in composes:
            status_counts[compose.status] += 1
        
        return {
            'total': len(composes),
            'status_distribution': dict(status_counts)
        }
    
    def _parse_self_usage(self, usage_str: str) -> Dict[str, Any]:
        """Parse self usage string into structured data."""
        try:
            # Expected format: "CPU: 12.5% MEM: 45.2MB"
            parts = usage_str.split()
            cpu_val = 0.0
            mem_val = 0.0
            
            for i, part in enumerate(parts):
                if part == "CPU:" and i + 1 < len(parts):
                    cpu_val = float(parts[i + 1].rstrip('%'))
                elif part == "MEM:" and i + 1 < len(parts):
                    mem_val = float(parts[i + 1].rstrip('MB'))
            
            return {
                'cpu_percent': cpu_val,
                'memory_mb': mem_val,
                'raw': usage_str
            }
        except (ValueError, IndexError, AttributeError):
            return {
                'cpu_percent': 0.0,
                'memory_mb': 0.0,
                'raw': usage_str
            }

class ChartRenderer:
    """Generates ASCII charts for statistics visualization."""
    
    @staticmethod
    def bar_chart(data: Dict[str, int], width: int = 20, height: int = 5) -> List[str]:
        """Generate ASCII bar chart."""
        if not data:
            return ["No data available"]
        
        max_value = max(data.values()) if data.values() else 1
        lines = []
        
        # Chart title
        lines.append("")
        
        # Chart bars
        for label, value in data.items():
            bar_length = int((value / max_value) * width) if max_value > 0 else 0
            bar = "█" * bar_length
            lines.append(f"{label:12} {bar} {value}")
        
        lines.append("")
        return lines
    
    @staticmethod
    def pie_chart(data: Dict[str, int], width: int = 30) -> List[str]:
        """Generate simple ASCII pie chart representation."""
        if not data:
            return ["No data available"]
        
        total = sum(data.values())
        if total == 0:
            return ["No data to display"]
        
        lines = ["Distribution:"]
        for label, value in data.items():
            percentage = (value / total) * 100
            bar_length = int((percentage / 100) * width)
            bar = "█" * bar_length
            lines.append(f"{label:12} {bar} {value:4d} ({percentage:5.1f}%)")
        
        return lines
    
    @staticmethod
    def sparkline(values: List[float], width: int = 40) -> str:
        """Generate ASCII sparkline from numeric values."""
        if not values:
            return "▁" * width
        
        min_val = min(values)
        max_val = max(values)
        range_val = max_val - min_val
        
        if range_val == 0:
            return "▄" * min(width, len(values))
        
        spark_chars = "▁▂▃▄▅▆▇█"
        result = []
        
        for i, value in enumerate(values[:width]):
            if i >= width:
                break
            normalized = (value - min_val) / range_val
            char_index = int(normalized * (len(spark_chars) - 1))
            result.append(spark_chars[char_index])
        
        return ''.join(result)