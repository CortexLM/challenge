# Troubleshooting

## Common Issues

### WebSocket Connection Failed

**Error**: `Unable to establish encrypted WebSocket connection`

**Causes**:
- Bootstrap not completed
- TDX attestation failed
- Network connectivity issues
- Platform API/Validator not running

**Solutions**:
1. Ensure bootstrap completed successfully
2. Verify TDX attestation is valid
3. Check network connectivity
4. Verify Platform API/Validator is running and accessible
5. Check logs for specific error messages

---

### Missing SDK Ephemeral Key

**Error**: `SDK_EPHEMERAL_SK_B64 environment variable not set`

**Causes**:
- Bootstrap not completed
- Attestation failed
- Environment variable not set

**Solutions**:
1. Complete bootstrap process
2. Check bootstrap logs for errors
3. Verify attestation endpoint is accessible
4. Ensure `SDK_EPHEMERAL_SK_B64` is set after bootstrap

---

### Credentials Decrypt Failed

**Error**: `credentials decrypt failed`

**Causes**:
- Invalid sealed credentials
- Wrong ephemeral key
- Credentials encrypted with different key

**Solutions**:
1. Verify credentials were encrypted with the correct public key
2. Ensure ephemeral key matches the one used during bootstrap
3. Check that sealed credentials are not corrupted
4. Verify Platform API is sending correct credentials

---

### Database Version Out of Range

**Error**: `Database version out of range`

**Causes**:
- Version not in range 1-16
- Version not set
- Invalid version format

**Solutions**:
1. Check `platform.toml` `[database] version` setting
2. Verify version is between 1 and 16
3. Ensure `challenge.set_db_version()` is called with valid version
4. Check version format is integer

---

### Migration Not Applied

**Issue**: Migrations are not being applied

**Causes**:
- `CHALLENGE_ADMIN=false` (migrations only work with Platform API)
- Migration directory not found
- Migration files not properly formatted

**Solutions**:
1. Ensure `CHALLENGE_ADMIN=true` when connecting Platform API
2. Check that `db/migrations/v{version}/` directory exists
3. Verify migration files are properly formatted
4. Check Platform API logs for migration errors
5. Ensure database version is set correctly

---

### ORM Query Fails

**Error**: ORM query returns error or permission denied

**Causes**:
- Missing ORM permissions
- Table/column not allowed
- Invalid query syntax
- Schema not found

**Solutions**:
1. Set ORM permissions using `challenge.set_orm_permissions()`
2. Verify table and columns are in permissions
3. Check query syntax is correct
4. Ensure schema exists (check migrations)
5. Verify Platform API has applied migrations

---

### Public Endpoint Not Accessible

**Error**: `404 Not Found` or `401 Unauthorized`

**Causes**:
- Endpoint not registered
- `CHALLENGE_ADMIN=false` (public endpoints require Platform API)
- MinerToken verification failed
- Endpoint name mismatch

**Solutions**:
1. Verify `@challenge.api.public()` decorator is used
2. Ensure `CHALLENGE_ADMIN=true` for Platform API
3. Check MinerToken is valid and signed correctly
4. Verify endpoint name matches URL path
5. Check Platform API is proxying requests correctly

---

### Job Handler Not Found

**Error**: `No job handler found for '{job_name}'`

**Causes**:
- Handler not registered
- Job name mismatch
- Default handler not defined

**Solutions**:
1. Register handler with `@challenge.on_job(job_name)`
2. Or register default handler with `@challenge.on_job()`
3. Verify job name matches handler registration
4. Check handler is defined before `run()` is called

---

### Context Not Initialized

**Error**: Context attributes are `None` or not available

**Causes**:
- Context not properly initialized
- Called outside job handler
- Environment variables not set

**Solutions**:
1. Only use Context inside job handlers
2. Verify environment variables are set
3. Check Context is passed correctly to handlers
4. Ensure challenge is in ready state

---

## Debug Mode

Enable development mode for easier debugging:

```bash
SDK_DEV_MODE=true \
CHALLENGE_ADMIN=true \
python my_challenge.py
```

**Development Mode Features**:
- Bypass TDX attestation
- Plain text WebSocket (no encryption)
- Local database support
- Detailed logging
- No security checks

**Warning**: Never use debug mode in production!

## Getting Help

1. Check this troubleshooting guide
2. Review [API Reference](api-reference.md)
3. Check [Usage Guide](usage.md)
4. Review example code in `examples/`
5. Check GitHub issues for similar problems
6. Create a new issue with:
   - Error message
   - Steps to reproduce
   - Environment details
   - Relevant logs

## Logging

Enable detailed logging:

```python
import logging

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
```

## See Also

- [Getting Started](getting-started.md) - Installation guide
- [Usage Guide](usage.md) - Usage examples
- [API Reference](api-reference.md) - API documentation
- [Security](security.md) - Security troubleshooting

