"""
Logging Service
Provides structured logging functionality for the workflow
"""
import logging
import os
from datetime import datetime
from typing import Dict, Any


class Logger:
    def __init__(self, log_dir: str = 'logs', log_level: str = 'INFO'):
        """
        Initialize logger

        Args:
            log_dir: Directory to store log files
            log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        """
        self.log_dir = log_dir
        self.log_level = getattr(logging, log_level.upper(), logging.INFO)

        # Create logs directory if it doesn't exist
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)

        # Create logger
        self.logger = logging.getLogger('intercom-automation')
        self.logger.setLevel(self.log_level)

        # Clear existing handlers
        self.logger.handlers.clear()

        # Create file handler with daily rotation
        log_filename = os.path.join(
            log_dir,
            f"workflow_{datetime.now().strftime('%Y%m%d')}.log"
        )
        file_handler = logging.FileHandler(log_filename, encoding='utf-8')
        file_handler.setLevel(self.log_level)

        # Create console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(self.log_level)

        # Create formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)

        # Add handlers to logger
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)

    def info(self, message: str, **kwargs):
        """Log info message"""
        extra_info = ' | '.join([f"{k}={v}" for k, v in kwargs.items()]) if kwargs else ''
        full_message = f"{message} {extra_info}" if extra_info else message
        self.logger.info(full_message)

    def debug(self, message: str, **kwargs):
        """Log debug message"""
        extra_info = ' | '.join([f"{k}={v}" for k, v in kwargs.items()]) if kwargs else ''
        full_message = f"{message} {extra_info}" if extra_info else message
        self.logger.debug(full_message)

    def warning(self, message: str, **kwargs):
        """Log warning message"""
        extra_info = ' | '.join([f"{k}={v}" for k, v in kwargs.items()]) if kwargs else ''
        full_message = f"{message} {extra_info}" if extra_info else message
        self.logger.warning(full_message)

    def error(self, message: str, **kwargs):
        """Log error message"""
        extra_info = ' | '.join([f"{k}={v}" for k, v in kwargs.items()]) if kwargs else ''
        full_message = f"{message} {extra_info}" if extra_info else message
        self.logger.error(full_message)

    def critical(self, message: str, **kwargs):
        """Log critical message"""
        extra_info = ' | '.join([f"{k}={v}" for k, v in kwargs.items()]) if kwargs else ''
        full_message = f"{message} {extra_info}" if extra_info else message
        self.logger.critical(full_message)

    def log_workflow_start(self, article_id: str):
        """Log workflow start"""
        self.info(f"="*60)
        self.info(f"WORKFLOW STARTED", article_id=article_id)
        self.info(f"="*60)

    def log_workflow_complete(self, article_id: str, result: Dict[str, Any]):
        """Log workflow completion"""
        self.info(f"="*60)
        self.info(f"WORKFLOW COMPLETED",
                 article_id=article_id,
                 processed_charts=result.get('processed_charts', 0),
                 skipped_charts=result.get('skipped_charts', 0))
        self.info(f"="*60)

    def log_workflow_error(self, article_id: str, error: Exception):
        """Log workflow error"""
        self.error(f"WORKFLOW FAILED",
                  article_id=article_id,
                  error=str(error))

    def log_step(self, step_name: str, status: str = 'started', **kwargs):
        """Log workflow step"""
        if status == 'started':
            self.info(f"[{step_name}] Started", **kwargs)
        elif status == 'completed':
            self.info(f"[{step_name}] Completed", **kwargs)
        elif status == 'failed':
            self.error(f"[{step_name}] Failed", **kwargs)
        elif status == 'skipped':
            self.warning(f"[{step_name}] Skipped", **kwargs)

    def log_chart_processing(self, chart_title: str, status: str, **kwargs):
        """Log chart processing"""
        if status == 'success':
            self.info(f"Chart processed successfully",
                     chart_title=chart_title, **kwargs)
        elif status == 'skipped':
            self.warning(f"Chart skipped",
                        chart_title=chart_title, **kwargs)
        elif status == 'error':
            self.error(f"Chart processing failed",
                      chart_title=chart_title, **kwargs)

    def log_field_processing(self, field_name: str, status: str, **kwargs):
        """Log field processing"""
        if status == 'success':
            self.info(f"Field processed successfully",
                     field_name=field_name, **kwargs)
        elif status == 'skipped':
            self.warning(f"Field skipped",
                        field_name=field_name, **kwargs)
        elif status == 'error':
            self.error(f"Field processing failed",
                      field_name=field_name, **kwargs)

    def log_api_call(self, service: str, endpoint: str, status_code: int = None, **kwargs):
        """Log API call"""
        if status_code and status_code >= 200 and status_code < 300:
            self.info(f"API call successful",
                     service=service,
                     endpoint=endpoint,
                     status_code=status_code,
                     **kwargs)
        elif status_code:
            self.error(f"API call failed",
                      service=service,
                      endpoint=endpoint,
                      status_code=status_code,
                      **kwargs)
        else:
            self.info(f"API call initiated",
                     service=service,
                     endpoint=endpoint,
                     **kwargs)
