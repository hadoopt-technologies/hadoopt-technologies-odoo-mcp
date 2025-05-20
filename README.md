# Odoo MCP

A powerful MCP integration for Odoo ERP systems, providing enhanced tools and utilities for data management, analysis, and automation.

## Overview

Odoo MCP is a bridge between Claude AI and Odoo ERP systems, allowing for intelligent operations, data analysis, and process automation. It provides a comprehensive set of tools to interact with Odoo data, perform data analysis, and manage imports/exports efficiently.

## Latest Improvements (May 2025)

- **Enhanced Visualization**: Improved chart generation with support for bar, line, pie, and scatter plots
- **Advanced Analytics**: Added statistical functions including median, percentiles, and standard deviation
- **Optimized Batch Processing**: Better handling of large datasets with improved error recovery
- **Intelligent Model Discovery**: Enhanced model matching with better similarity metrics
- **Relationship Mapping**: New tools to discover and visualize relationships between models
- **Performance Enhancements**: Parallel processing capabilities and intelligent caching
- **Multi-Instance Support**: Connect to multiple Odoo instances simultaneously and switch between them seamlessly

## Features

### Core Functionality

- **Flexible Odoo Connection**: Secure XML-RPC client with robust error handling, automatic retries, and connection pooling
- **Smart Caching**: Automatic caching with TTL (Time To Live) for improved performance and reduced API calls
- **Multi-Company Support**: Full support for Odoo's multi-company environments with company-specific operations
- **Record Management**: Enhanced CRUD operations with validation and intelligent error handling
- **Batch Processing**: Efficient handling of large datasets with automatic batching and parallel processing
- **Performance Monitoring**: Built-in metrics tracking for identifying and resolving performance bottlenecks
- **Multi-Instance Management**: Manage connections to multiple Odoo instances with automatic reconnection and connection validation

### Model Discovery and Exploration

- **Natural Language Model Discovery**: Find models by description without knowing technical model names
- **Model Suggestions for Tasks**: Get recommendations for models based on business task descriptions
- **Field Categorization**: Intelligently categorized model fields (identification, descriptive, relational, etc.)
- **Model Relationship Mapping**: Explore relationships between different models
- **Data Type Detection**: Automatic classification of models as master or transactional data
- **Field Discovery**: Find relevant fields across models for specific data requirements

### Data Operations and Management

- **Advanced Searching**: Enhanced search capabilities with multi-company and archiving support
- **Duplicate Detection**: Intelligent algorithms to find and manage similar or duplicate records
- **Data Import/Export**: Streamlined import/export functionality for CSV, JSON, and XLSX formats
- **Data Validation**: Field validation against Odoo constraints to ensure data integrity
- **Record Access Control**: Verify user access rights for specific records and models
- **Archive Management**: Tools to handle archived records with enhanced visibility control
- **Cross-Instance Operations**: Query and manipulate data across multiple Odoo instances

### Analytics and Data Visualization

- **Generic Model Analysis**: Powerful analysis tools applicable to any Odoo model
- **Statistical Analysis**: Summary, trend, and distribution analysis of numeric data
- **Grouping & Aggregation**: Flexible grouping with multiple aggregation functions
- **Time Series Analysis**: Track changes and trends over custom time periods with period-over-period comparison
- **Comparative Analysis**: Compare metrics across different time periods or dimensions
- **Business Insights**: Convert raw data into actionable business intelligence
- **Sales Performance Analysis**: Specialized tools for analyzing sales pipeline and performance
- **Interactive Charts**: Generate bar, line, pie, scatter, and time series charts from Odoo data
- **Chart Customization**: Customize charts with titles, colors, and limits
- **Data Distribution Analysis**: Analyze frequency distributions and histograms of any field
- **Cross-Instance Analytics**: Compare metrics across different Odoo instances

### System Utilities and Optimization

- **Enhanced Logging**: Comprehensive logging system with file and console options
- **Resource Optimization**: Automatic resource allocation based on system capabilities
- **Configuration Management**: Flexible configuration via environment variables or config files
- **Error Handling**: Sophisticated error handling with detailed diagnostics
- **Startup Tools**: Streamlined server initialization with optimized settings
- **Performance Tuning**: Tools to monitor and improve system performance
- **Parallel Processing**: Multi-threaded operations for improved performance
- **Instance Context Management**: Temporarily switch between instances for specific operations

## Installation

Odoo MCP is designed to work as an MCP within Claude AI. No separate installation is required as Claude can access and utilize the functionality directly.

### Required Python Packages

```
# Install dependencies
pip install -r requirements.txt
```

**requirements.txt**
```
fastmcp>=1.0.0
requests>=2.28.1
xmlrpc>=0.9.0
python-dotenv>=1.0.0
pydantic>=2.0.0
pytz>=2023.3
uvicorn>=0.22.0
numpy>=1.24.3
matplotlib>=3.7.1
pandas>=2.0.1
openpyxl>=3.1.2
python-dateutil>=2.8.2
Pillow>=9.4.0
statsmodels>=0.14.0
psutil>=5.9.5
```

## Configuration

The MCP can be configured through various methods:

1. **Environment Variables**:
   - `ODOO_URL`: Odoo server URL (e.g., "https://example.odoo.com")
   - `ODOO_DB`: Database name
   - `ODOO_USERNAME`: Username for authentication
   - `ODOO_PASSWORD`: Password for authentication
   - `ODOO_TIMEOUT`: Connection timeout in seconds (default: 30)
   - `ODOO_VERIFY_SSL`: Whether to verify SSL certificates (default: true)
   - `ODOO_CACHE_ENABLED`: Enable response caching (default: true)
   - `ODOO_CACHE_TTL`: Cache time-to-live in seconds (default: 300)
   - `MCP_LOG_LEVEL`: Logging level (INFO, DEBUG, WARNING, ERROR)
   - `MCP_LOG_TO_FILE`: Whether to log to file (1, 0)

2. **Configuration File**:
   A `config.json` file can be placed in the project root:
   ```json
   {
     "url": "https://example.odoo.com",
     "db": "odoo_db",
     "username": "admin",
     "password": "password",
     "timeout": 30,
     "verify_ssl": true,
     "cache_enabled": true,
     "cache_ttl": 300
   }
   ```

3. **Multi-Instance Configuration**:
   For multiple Odoo instances, create separate configuration files named after each instance:
   - `config/production.json`
   - `config/testing.json`
   - `config/development.json`

   Or use environment variables with instance prefixes:
   ```bash
   export PRODUCTION_ODOO_URL=https://production.odoo.com
   export PRODUCTION_ODOO_DB=prod_db
   export TESTING_ODOO_URL=https://test.odoo.com
   export TESTING_ODOO_DB=test_db
   ```

## Usage Examples

### Model Discovery

The Odoo MCP includes powerful model discovery capabilities, allowing you to work with models based on descriptions rather than technical names:

#### Finding Models by Description
```
Find models related to customer invoicing
```

#### Exploring Model Fields
```
What fields are available in the customer model for storing contact information?
```

#### Suggesting Models for Tasks
```
What models would I need to analyze the sales pipeline and conversion rates?
```

#### Discovering Model Relationships
```
Show me the relationships between sales orders, invoices, and payments
```

### Data Operations

#### Searching Records
```
Find all customers from the United States with purchases over $10,000 this year
```

#### Creating Records with Duplicate Detection
```
Create a new product called "Premium Service Package" with code PS100, checking for duplicates first
```

#### Batch Processing
```
Update the status of all draft orders to "approved"
```

#### Parallel Processing
```
Process and validate all incoming supplier invoices using parallel workers
```

### Multi-Instance Operations

#### List Available Instances
```
List all available Odoo instances
```

#### Switch Between Instances
```
Switch to the production instance
```

#### Cross-Instance Operations
```
Compare inventory levels between production and testing instances
```

#### Instance-Specific Operations
```
Find all customers in the production instance and create corresponding records in the testing instance
```

### Data Analysis

#### Customer Analysis
```
Analyze the customer base by country, showing average credit limits and purchase volumes
```

#### Sales Analysis
```
Show me the quarterly sales trends by product category with margin percentages and period-over-period growth
```

#### Inventory Analysis
```
Analyze inventory levels across all warehouses, identifying slow-moving items
```

#### Statistical Analysis
```
Calculate the median, quartiles, and standard deviation of order values by customer segment
```

### Data Visualization

#### Basic Charts
```
Create a bar chart of total sales by product category for this year
```

#### Time Series Visualization
```
Generate a line chart showing sales trends over the last 12 months
```

#### Distribution Analysis
```
Show me the distribution of customer order values as a histogram
```

#### Scatter Plots
```
Create a scatter plot of product price vs. sales volume to identify pricing opportunities
```

## MCP Resources

The MCP exposes several resources for direct access:

- `odoo://models` - List all available models
- `odoo://model/{model_name}` - Get model information and fields
- `odoo://record/{model_name}/{record_id}` - Get a specific record
- `odoo://search/{model_name}/{domain}` - Search records with a domain
- `odoo://discover/{description}` - Discover models by description
- `odoo://model/{model_name}/fields` - Get detailed field information
- `odoo://chart/{model}/{measure}/{group_by}` - Generate a chart for a model
- `odoo://instances` - List all available instances
- `odoo://instance/{instance_name}` - Get information about a specific instance

## Batch Processing Capabilities

The batch processor supports:

- **Large Dataset Handling**: Process millions of records efficiently
- **Memory Optimization**: Process data in chunks to avoid memory issues
- **Parallel Processing**: Utilize multiple threads for faster processing
- **Error Recovery**: Continue processing despite errors in individual records
- **Progress Tracking**: Monitor progress of long-running operations
- **Automatic Retries**: Retry failed operations with exponential backoff
- **File Export**: Export large datasets to CSV, JSON, or XLSX formats
- **Cross-Instance Processing**: Batch operations across multiple instances

## Best Practices

1. **Use Model Discovery**: Leverage natural language model discovery rather than memorizing technical model names
2. **Specify Fields**: When possible, specify which fields you need to improve performance
3. **Use Batch Processing**: For operations involving many records, always use batch processing
4. **Leverage Caching**: The system caches results automatically, but be aware of cache TTL settings
5. **Monitor Performance**: Use the performance monitoring tools to identify bottlenecks
6. **Check for Duplicates**: When creating master data, always enable duplicate detection
7. **Enable Multi-Company Filtering**: For multi-company environments, always specify company_id
8. **Use Parallel Processing**: For CPU-intensive operations, utilize parallel processing
9. **Manage Instance Connections**: For multi-instance setups, be explicit about which instance to use
10. **Use Instance Context**: For temporary instance switching, use the instance context manager

## Troubleshooting

Common issues and their solutions:

1. **Connection Errors**:
   - Verify Odoo URL, credentials, and network connection
   - Check SSL certificate verification settings
   - Review connection timeout settings

2. **Permission Errors**:
   - Ensure the user has proper access rights for the models
   - Verify permissions for records
   - Check multi-company access settings

3. **Import Failures**:
   - Validate data format and required fields
   - Handle duplicate records appropriately
   - Use smaller batch sizes for complex imports

4. **Performance Issues**:
   - Use batch processing for large datasets
   - Specify only required fields in searches
   - Review performance metrics to identify bottlenecks
   - Optimize caching settings
   - Utilize parallel processing for CPU-intensive operations

5. **Multi-Instance Issues**:
   - Verify instance configurations
   - Check instance connection status
   - Ensure proper instance switching
   - Review instance context management

## Setup Guide

### 1. Configuration

The system is pre-configured with defaults in the `config.json` file. You can modify this file if needed, but the default configuration should work for most use cases:

```json
{
  "url": "https://example.odoo.com",
  "db": "odoo_db",
  "username": "admin",
  "password": "password",
  "verify_ssl": false,
  "timeout": 30,
  "cache_enabled": true,
  "cache_ttl": 300
}
```

For multi-instance setups, create additional configuration files in the `config` directory:

```json
{
  "url": "https://production.odoo.com",
  "db": "prod_db",
  "username": "admin",
  "password": "secure_password",
  "verify_ssl": true,
  "timeout": 60,
  "cache_enabled": true,
  "cache_ttl": 600
}
```

### 2. Running the Server

Two options are available for running the server:

1. Standard mode with file logging:
   ```
   python run_server.py
   ```

2. Console-only logging mode:
   ```
   python run_server_nofile.py
   ```

### 3. Setup in Claude Desktop

To use the Odoo MCP with Claude Desktop:

1. **Add the MCP to Claude Desktop**:
   - Open Claude Desktop application
   - Navigate to Settings > Developer
   - Click "Edit Config"
   - Open "claude_desktop_config.json"
   ```
   {
     "globalShortcut": "Alt+Space",
     "mcpServers": { 
       "odoo": {
         "command": "PATH TO VIRTUAL ENV/.venv/bin/python3",
         "args": ["PATH/run_server.py"],
         "startup_timeout": 5000
       }
     }
      
   }
   ```
 
2. **Test the Integration**:
   - Try a simple query like "List all Odoo models related to sales"
   - If functioning correctly, Claude should use the MCP to discover and list relevant models

### 4. Verifying Installation

After starting the server, you should see log output confirming successful connection to Odoo. The logs will be stored in:
- Standard mode: `~/mcp_logs/`
- Console-only mode: Terminal output only

## Example Workflows

1. **Intelligent Product Management**:
   ```
   Find all products with low inventory, update their prices and reorder points in bulk
   ```

2. **Customer Data Cleanup**:
   ```
   Discover and merge duplicate customers based on email similarity, preserving the most recent data
   ```

3. **Business Intelligence Dashboard**:
   ```
   Analyze business performance across sales, inventory, and financials for the last year, with visualizations
   ```

4. **Multi-Company Operations**:
   ```
   Generate reports across all companies while respecting access controls and data visibility
   ```

5. **Sales Pipeline Optimization**:
   ```
   Analyze conversion rates at each pipeline stage and identify bottlenecks with statistical analysis
   ```

6. **Cross-Instance Data Migration**:
   ```
   Copy all product templates from the development instance to the production instance, preserving relationships
   ```

7. **Instance Comparison**:
   ```
   Compare configuration settings between test and production instances to identify discrepancies
   ```

## License

MIT License

Copyright (c) 2025 Hadoopt Technologies Private Limited

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
