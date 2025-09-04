import os
import json
import pickle
from typing import List, Dict, Any
from collections import defaultdict
import re

class KnowledgeBase:
    def __init__(self):
        self.knowledge_file = "data/knowledge_base.json"
        self.ensure_data_dir()
        self.knowledge_data = self.load_knowledge_base()
        
    def ensure_data_dir(self):
        """Ensure data directory exists"""
        os.makedirs("data", exist_ok=True)
        
    def load_knowledge_base(self) -> Dict[str, Any]:
        """Load knowledge base from file or create default"""
        if os.path.exists(self.knowledge_file):
            try:
                with open(self.knowledge_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Error loading knowledge base: {e}")
                
        # Default knowledge base
        default_kb = {
            "error_solutions": {
                "outofmemoryerror": {
                    "description": "Java heap space exhausted",
                    "solutions": [
                        "Increase JVM heap size with -Xmx parameter",
                        "Optimize memory usage in application code",
                        "Check for memory leaks",
                        "Use memory profiling tools"
                    ],
                    "keywords": ["memory", "heap", "oom", "outofmemory"]
                },
                "connection_refused": {
                    "description": "Service not accepting connections",
                    "solutions": [
                        "Check if the service is running",
                        "Verify port is not blocked by firewall",
                        "Check service configuration",
                        "Restart the service if necessary"
                    ],
                    "keywords": ["connection", "refused", "connect", "port"]
                },
                "timeout_error": {
                    "description": "Request or operation timed out",
                    "solutions": [
                        "Increase timeout values in configuration",
                        "Check network connectivity and latency",
                        "Monitor server performance and load",
                        "Optimize slow operations"
                    ],
                    "keywords": ["timeout", "timed", "slow", "latency"]
                },
                "permission_denied": {
                    "description": "Insufficient permissions to access resource",
                    "solutions": [
                        "Check file/directory permissions with ls -la",
                        "Verify user has appropriate access rights",
                        "Use chmod to adjust permissions if needed",
                        "Check SELinux context if applicable"
                    ],
                    "keywords": ["permission", "denied", "access", "forbidden"]
                },
                "disk_space_full": {
                    "description": "No space left on device",
                    "solutions": [
                        "Clean up old log files and temporary files",
                        "Use df -h to check disk usage",
                        "Implement log rotation",
                        "Expand storage or add new disk"
                    ],
                    "keywords": ["disk", "space", "full", "storage"]
                },
                "database_error": {
                    "description": "Database connection or query issues",
                    "solutions": [
                        "Check database service status",
                        "Verify connection parameters",
                        "Check database locks and transactions",
                        "Monitor database performance"
                    ],
                    "keywords": ["database", "db", "sql", "query", "table"]
                }
            },
            "system_commands": {
                "memory_check": [
                    "free -h  # Check memory usage",
                    "ps aux --sort=-%mem | head -10  # Top memory consumers",
                    "cat /proc/meminfo  # Detailed memory info"
                ],
                "disk_check": [
                    "df -h  # Check disk space",
                    "du -sh /* | sort -rh | head -10  # Large directories",
                    "lsof +L1  # Find deleted files still open"
                ],
                "process_check": [
                    "ps aux  # All running processes",
                    "top  # Real-time process monitor",
                    "netstat -tulpn  # Network connections"
                ],
                "log_analysis": [
                    "tail -f /var/log/messages  # System messages",
                    "journalctl -f  # Systemd logs",
                    "grep -i error /var/log/*  # Search for errors"
                ]
            },
            "centos_specific": {
                "firewall": [
                    "sudo firewall-cmd --list-all  # Check firewall rules",
                    "sudo firewall-cmd --permanent --add-port=PORT/tcp  # Open port",
                    "sudo firewall-cmd --reload  # Reload firewall"
                ],
                "services": [
                    "sudo systemctl status SERVICE  # Check service status",
                    "sudo systemctl start SERVICE  # Start service",
                    "sudo systemctl enable SERVICE  # Enable on boot"
                ],
                "packages": [
                    "sudo yum update  # Update packages",
                    "sudo yum install PACKAGE  # Install package",
                    "yum list installed | grep PACKAGE  # Check if installed"
                ]
            }
        }
        
        self.save_knowledge_base(default_kb)
        return default_kb
    
    def save_knowledge_base(self, data: Dict[str, Any]):
        """Save knowledge base to file"""
        try:
            with open(self.knowledge_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"Error saving knowledge base: {e}")

    def search_relevant_content(self, query: str, n_results: int = 5) -> str:
        """Search for relevant content in knowledge base"""
        query_lower = query.lower()
        relevant_content = []
        
        # Search error solutions
        for error_type, error_info in self.knowledge_data.get("error_solutions", {}).items():
            keywords = error_info.get("keywords", [])
            if any(keyword in query_lower for keyword in keywords):
                content = f"**{error_type.replace('_', ' ').title()}**\n"
                content += f"Description: {error_info.get('description', 'No description')}\n"
                content += "Solutions:\n"
                for i, solution in enumerate(error_info.get('solutions', [])[:3], 1):
                    content += f"  {i}. {solution}\n"
                relevant_content.append(content)
        
        # Search system commands
        command_keywords = {
            'memory': 'memory_check',
            'disk': 'disk_check', 
            'process': 'process_check',
            'log': 'log_analysis'
        }
        
        for keyword, command_type in command_keywords.items():
            if keyword in query_lower:
                commands = self.knowledge_data.get("system_commands", {}).get(command_type, [])
                if commands:
                    content = f"**{command_type.replace('_', ' ').title()} Commands**\n"
                    for cmd in commands[:3]:
                        content += f"  • {cmd}\n"
                    relevant_content.append(content)
        
        # Search CentOS specific commands
        if any(term in query_lower for term in ['centos', 'firewall', 'service', 'yum']):
            for section, commands in self.knowledge_data.get("centos_specific", {}).items():
                content = f"**CentOS {section.title()} Commands**\n"
                for cmd in commands[:3]:
                    content += f"  • {cmd}\n"
                relevant_content.append(content)
        
        return "\n".join(relevant_content[:n_results]) if relevant_content else self.get_general_troubleshooting()

    def get_general_troubleshooting(self) -> str:
        """Return general troubleshooting advice"""
        return """**General Troubleshooting Steps**
1. Check system logs: journalctl -xe
2. Monitor resources: top, free -h, df -h
3. Verify services: systemctl status SERVICE_NAME
4. Check network: ping, netstat -tulpn
5. Review configuration files for recent changes"""

    def add_custom_solution(self, error_type: str, description: str, solutions: List[str], keywords: List[str]):
        """Add custom solution to knowledge base"""
        if "error_solutions" not in self.knowledge_data:
            self.knowledge_data["error_solutions"] = {}
            
        self.knowledge_data["error_solutions"][error_type] = {
            "description": description,
            "solutions": solutions,
            "keywords": keywords
        }
        self.save_knowledge_base(self.knowledge_data)

    def get_error_explanation(self, error_type: str) -> str:
        """Get detailed explanation for specific error types"""
        error_explanations = {
            "404": "HTTP 404 Not Found - The requested resource could not be found on the server",
            "500": "HTTP 500 Internal Server Error - The server encountered an unexpected condition",
            "timeout": "Request timeout - The server took too long to respond to the request",
            "connection_refused": "Connection refused - The target server actively refused the connection",
            "segmentation_fault": "Segmentation fault - Program tried to access memory it doesn't have permission to access",
            "kernel_panic": "Kernel panic - Critical system error that requires system restart"
        }
        return error_explanations.get(error_type.lower(), "No explanation available for this error type")

    def search_by_similarity(self, query: str) -> List[str]:
        """Simple text similarity search without external dependencies"""
        query_words = set(query.lower().split())
        matches = []
        
        for error_type, error_info in self.knowledge_data.get("error_solutions", {}).items():
            # Check keywords
            keywords = set(error_info.get("keywords", []))
            description_words = set(error_info.get("description", "").lower().split())
            
            # Calculate simple overlap score
            overlap = len(query_words.intersection(keywords.union(description_words)))
            if overlap > 0:
                matches.append((error_type, overlap))
        
        # Sort by overlap score
        matches.sort(key=lambda x: x[1], reverse=True)
        return [match[0] for match in matches[:5]]