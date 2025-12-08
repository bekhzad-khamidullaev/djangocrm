#!/usr/bin/env python
"""
Generate OpenAPI schema using drf-yasg (alternative to drf-spectacular)
"""
import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'webcrm.settings')
django.setup()

from drf_yasg.generators import OpenAPISchemaGenerator
from drf_yasg import openapi
import yaml

print("="*80)
print("OpenAPI Schema Generation with drf-yasg")
print("="*80)

print(f"\nCreating schema generator...")

# Create generator
generator = OpenAPISchemaGenerator(
    info=openapi.Info(
        title="Django-CRM API",
        default_version='v1',
        description="Complete REST API for Django CRM System",
        terms_of_service="https://www.djangocrm.io/terms/",
        contact=openapi.Contact(email="support@djangocrm.io"),
        license=openapi.License(name="MIT License"),
    ),
    url='http://localhost:8000/',
    urlconf='api.urls',  # Point to api.urls
)

print(f"  Generator created")
print(f"  urlconf: api.urls")

# Generate schema
print(f"\nGenerating schema...")

try:
    schema = generator.get_schema(request=None, public=False)
    
    # Convert to dict
    schema_dict = schema.as_odict() if hasattr(schema, 'as_odict') else dict(schema)
    
    paths = schema_dict.get('paths', {})
    definitions = schema_dict.get('definitions', {})
    
    print(f"\n📊 Schema statistics:")
    print(f"   Paths: {len(paths)}")
    print(f"   Definitions: {len(definitions)}")
    
    if len(paths) == 0:
        print(f"\n⚠️  WARNING: No paths generated with drf-yasg either!")
        print(f"\nTrying with ROOT_URLCONF...")
        
        # Try with ROOT_URLCONF
        generator2 = OpenAPISchemaGenerator(
            info=openapi.Info(
                title="Django-CRM API",
                default_version='v1',
                description="Complete REST API for Django CRM System",
            ),
            url='http://localhost:8000/',
            urlconf=None,  # Use ROOT_URLCONF
        )
        
        schema = generator2.get_schema(request=None, public=False)
        schema_dict = schema.as_odict() if hasattr(schema, 'as_odict') else dict(schema)
        paths = schema_dict.get('paths', {})
        definitions = schema_dict.get('definitions', {})
        
        print(f"   Paths: {len(paths)}")
        print(f"   Definitions: {len(definitions)}")
    
    if len(paths) > 0:
        # Categorize
        detail_paths = [p for p in paths.keys() if '{' in p]
        list_paths = [p for p in paths.keys() if '{' not in p]
        
        print(f"\n📋 Endpoint breakdown:")
        print(f"   List/Collection: {len(list_paths)}")
        print(f"   Detail/Item: {len(detail_paths)}")
        
        # Show samples
        print(f"\n   First 30 endpoints:")
        for i, path in enumerate(sorted(paths.keys())[:30], 1):
            methods = list(paths[path].keys())
            print(f"     {i:2d}. {path:55s} [{', '.join([m.upper() for m in methods])}]")
        
        if len(paths) > 30:
            print(f"     ... and {len(paths) - 30} more")
        
        # Save to YAML
        output_file = 'openapi-schema.yml'
        print(f"\n💾 Saving to {output_file}...")
        
        with open(output_file, 'w', encoding='utf-8') as f:
            yaml.dump(schema_dict, f, sort_keys=False, allow_unicode=True,
                     default_flow_style=False, width=120, indent=2)
        
        # Stats
        size = os.path.getsize(output_file)
        lines = sum(1 for _ in open(output_file))
        
        print(f"\n✅ SUCCESS with drf-yasg!")
        print(f"   File: {output_file}")
        print(f"   Size: {size:,} bytes ({size/1024:.2f} KB)")
        print(f"   Lines: {lines:,}")
        print(f"   Endpoints: {len(paths)}")
        print(f"   Models: {len(definitions)}")
        
        print(f"\n📖 Next steps:")
        print(f"   • View: cat {output_file}")
        print(f"   • Edit: https://editor.swagger.io/")
        print(f"   • Generate client: openapi-generator generate -i {output_file}")
        
    else:
        print(f"\n❌ ERROR: Still no paths with drf-yasg!")
        print(f"\nThis indicates a fundamental configuration issue.")
        print(f"Please check:")
        print(f"  • ViewSets are registered in router")
        print(f"  • URL patterns are correct")
        print(f"  • No global schema exclusions")
        sys.exit(1)
        
except Exception as e:
    print(f"\n❌ ERROR: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n" + "="*80)
