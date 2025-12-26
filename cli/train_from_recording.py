#!/usr/bin/env python3
"""
Generate scraper from human recording
"""
import asyncio
import json
import sys
from pathlib import Path
from agents.code_generator_agent import CodeGeneratorAgent

async def main():
    if len(sys.argv) < 2:
        print("Usage: python train_from_recording.py <recording_file>")
        sys.exit(1)
    
    recording_file = sys.argv[1]
    
    # Load recording
    with open(recording_file, 'r') as f:
        recording = json.load(f)
    
    print(f"📹 Loaded recording: {recording_file}")
    print(f"   Actions: {len(recording.get('actions', []))}")
    print(f"   Duration: {recording.get('end_time', 0) - recording.get('start_time', 0):.1f}s")
    print()
    
    # Convert recording to schema format
    # Extract unique fields from actions
    fields_map = {}
    for action in recording.get('actions', []):
        if action['action_type'] in ['fill', 'select']:
            elem_info = action.get('element_info', {})
            field_name = elem_info.get('name') or elem_info.get('id')
            if field_name and field_name not in fields_map:
                field_type = 'dropdown' if elem_info.get('tagName') == 'select' else \
                            'textarea' if elem_info.get('tagName') == 'textarea' else 'text'
                fields_map[field_name] = {
                    'name': field_name,
                    'label': elem_info.get('placeholder', field_name).replace('\u092a\u0942\u0930\u093e \u0928\u093e\u092e', 'Full Name'),
                    'type': field_type,
                    'selector': action.get('selector', f"#{field_name}"),
                    'required': False,
                    'value': action.get('value')
                }
    
    fields = list(fields_map.values())
    
    # Create schema
    schema = {
        'url': recording.get('url'),
        'municipality': recording.get('municipality'),
        'title': 'Abua Sathi Grievance Form',
        'fields': fields,
        'submit_button': {'selector': 'button[type="submit"], .btn-primary'},
        'submission_type': 'form_post',
        'success_indicator': {},
        'requires_captcha': False,
        'multi_step': False
    }
    
    print("📋 Extracted schema:")
    print(f"   Fields: {len(fields)}")
    for field in fields:
        print(f"     - {field['name']} ({field['type']})")
    print()
    
    # Generate code
    print("🤖 Generating scraper from recording...")
    agent = CodeGeneratorAgent()
    
    task = {
        'schema': schema,
        'js_analysis': {
            'strategy': 'browser_automation',
            'submission_method': 'form_post',
            'complexity': 60
        }
    }
    
    result = await agent.execute(task)
    
    if result.get('success'):
        print("✅ Scraper generated successfully!")
        print(f"   Path: {result.get('scraper', {}).get('path')}")
        print(f"   Cost: ${agent.get_total_cost():.4f}")
    else:
        print(f"❌ Failed: {result.get('error')}")
    
    return result

if __name__ == '__main__':
    asyncio.run(main())
