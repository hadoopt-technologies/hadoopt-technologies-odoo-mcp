# Odoo MCP Instance Configuration

This directory contains configuration files for connecting to different Odoo instances.

## Configuration File Format

Each Odoo instance should have its own JSON configuration file with the following format:

```json
{
  "url": "https://example.odoo.com",
  "db": "example_db",
  "username": "admin",
  "password": "admin_password",
  "timeout": 30,
  "verify_ssl": true,
  "cache_enabled": true,
  "cache_ttl": 300
}
```

## File Naming

The filename (without `.json` extension) will be used as the instance name. For example:
- `default.json` - Default instance
- `production.json` - Production instance
- `test.json` - Test instance

## Environment Variables

Instead of configuration files, you can also use environment variables:

```
# For the default instance
ODOO_URL=https://example.odoo.com
ODOO_DB=example_db
ODOO_USERNAME=admin
ODOO_PASSWORD=admin_password
ODOO_TIMEOUT=30
ODOO_VERIFY_SSL=1
ODOO_CACHE_ENABLED=1
ODOO_CACHE_TTL=300

# For a named instance (e.g., "PRODUCTION")
PRODUCTION_ODOO_URL=https://production.odoo.com
PRODUCTION_ODOO_DB=production_db
PRODUCTION_ODOO_USERNAME=admin
PRODUCTION_ODOO_PASSWORD=admin_password
PRODUCTION_ODOO_TIMEOUT=30
PRODUCTION_ODOO_VERIFY_SSL=1
PRODUCTION_ODOO_CACHE_ENABLED=1
PRODUCTION_ODOO_CACHE_TTL=300
```

## Usage

When using the Odoo MCP server, you can switch between instances using the `switch_instance` tool:

```python
# Switch to the "production" instance
result = switch_instance(instance_name="production")

# Execute a method on the "test" instance
result = execute_method_on_instance(
    instance_name="test",
    model="res.partner",
    method="search_read",
    args=[[["is_company", "=", True]]],
    kwargs={"fields": ["name", "email"]}
)
```

Or you can specify the instance name when using any of the main tools:

```python
# Search records on the "test" instance
result = search_records(
    model="res.partner",
    domain=[["is_company", "=", True]],
    fields=["name", "email"],
    instance_name="test"
)
```
