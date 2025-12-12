import ast
import re
from typing import Dict, Any

async def extract_functions(state: Dict[str, Any]) -> Dict[str, Any]:
    code = state.get('code', '')
    functions = []
    
    try:
        tree = ast.parse(code)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                functions.append({
                    'name': node.name,
                    'line_start': node.lineno,
                    'args_count': len(node.args.args),
                    'body_length': len(node.body)
                })
    except:
        lines = code.split('\n')
        for i, line in enumerate(lines):
            if line.strip().startswith('def '):
                match = re.match(r'def\s+(\w+)', line)
                if match:
                    functions.append({
                        'name': match.group(1),
                        'line_start': i + 1,
                        'args_count': line.count(',') + 1 if '(' in line else 0,
                        'body_length': 1
                    })
    
    return {'functions': functions, 'function_count': len(functions)}

async def check_complexity(state: Dict[str, Any]) -> Dict[str, Any]:
    functions = state.get('functions', [])
    complexity_scores = []
    
    for func in functions:
        score = 0
        score += func.get('args_count', 0) * 2
        score += func.get('body_length', 0)
        
        complexity_scores.append({
            'function': func['name'],
            'complexity': score,
            'level': 'high' if score > 20 else 'medium' if score > 10 else 'low'
        })
    
    avg_complexity = sum(s['complexity'] for s in complexity_scores) / len(complexity_scores) if complexity_scores else 0
    
    return {
        'complexity_scores': complexity_scores,
        'avg_complexity': avg_complexity
    }

async def detect_issues(state: Dict[str, Any]) -> Dict[str, Any]:
    code = state.get('code', '')
    issues = []
    
    if len(code) > 5000:
        issues.append({'type': 'length', 'message': 'Code is very long', 'severity': 'medium'})
    
    if code.count('global ') > 2:
        issues.append({'type': 'globals', 'message': 'Too many global variables', 'severity': 'high'})
    
    if 'except:' in code or 'except :' in code:
        issues.append({'type': 'exception', 'message': 'Bare except clause found', 'severity': 'medium'})
    
    functions = state.get('functions', [])
    for func in functions:
        if func.get('args_count', 0) > 5:
            issues.append({
                'type': 'parameters',
                'message': f"Function {func['name']} has too many parameters",
                'severity': 'medium'
            })
    
    return {'issues': issues, 'issue_count': len(issues)}

async def suggest_improvements(state: Dict[str, Any]) -> Dict[str, Any]:
    issues = state.get('issues', [])
    complexity_scores = state.get('complexity_scores', [])
    suggestions = []
    
    for issue in issues:
        if issue['type'] == 'length':
            suggestions.append('Consider splitting the code into multiple modules')
        elif issue['type'] == 'globals':
            suggestions.append('Refactor to use class attributes or function parameters')
        elif issue['type'] == 'exception':
            suggestions.append('Use specific exception types instead of bare except')
        elif issue['type'] == 'parameters':
            suggestions.append(f"Reduce parameters in {issue['message']}")
    
    for score in complexity_scores:
        if score['level'] == 'high':
            suggestions.append(f"Simplify function {score['function']} - complexity is high")
    
    quality_score = 100 - (len(issues) * 10) - (state.get('avg_complexity', 0) / 2)
    quality_score = max(0, min(100, quality_score))
    
    return {
        'suggestions': suggestions,
        'quality_score': quality_score,
        'improvement_count': len(suggestions)
    }

def setup_code_review_workflow():
    from main import register_tool
    
    register_tool('extract_functions', extract_functions)
    register_tool('check_complexity', check_complexity)
    register_tool('detect_issues', detect_issues)
    register_tool('suggest_improvements', suggest_improvements)