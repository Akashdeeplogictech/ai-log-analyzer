import re
import json
import pandas as pd
from datetime import datetime
from typing import Dict, List, Any
from collections import Counter

class LogProcessor:
    def __init__(self):
        self.error_patterns = {
            'error': r'(?i)(error|err|exception|fail|fatal)',
            'warning': r'(?i)(warn|warning|caution)',
            'critical': r'(?i)(critical|crit|emergency|alert)',
            'timeout': r'(?i)(timeout|time.?out|expired)',
            'connection': r'(?i)(connection|connect|disconnect|refused)',
            'memory': r'(?i)(memory|mem|oom|out.?of.?memory)',
            'disk': r'(?i)(disk|storage|space|full|quota)',
            'network': r'(?i)(network|net|tcp|udp|http|https)',
            'database': r'(?i)(database|db|sql|query|table)',
            'authentication': r'(?i)(auth|login|password|credential|token)'
        }
        
        self.severity_levels = {
            'CRITICAL': 4,
            'ERROR': 3,
            'WARNING': 2,
            'INFO': 1,
            'DEBUG': 0
        }
    
    def process_file(self, uploaded_file) -> Dict[str, Any]:
        """Process uploaded log file and return analysis"""
        try:
            # Read file content
            content = uploaded_file.read().decode('utf-8')
            lines = content.split('\n')
            
            # Analyze log entries
            analysis = {
                'total_lines': len(lines),
                'error_count': 0,
                'warning_count': 0,
                'critical_count': 0,
                'patterns_found': {},
                'timeline': [],
                'recommendations': [],
                'summary': ""
            }
            
            # Process each line
            for i, line in enumerate(lines):
                if not line.strip():
                    continue
                    
                # Extract timestamp
                timestamp = self.extract_timestamp(line)
                
                # Check for patterns
                for pattern_name, pattern in self.error_patterns.items():
                    if re.search(pattern, line):
                        if pattern_name not in analysis['patterns_found']:
                            analysis['patterns_found'][pattern_name] = []
                        analysis['patterns_found'][pattern_name].append({
                            'line_number': i + 1,
                            'content': line.strip(),
                            'timestamp': timestamp
                        })
                
                # Count severity levels
                if re.search(self.error_patterns['error'], line):
                    analysis['error_count'] += 1
                elif re.search(self.error_patterns['warning'], line):
                    analysis['warning_count'] += 1
                elif re.search(self.error_patterns['critical'], line):
                    analysis['critical_count'] += 1
            
            # Generate recommendations
            analysis['recommendations'] = self.generate_recommendations(analysis)
            analysis['summary'] = self.generate_summary(analysis)
            
            return analysis
            
        except Exception as e:
            return {'error': f"Failed to process file: {str(e)}"}
    
    def extract_timestamp(self, line: str) -> str:
        """Extract timestamp from log line"""
        timestamp_patterns = [
            r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}',
            r'\d{2}/\d{2}/\d{4} \d{2}:\d{2}:\d{2}',
            r'\w{3} \d{2} \d{2}:\d{2}:\d{2}',
        ]
        
        for pattern in timestamp_patterns:
            match = re.search(pattern, line)
            if match:
                return match.group()
        return ""
    
    def generate_recommendations(self, analysis: Dict) -> List[str]:
        """Generate actionable recommendations based on analysis"""
        recommendations = []
        
        if analysis['error_count'] > 10:
            recommendations.append("High error count detected. Consider investigating root causes.")
        
        if 'memory' in analysis['patterns_found']:
            recommendations.append("Memory issues detected. Check system resources and consider scaling.")
        
        if 'connection' in analysis['patterns_found']:
            recommendations.append("Connection issues found. Verify network connectivity and firewall rules.")
        
        if 'database' in analysis['patterns_found']:
            recommendations.append("Database-related issues detected. Check DB performance and connections.")
        
        return recommendations
    
    def generate_summary(self, analysis: Dict) -> str:
        """Generate analysis summary"""
        total_issues = analysis['error_count'] + analysis['warning_count'] + analysis['critical_count']
        
        summary = f"Analyzed {analysis['total_lines']} log lines. "
        summary += f"Found {total_issues} total issues: "
        summary += f"{analysis['critical_count']} critical, "
        summary += f"{analysis['error_count']} errors, "
        summary += f"{analysis['warning_count']} warnings."
        
        if analysis['patterns_found']:
            top_issues = sorted(analysis['patterns_found'].keys(), 
                              key=lambda x: len(analysis['patterns_found'][x]), 
                              reverse=True)[:3]
            summary += f" Main issue categories: {', '.join(top_issues)}."
        
        return summary
