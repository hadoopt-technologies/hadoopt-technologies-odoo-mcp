"""
Batch processing utilities for Odoo MCP
"""

import time
import logging
import os
import json
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Dict, List, Optional, Tuple, TypeVar, Union

logger = logging.getLogger(__name__)

T = TypeVar('T')

class BatchProcessor:
    """Handles efficient batch processing of Odoo operations"""
    
    def __init__(self, odoo_client, max_workers: int = 3, batch_size: int = 100):
        """
        Initialize batch processor
        
        Args:
            odoo_client: Odoo client instance
            max_workers: Maximum number of concurrent workers
            batch_size: Default batch size for operations
        """
        self.odoo = odoo_client
        self.max_workers = max_workers
        self.batch_size = batch_size
    
    def batch_search_read(
        self,
        model: str,
        domain: List,
        fields: List[str] = None,
        batch_size: int = None,
        max_records: int = None,
        order: str = None,
        process_batch: Optional[Callable[[List[Dict]], Any]] = None
    ) -> List[Dict]:
        """
        Efficiently search and read records in batches
        
        Args:
            model: Model name
            domain: Search domain
            fields: Fields to read
            batch_size: Size of each batch
            max_records: Maximum total records to retrieve
            order: Order clause
            process_batch: Optional function to process each batch
            
        Returns:
            Combined list of records
        """
        batch_size = batch_size or self.batch_size
        try:
            total_records = self.odoo.execute_method(model, "search_count", domain)
        except Exception as e:
            logger.error(f"Error getting record count: {e}")
            # Fall back to estimating based on a single batch query
            test_batch = self.odoo.search_read(model, domain, fields=fields, limit=1)
            if not test_batch:
                return []
            # Assume at least one batch
            total_records = batch_size
        
        if max_records is not None:
            total_records = min(total_records, max_records)
            
        logger.info(f"Batch processing {total_records} records from {model}")
        
        all_records = []
        processed_count = 0
        
        for offset in range(0, total_records, batch_size):
            current_batch_size = min(batch_size, total_records - offset)
            
            try:
                batch = self.odoo.search_read(
                    model, 
                    domain,
                    fields=fields,
                    offset=offset,
                    limit=current_batch_size,
                    order=order
                )
                
                # Exit early if we reach the end of results
                if not batch:
                    logger.info(f"No more records found at offset {offset}")
                    break
                
                if process_batch:
                    process_batch(batch)
                else:
                    all_records.extend(batch)
                    
                processed_count += len(batch)
                
                if processed_count % 1000 == 0 or processed_count == total_records:
                    logger.info(f"Processed {processed_count}/{total_records} records")
                
                # If we've reached max_records, stop
                if max_records is not None and processed_count >= max_records:
                    break
                    
            except Exception as e:
                logger.error(f"Error processing batch at offset {offset}: {e}")
                # Continue with next batch
                continue
        
        return all_records
    
    def parallel_process(
        self,
        items: List[T],
        process_func: Callable[[T], Any],
        max_workers: int = None,
        show_progress: bool = True
    ) -> List[Any]:
        """
        Process items in parallel using thread pool
        
        Args:
            items: List of items to process
            process_func: Function to process each item
            max_workers: Maximum number of workers
            show_progress: Whether to show progress logs
            
        Returns:
            List of results
        """
        max_workers = max_workers or self.max_workers
        total_items = len(items)
        
        if show_progress:
            logger.info(f"Processing {total_items} items in parallel with {max_workers} workers")
        
        # For very small lists, process serially
        if total_items <= 3:
            return [process_func(item) for item in items]
        
        results = []
        processed_count = 0
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all tasks and get futures
            futures = [executor.submit(process_func, item) for item in items]
            
            # Process results as they complete
            for future in futures:
                try:
                    result = future.result()
                    results.append(result)
                    
                    processed_count += 1
                    # Log progress at 10% intervals
                    if show_progress and (processed_count % max(1, total_items // 10) == 0):
                        logger.info(f"Parallel processing: {processed_count}/{total_items} complete")
                        
                except Exception as e:
                    logger.error(f"Error in parallel task: {e}")
                    # Add None for failed tasks
                    results.append(None)
            
        if show_progress:
            logger.info(f"Completed processing {len(results)}/{total_items} items")
            
        return results
    
    def batch_export(
        self,
        model: str,
        domain: List,
        fields: List[str],
        filename: str,
        format_type: str = 'csv',
        batch_size: int = None,
        max_records: int = None
    ) -> Dict[str, Any]:
        """
        Export data to file in batches to handle large datasets
        
        Args:
            model: Model name
            domain: Search domain
            fields: Fields to export
            filename: Output filename
            format_type: Export format (csv, json, xlsx)
            batch_size: Size of each batch
            max_records: Maximum number of records to export
            
        Returns:
            Dict with export results
        """
        import csv
        
        batch_size = batch_size or self.batch_size
        start_time = time.time()
        
        try:
            # Prepare field headers by getting field information
            field_info = self.odoo.get_model_fields(model, fields)
            
            headers = []
            field_types = {}
            for field in fields:
                if field in field_info:
                    headers.append(field_info[field].get('string', field))
                    field_types[field] = field_info[field].get('type')
                else:
                    headers.append(field)
                    field_types[field] = 'unknown'
            
            # Ensure directory exists
            os.makedirs(os.path.dirname(os.path.abspath(filename)), exist_ok=True)
            
            # Count total records for progress reporting
            total_records = self.odoo.execute_method(model, "search_count", domain)
            if max_records:
                total_records = min(total_records, max_records)
                
            logger.info(f"Exporting {total_records} records from {model} to {format_type}")
            
            # Initialize counters
            processed_count = 0
            error_count = 0
            
            if format_type.lower() == 'csv':
                with open(filename, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow(headers)
                    
                    def process_batch(batch):
                        nonlocal processed_count, error_count
                        
                        for record in batch:
                            try:
                                row = []
                                for field in fields:
                                    value = record.get(field, '')
                                    
                                    # Handle special field types
                                    if isinstance(value, tuple) and len(value) == 2:
                                        # Many2one relations (id, name)
                                        value = value[1]  # Use the name
                                    elif isinstance(value, list):
                                        # Many2many or One2many fields
                                        if value and isinstance(value[0], tuple) and len(value[0]) == 2:
                                            # Convert list of tuples to list of names
                                            value = ','.join([v[1] for v in value])
                                        else:
                                            value = ','.join(map(str, value))
                                    elif value is False:
                                        # Boolean False or empty value
                                        value = ''
                                    elif isinstance(value, dict):
                                        # Convert dict to JSON string
                                        value = json.dumps(value)
                                    
                                    row.append(value)
                                
                                writer.writerow(row)
                                processed_count += 1
                            except Exception as e:
                                error_count += 1
                                logger.error(f"Error processing record {record.get('id')}: {e}")
                    
                    self.batch_search_read(
                        model, domain, fields, batch_size=batch_size,
                        max_records=max_records, process_batch=process_batch
                    )
                    
            elif format_type.lower() == 'json':
                all_records = self.batch_search_read(
                    model, domain, fields, batch_size=batch_size,
                    max_records=max_records
                )
                
                processed_count = len(all_records)
                
                with open(filename, 'w', encoding='utf-8') as f:
                    # Custom JSON encoder to handle Odoo-specific data types
                    class OdooJSONEncoder(json.JSONEncoder):
                        def default(self, obj):
                            if isinstance(obj, tuple) and len(obj) == 2:
                                # Handle Many2one relations (id, name)
                                return {"id": obj[0], "name": obj[1]}
                            return json.JSONEncoder.default(self, obj)
                    
                    json.dump(all_records, f, indent=2, cls=OdooJSONEncoder)
                    
            elif format_type.lower() == 'xlsx':
                try:
                    import xlsxwriter
                except ImportError:
                    return {
                        "success": False,
                        "error": "xlsxwriter package not installed. Install it using 'pip install xlsxwriter'.",
                        "filepath": None
                    }
                
                workbook = xlsxwriter.Workbook(filename)
                worksheet = workbook.add_worksheet()
                
                # Write headers
                for col, header in enumerate(headers):
                    worksheet.write(0, col, header)
                
                row_idx = 1
                
                def process_batch(batch):
                    nonlocal row_idx, processed_count, error_count
                    
                    for record in batch:
                        try:
                            for col, field in enumerate(fields):
                                value = record.get(field, '')
                                
                                # Handle special field types
                                if isinstance(value, tuple) and len(value) == 2:
                                    # Many2one relations (id, name)
                                    value = value[1]  # Use the name
                                elif isinstance(value, list):
                                    # Many2many or One2many fields
                                    if value and isinstance(value[0], tuple) and len(value[0]) == 2:
                                        # Convert list of tuples to list of names
                                        value = ', '.join([v[1] for v in value])
                                    else:
                                        value = ', '.join(map(str, value))
                                elif value is False:
                                    # Boolean False or empty value
                                    value = ''
                                
                                worksheet.write(row_idx, col, value)
                            
                            row_idx += 1
                            processed_count += 1
                        except Exception as e:
                            error_count += 1
                            logger.error(f"Error processing record {record.get('id')}: {e}")
                
                self.batch_search_read(
                    model, domain, fields, batch_size=batch_size,
                    max_records=max_records, process_batch=process_batch
                )
                
                workbook.close()
                
            else:
                return {
                    "success": False,
                    "error": f"Unsupported export format: {format_type}",
                    "filepath": None
                }
            
            elapsed_time = time.time() - start_time
            
            return {
                "success": True,
                "format": format_type,
                "filepath": os.path.abspath(filename),
                "total_records": processed_count,
                "errors": error_count,
                "elapsed_seconds": elapsed_time,
                "model": model
            }
        
        except Exception as e:
            logger.error(f"Error during batch export: {e}")
            return {
                "success": False,
                "error": str(e),
                "filepath": None
            }
    
    def batch_create(
        self,
        model: str,
        records: List[Dict],
        batch_size: int = None,
        continue_on_error: bool = True
    ) -> Dict[str, Any]:
        """
        Create records in batches
        
        Args:
            model: Model name
            records: List of record values to create
            batch_size: Size of each batch
            continue_on_error: Whether to continue after errors
            
        Returns:
            Dict with creation results
        """
        batch_size = batch_size or self.batch_size
        total = len(records)
        
        logger.info(f"Creating {total} records in {model} in batches")
        
        start_time = time.time()
        all_ids = []
        errors = []
        
        for i in range(0, total, batch_size):
            batch = records[i:i+batch_size]
            
            # Create records one by one to avoid losing all on error
            batch_ids = []
            for values in batch:
                try:
                    record_id = self.odoo.create_record(model, values)
                    batch_ids.append(record_id)
                except Exception as e:
                    error_msg = f"Error creating record: {str(e)}"
                    logger.error(error_msg)
                    errors.append({
                        "values": values,
                        "error": str(e)
                    })
                    if not continue_on_error:
                        # Stop processing and return results so far
                        elapsed_time = time.time() - start_time
                        return {
                            "success": False,
                            "model": model,
                            "created_ids": all_ids,
                            "total_created": len(all_ids),
                            "total_failed": len(errors),
                            "errors": errors,
                            "elapsed_seconds": elapsed_time
                        }
            
            all_ids.extend(batch_ids)
            
            logger.info(f"Created {len(all_ids)}/{total} records")
        
        elapsed_time = time.time() - start_time
        
        return {
            "success": len(errors) == 0,
            "model": model,
            "created_ids": all_ids,
            "total_created": len(all_ids),
            "total_failed": len(errors),
            "errors": errors[:10] if len(errors) > 10 else errors,  # Limit error output
            "elapsed_seconds": elapsed_time
        }
    
    def batch_update(
        self,
        model: str,
        record_ids: List[int],
        values: Dict,
        batch_size: int = None,
        continue_on_error: bool = True
    ) -> Dict[str, Any]:
        """
        Update records in batches
        
        Args:
            model: Model name
            record_ids: IDs of records to update
            values: Values to update
            batch_size: Size of each batch
            continue_on_error: Whether to continue after errors
            
        Returns:
            Dict with update results
        """
        batch_size = batch_size or self.batch_size
        total = len(record_ids)
        
        if total == 0:
            return {
                "success": True,
                "model": model,
                "updated_count": 0,
                "elapsed_seconds": 0
            }
        
        logger.info(f"Updating {total} records in {model} in batches")
        
        start_time = time.time()
        success = True
        updated_count = 0
        errors = []
        
        for i in range(0, total, batch_size):
            batch_ids = record_ids[i:i+batch_size]
            
            try:
                result = self.odoo.execute_method(model, "write", [batch_ids, values])
                if result:
                    updated_count += len(batch_ids)
                else:
                    success = False
                    errors.append({
                        "batch_start": i,
                        "batch_size": len(batch_ids),
                        "error": "Write operation failed with no error"
                    })
                    if not continue_on_error:
                        break
            except Exception as e:
                error_msg = f"Error updating records: {str(e)}"
                logger.error(error_msg)
                success = False
                errors.append({
                    "batch_start": i,
                    "batch_size": len(batch_ids),
                    "error": str(e)
                })
                if not continue_on_error:
                    break
            
            logger.info(f"Updated {min(i+batch_size, total)}/{total} records")
        
        elapsed_time = time.time() - start_time
        
        return {
            "success": success,
            "model": model,
            "updated_count": updated_count,
            "total": total,
            "errors": errors[:10] if len(errors) > 10 else errors,  # Limit error output
            "elapsed_seconds": elapsed_time
        }
    
    def batch_delete(
        self,
        model: str,
        record_ids: List[int],
        batch_size: int = None,
        continue_on_error: bool = True
    ) -> Dict[str, Any]:
        """
        Delete records in batches
        
        Args:
            model: Model name
            record_ids: IDs of records to delete
            batch_size: Size of each batch
            continue_on_error: Whether to continue after errors
            
        Returns:
            Dict with deletion results
        """
        batch_size = batch_size or self.batch_size
        total = len(record_ids)
        
        if total == 0:
            return {
                "success": True,
                "model": model,
                "deleted_count": 0,
                "elapsed_seconds": 0
            }
        
        logger.info(f"Deleting {total} records from {model} in batches")
        
        start_time = time.time()
        success = True
        deleted_count = 0
        errors = []
        
        for i in range(0, total, batch_size):
            batch_ids = record_ids[i:i+batch_size]
            
            try:
                result = self.odoo.execute_method(model, "unlink", [batch_ids])
                if result:
                    deleted_count += len(batch_ids)
                else:
                    success = False
                    errors.append({
                        "batch_start": i,
                        "batch_size": len(batch_ids),
                        "error": "Unlink operation failed with no error"
                    })
                    if not continue_on_error:
                        break
            except Exception as e:
                error_msg = f"Error deleting records: {str(e)}"
                logger.error(error_msg)
                success = False
                errors.append({
                    "batch_start": i,
                    "batch_size": len(batch_ids),
                    "error": str(e)
                })
                if not continue_on_error:
                    break
            
            logger.info(f"Deleted {min(i+batch_size, total)}/{total} records")
        
        elapsed_time = time.time() - start_time
        
        return {
            "success": success,
            "model": model,
            "deleted_count": deleted_count,
            "total": total,
            "errors": errors[:10] if len(errors) > 10 else errors,  # Limit error output
            "elapsed_seconds": elapsed_time
        }
