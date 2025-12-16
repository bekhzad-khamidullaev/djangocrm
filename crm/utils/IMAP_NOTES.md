# IMAP Management Notes

## Throttling Configuration

Error notifications are throttled to prevent email storms:
- **Window**: 1 hour (3600 seconds)
- **Max notifications**: 3 per error type per window
- **Cache key format**: `imap_error_throttle:{error_type}`

## Error Types

- `get_crmimap_exception`: Errors when getting/creating IMAP connection
- `serve_crmimap_exception`: Errors in background IMAP maintenance

## Handling None Returns

`get_crmimap()` returns `None` in the following cases:
- Running in test mode (`settings.TESTING = True`)
- IMAP connection fails
- Exception during connection creation

**Callers MUST handle None**:

```python
crmimap = manager.get_crmimap(email_account, box='INBOX')
if not crmimap:
    logger.error('Failed to get IMAP connection')
    return  # or handle gracefully
```

## Logging

All IMAP operations now log:
- Info: Successful operations
- Warning: Connection failures, noop failures
- Error: Exceptions, critical failures

Use structured logging with context (email_host_user, error details).

## Configuration

Set in Django cache backend for throttling (Redis recommended for production).
