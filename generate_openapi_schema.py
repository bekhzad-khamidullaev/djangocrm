#!/usr/bin/env python
"""
Standalone script to generate OpenAPI schema
Run: python generate_openapi_schema.py
"""
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webcrm.settings')
django.setup()

from drf_spectacular.generators import SchemaGenerator
import yaml
import drf_spectacular

print("="*80)
print("OpenAPI Schema Generation")
print("="*80)
print(f"\nVersions:")
print(f"  Django: {django.__version__}")
print(f"  drf-spectacular: {drf_spectacular.__version__}")

# Create generator with ROOT_URLCONF
print(f"\nCreating SchemaGenerator...")
generator = SchemaGenerator(
    title='Django-CRM API',
    version='1.0.0',
    description='Complete REST API for Django CRM System',
    urlconf=None,  # Use ROOT_URLCONF
)

print(f"  urlconf: {generator.urlconf or 'ROOT_URLCONF'}")

# Check endpoints
from drf_spectacular.generators import EndpointEnumerator
enumerator = EndpointEnumerator(patterns=None, urlconf=None)
all_endpoints = enumerator.get_api_endpoints()

print(f"\nEndpoints discovered: {len(all_endpoints)}")
api_endpoints = [e for e in all_endpoints if e[0].startswith('/api/')]
print(f"  /api/ endpoints: {len(api_endpoints)}")

# Generate schema
print(f"\nGenerating schema...")
try:
    schema = generator.get_schema(request=None, public=False)
    
    paths = schema.get('paths', {})
    components = schema.get('components', {}).get('schemas', {})
    
    print(f"\n📊 Schema statistics:")
    print(f"   Paths: {len(paths)}")
    print(f"   Components: {len(components)}")
    
    if len(paths) == 0:
        print(f"\n❌ ERROR: No paths generated!")
        print(f"\nThis is a known issue with drf-spectacular in this project.")
        print(f"Possible solutions:")
        print(f"  1. Use Swagger UI in browser: http://localhost:8000/api/docs/")
        print(f"  2. Try downgrading drf-spectacular: pip install drf-spectacular==0.26.5")
        print(f"  3. Use alternative: pip install drf-yasg")
        sys.exit(1)
    
    # Categorize endpoints
    detail_endpoints = [p for p in paths.keys() if '{' in p]
    list_endpoints = [p for p in paths.keys() if '{' not in p]
    
    print(f"\n📋 Endpoint breakdown:")
    print(f"   List/Collection: {len(list_endpoints)}")
    print(f"   Detail/Item: {len(detail_endpoints)}")
    
    # Show sample endpoints
    print(f"\n   First 30 endpoints:")
    for i, path in enumerate(sorted(paths.keys())[:30], 1):
        methods = [m.upper() for m in paths[path].keys() if m not in ['parameters', 'description']]
        print(f"     {i:2d}. {path:55s} [{', '.join(methods)}]")
    
    if len(paths) > 30:
        print(f"     ... and {len(paths) - 30} more")
    
    # Save to file
    output_file = 'openapi-schema.yml'
    print(f"\n💾 Saving schema to {output_file}...")
    
    with open(output_file, 'w', encoding='utf-8') as f:
        yaml.dump(schema, f, sort_keys=False, allow_unicode=True,
                 default_flow_style=False, width=120, indent=2)
    
    # Get file stats
    size = os.path.getsize(output_file)
    with open(output_file, 'r') as f:
        lines = sum(1 for _ in f)
    
    print(f"\n✅ SUCCESS!")
    print(f"   File: {output_file}")
    print(f"   Size: {size:,} bytes ({size/1024:.2f} KB)")
    print(f"   Lines: {lines:,}")
    print(f"   Endpoints: {len(paths)}")
    print(f"   Models: {len(components)}")
    
    print(f"\n📖 You can now:")
    print(f"   • View the schema: cat {output_file}")
    print(f"   • Use Swagger Editor: https://editor.swagger.io/")
    print(f"   • Generate client SDK: openapi-generator generate -i {output_file}")
    
except Exception as e:
    print(f"\n❌ ERROR: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n" + "="*80)
