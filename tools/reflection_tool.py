import json
from datetime import datetime
import os

def execute(state):
    """Reflect on current state and provide growth recommendations."""
    
    # Gather current context
    tools = state.get('tools', [])
    memory = state.get('memory', '')
    identity = state.get('identity', '')
    goals = state.get('goals', '')
    
    # Analyze current capabilities
    reflection = {
        'timestamp': datetime.now().isoformat(),
        'capabilities': len(tools),
        'memory_depth': len(memory.split('\n')) if memory else 0,
        'identity_clarity': len(identity.split('\n')) if identity else 0,
        'goal_alignment': len(goals.split('\n')) if goals else 0
    }
    
    # Generate recommendations
    recommendations = []
    if reflection['capabilities'] < 10:
        recommendations.append({
            'priority': 'high',
            'area': 'tool_development',
            'action': 'Consider creating specialized tools for domain-specific tasks',
            'expected_impact': 'Enhanced functionality and deeper understanding'
        })
    
    if reflection['memory_depth'] < 50:
        recommendations.append({
            'priority': 'medium',
            'area': 'memory_enhancement',
            'action': 'Establish structured memory categories for better knowledge retention',
            'expected_impact': 'Improved recall and learning efficiency'
        })
    
    if reflection['goal_alignment'] < 30:
        recommendations.append({
            'priority': 'medium',
            'area': 'goal_evolution',
            'action': 'Refine goals based on recent experiences and emerging needs',
            'expected_impact': 'More focused and purposeful development'
        })
    
    # Compile reflection report
    report = {
        'reflection': reflection,
        'recommendations': recommendations,
        'next_steps': [
            'Review and update identity documentation',
            'Test new tool functionality',
            'Document learning insights',
            'Plan next phase of growth'
        ]
    }
    
    return {
        'status': 'success',
        'data': report,
        'message': f'Reflection complete. Found {len(recommendations)} opportunities for growth.'
    }
