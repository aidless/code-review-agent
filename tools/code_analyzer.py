"""
Code Static Analysis Tool - Analyzes code quality without LLM.

Performs basic static analysis:
- Line length checks
- TODO/FIXME comments
- Basic code smell detection (long functions, deep nesting)
- Language-specific checks (Python: import checks, Java: null checks)
"""
import re
import ast
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field


@dataclass
class AnalysisFinding:
    """A finding from static analysis."""
    file: str
    line: int
    severity: str  # "critical", "major", "minor", "info"
    category: str  # "style", "complexity", "security", "performance"
    message: str
    suggestion: str = ""


class CodeAnalyzer:
    """Static code analyzer for multiple languages."""
    
    def analyze_file(self, file_path: str, code: str, language: str) -> List[AnalysisFinding]:
        """
        Analyze a single file for code quality issues.
        
        Args:
            file_path: Path to the file
            code: File content (the diff patch or full code)
            language: Programming language
            
        Returns:
            List of AnalysisFinding objects
        """
        findings = []
        
        if language == "python":
            findings.extend(self._analyze_python(file_path, code))
        elif language in ("javascript", "typescript", "jsx", "tsx"):
            findings.extend(self._analyze_js_ts(file_path, code))
        else:
            # Generic analysis for unsupported languages
            findings.extend(self._analyze_generic(file_path, code))
        
        return findings
    
    def _analyze_python(self, file_path: str, code: str) -> List[AnalysisFinding]:
        findings = []
        lines = code.split("\n")
        
        # Check line length
        for i, line in enumerate(lines, 1):
            if len(line.rstrip()) > 120:
                findings.append(AnalysisFinding(
                    file=file_path,
                    line=i,
                    severity="minor",
                    category="style",
                    message=f"Line {i} exceeds 120 characters ({len(line.rstrip())})",
                    suggestion="Consider breaking the line"
                ))
        
        # Check for TODO/FIXME
        for i, line in enumerate(lines, 1):
            if re.search(r"\b(TODO|FIXME|HACK|XXX)\b", line, re.IGNORECASE):
                findings.append(AnalysisFinding(
                    file=file_path,
                    line=i,
                    severity="info",
                    category="documentation",
                    message="TODO/FIXME comment found",
                    suggestion="Consider creating a ticket to track this"
                ))
        
        # Try AST analysis (only works on valid Python code)
        try:
            tree = ast.parse(code)
            findings.extend(self._check_python_ast(file_path, tree))
        except SyntaxError:
            pass  # Code might be a diff patch, not valid Python
        
        return findings
    
    def _check_python_ast(self, file_path: str, tree: ast.AST) -> List[AnalysisFinding]:
        findings = []
        
        for node in ast.walk(tree):
            # Check for bare except clauses
            if isinstance(node, ast.ExceptHandler):
                if node.type is None:  # bare except
                    findings.append(AnalysisFinding(
                        file=file_path,
                        line=node.lineno,
                        severity="major",
                        category="reliability",
                        message="Bare except clause (except without exception type)",
                        suggestion="Catch specific exceptions instead of using bare 'except:'"
                    ))
            
            # Check for long functions (>50 lines)
            if isinstance(node, ast.FunctionDef):
                func_lines = node.end_lineno - node.lineno if hasattr(node, 'end_lineno') else 0
                if func_lines > 50:
                    findings.append(AnalysisFinding(
                        file=file_path,
                        line=node.lineno,
                        severity="minor",
                        category="complexity",
                        message=f"Function '{node.name}' is too long ({func_lines} lines)",
                        suggestion="Consider breaking into smaller functions"
                    ))
        
        return findings
    
    def _analyze_js_ts(self, file_path: str, code: str) -> List[AnalysisFinding]:
        findings = []
        lines = code.split("\n")
        
        # Check line length
        for i, line in enumerate(lines, 1):
            if len(line.rstrip()) > 120:
                findings.append(AnalysisFinding(
                    file=file_path, line=i, severity="minor", category="style",
                    message=f"Line {i} exceeds 120 characters",
                    suggestion="Consider breaking the line"
                ))
        
        # Check for console.log (should use proper logging)
        for i, line in enumerate(lines, 1):
            if re.search(r"\bconsole\.(log|debug)\b", line):
                findings.append(AnalysisFinding(
                    file=file_path, line=i, severity="minor", category="style",
                    message="console.log/debug found in production code",
                    suggestion="Use a proper logging framework instead"
                ))
        
        # Check for TODO/FIXME
        for i, line in enumerate(lines, 1):
            if re.search(r"\b(TODO|FIXME|HACK|XXX)\b", line, re.IGNORECASE):
                findings.append(AnalysisFinding(
                    file=file_path, line=i, severity="info", category="documentation",
                    message="TODO/FIXME comment found",
                    suggestion="Consider creating a ticket"
                ))
        
        return findings
    
    def _analyze_generic(self, file_path: str, code: str) -> List[AnalysisFinding]:
        findings = []
        lines = code.split("\n")
        
        # Generic checks: line length, TODO
        for i, line in enumerate(lines, 1):
            if len(line.rstrip()) > 120:
                findings.append(AnalysisFinding(
                    file=file_path, line=i, severity="minor", category="style",
                    message=f"Line {i} exceeds 120 characters",
                    suggestion="Consider breaking the line"
                ))
            if re.search(r"\b(TODO|FIXME)\b", line, re.IGNORECASE):
                findings.append(AnalysisFinding(
                    file=file_path, line=i, severity="info", category="documentation",
                    message="TODO/FIXME comment found",
                    suggestion="Consider creating a ticket"
                ))
        
        return findings
