import logging
import re

# Add a filter to mask sensitive information
class SensitiveDataFilter(logging.Filter):
    def __init__(self, patterns=None):
        super().__init__()
        self.patterns = patterns or [
            (r'bot[0-9]+:[A-Za-z0-9-_]+', 'bot_token_redacted'),
            # Add other patterns as needed
        ]

    def filter(self, record):
        msg = record.getMessage()
        for pattern, replacement in self.patterns:
            msg = re.sub(pattern, replacement, msg)
        record.msg = msg
        return True

# Add this filter to your logger configuration
logger.addFilter(SensitiveDataFilter()) 