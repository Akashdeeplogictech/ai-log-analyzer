import os
import json
import pickle
from typing import List, Dict, Any
from collections import defaultdict
import re
import logging

logger = logging.getLogger(__name__)

class KnowledgeBase:
    def __init__(self):
        self.knowledge_file = "data/knowledge_base.json"
        self.cache_file = "data/search_cache.pkl"
        self.ensure_data_dir()
        self.knowledge_data = self.load_knowledge_base()
        self.search_cache = self.load_search_cache()
        
        # Pre-compile regex patterns for better performance
        self._compiled_patterns = {}
        self._precompile_patterns()
    
    def ensure_data_dir(self):
        """Ensure data directory exists"""
        os.makedirs("data", exist_ok=True)
    
    def _precompile_patterns(self):
        """Pre-compile common search patterns for performance"""
        common_patterns = {
            'memory': r'\b(memory|mem|oom|heap|ram)\b',
            'disk': r'\b(disk|storage|space|full|quota)\b',
            'connection': r'\b(connection|connect|refused|timeout)\b',
            'error': r'\b(error|err|exception|fail|fatal)\b',
            'database': r'\b(database|db|sql|query|table)\b',
            'network': r'\b(network|net|tcp|udp|http|https)\b'
        }
        
        for name, pattern in common_patterns.items():
            try:
                self._compiled_patterns[name] = re.compile(pattern, re.IGNORECASE)
            except Exception as e:
                logger.warning(f"Failed to compile pattern {name}: {e}")
    
    def load_search_cache(self) -> Dict[str, str]:
        """Load search result cache"""
        try:
            if os.path.exists(self.cache_file):
                with open(self.cache_file, 'rb') as f:
                    return pickle.load(f)
        except Exception as e:
            logger.warning(f"Failed to load search cache: {e}")
        return {}
    
    def save_search_cache(self):
        """Save search result cache"""
        try:
            # Limit cache size to prevent memory issues
            if len(self.search_cache) > 100:
                # Keep only the 50 most recent entries
                items = list(self.search_cache.items())[-50:]
                self.search_cache = dict(items)
            
            with open(self.cache_file, 'wb') as f:
                pickle.dump(self.search_cache, f)
        except Exception as e:
            logger.warning(f"Failed to save search cache: {e}")
        
    def load_knowledge_base(self) -> Dict[str, Any]:
        """Load knowledge base from file or create default"""
        try:
            if os.path.exists(self.knowledge_file):
                with open(self.knowledge_file, 'r') as f:
                    data = json.load(f)
                    logger.info("Knowledge base loaded successfully")
                    return data
        except Exception as e:
            logger.error(f"Error loading knowledge base: {e}")
        
        # Create default knowledge base if loading fails
        logger.info("Creating default knowledge base")
        return self._create_default_kb()
    
    def _create_default_kb(self) -> Dict[str, Any]:
        """Create default knowledge base with essential data"""
        default_kb = {
            "quick_solutions": {
                "disk_space": "Use 'df -h' to check disk usage and 'du -sh /*' to find large directories",
                "memory_issue": "Check memory with 'free -h' and top memory processes with 'ps aux --sort=-%mem'",
                "connection_refused": "Verify service status with 'systemctl status SERVICE' and check firewall",
                "high_cpu": "Use 'top' or 'htop' to identify CPU-intensive processes",
                "permission_denied": "Check permissions with 'ls -la' and fix with 'chmod' if needed"
            },
            "error_patterns": {
                "out of memory": ["memory", "oom", "heap"],
                "disk full": ["disk", "space", "full", "quota"],
                "connection issues": ["connection", "refused", "timeout", "unreachable"],
                "permission problems": ["permission", "denied", "forbidden", "access"]
            },
            "common_commands": [
                "systemctl status SERVICE - check service status",
                "df -h - check disk space",
                "free -h - check memory usage",
                "ps aux - list all processes",
                "netstat -tulpn - check network connections"
            ]
        }
        
        try:
            self.save_knowledge_base(default_kb)
        except Exception as e:
            logger.error(f"Failed to save default KB: {e}")
        
        return default_kb

    def save_knowledge_base(self, data: Dict[str, Any]):
        """Save knowledge base to file"""
        try:
            with open(self.knowledge_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving knowledge base: {e}")

    def search_relevant_content(self, query: str, n_results: int = 3) -> str:
        """Fast search for relevant content with caching"""
        if not query or not query.strip():
            return ""
        
        # Normalize query for caching
        query_key = query.lower().strip()
        
        # Check cache first
        if query_key in self.search_cache:
            logger.info("Returning cached search result")
            return self.search_cache[query_key]
        
        try:
            logger.info(f"Performing fresh search for: {query_key[:30]}...")
            
            # Fast keyword-based search
            results = self._fast_keyword_search(query_key, n_results)
            
            # Cache the result
            self.search_cache[query_key] = results
            
            # Save cache asynchronously
            try:
                self.save_search_cache()
            except Exception as e:
                logger.warning(f"Failed to save cache: {e}")
            
            return results
            
        except Exception as e:
            logger.error(f"Search error: {e}")
            return self._get_fallback_response(query_key)
    
    def _fast_keyword_search(self, query: str, max_results: int) -> str:
        """Optimized keyword-based search"""
        query_words = set(query.lower().split())
        results = []
        
        # Search quick solutions first (fastest)
        quick_solutions = self.knowledge_data.get("quick_solutions", {})
        for key, solution in quick_solutions.items():
            if any(word in key.lower() or word in solution.lower() for word in query_words):
                results.append(f"**Quick Fix**: {solution}")
                if len(results) >= max_results:
                    break
        
        # Search error patterns if we need more results
        if len(results) < max_results:
            error_patterns = self.knowledge_data.get("error_patterns", {})
            for error_type, keywords in error_patterns.items():
                if any(keyword in query for keyword in keywords):
                    results.append(f"**{error_type.title()}**: Check for {', '.join(keywords[:3])}")
                    if len(results) >= max_results:
                        break
        
        # Add common commands if still need results
        if len(results) < max_results:
            common_commands = self.knowledge_data.get("common_commands", [])
            for cmd in common_commands[:2]:  # Limit to 2 commands
                if any(word in cmd.lower() for word in query_words):
                    results.append(f"**Command**: {cmd}")
                    if len(results) >= max_results:
                        break
        
        return "\n\n".join(results) if results else ""
    
    def _get_fallback_response(self, query: str) -> str:
        """Provide fallback response for failed searches"""
        if any(term in query for term in ['disk', 'space', 'full']):
            return "**Quick Fix**: Use 'df -h' to check disk usage and clean up unnecessary files"
        elif any(term in query for term in ['memory', 'oom', 'ram']):
            return "**Quick Fix**: Check memory usage with 'free -h' and identify memory-intensive processes"
        elif any(term in query for term in ['connection', 'refused', 'timeout']):
            return "**Quick Fix**: Check service status and network connectivity"
        else:
            return "**General**: Check system logs with 'journalctl -xe' for more information"
    
    def get_pattern_matches(self, text: str) -> List[str]:
        """Fast pattern matching using pre-compiled regex"""
        matches = []
        
        for pattern_name, compiled_pattern in self._compiled_patterns.items():
            if compiled_pattern.search(text):
                matches.append(pattern_name)
                
        return matches
    
    def clear_cache(self):
        """Clear search cache"""
        try:
            self.search_cache.clear()
            if os.path.exists(self.cache_file):
                os.remove(self.cache_file)
            logger.info("Search cache cleared")
        except Exception as e:
            logger.error(f"Error clearing cache: {e}")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        return {
            'cache_size': len(self.search_cache),
            'knowledge_sections': list(self.knowledge_data.keys()),
            'compiled_patterns': len(self._compiled_patterns)
        }