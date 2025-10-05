# Azure Blob Storage Security Improvements

This document describes the security and CORS improvements made to Azure Blob Storage integration in the NalaMap application.

## Overview

The application now uses **time-limited SAS (Shared Access Signature) URLs** instead of public blob URLs for enhanced security, and includes **CORS configuration** to allow the frontend to access blob storage resources.

## Changes Made

### 1. SAS URL Generation for Secure Access

**What changed:**
- Files uploaded to Azure Blob Storage now return time-limited SAS URLs instead of permanent public URLs
- SAS URLs expire after a configurable period (default: 24 hours)
- Only read permission is granted, preventing unauthorized modifications
- Falls back to public URLs if SAS generation fails

**Files modified:**
- `backend/services/storage/file_management.py`
  - Added `_generate_sas_url()` function to create secure URLs
  - Updated `store_file()` to use SAS URLs
  - Updated `store_file_stream()` to use SAS URLs
- `backend/core/config.py`
  - Added `AZURE_SAS_EXPIRY_HOURS` configuration variable

**Benefits:**
- ✅ **Enhanced Security**: URLs automatically expire, limiting exposure window
- ✅ **Access Control**: Only read permission granted via SAS token
- ✅ **Revocable Access**: Can invalidate tokens by rotating storage account keys
- ✅ **No Public Container**: Container can remain private; access granted per-file

### 2. CORS Configuration for Azure Blob Domain

**What changed:**
- Nginx now allows CORS requests from Azure Blob Storage domain
- Configurable via `AZURE_BLOB_DOMAIN` environment variable
- Automatic pattern matching for `*.blob.core.windows.net` domains

**Files modified:**
- `nginx/nginx.conf.envsubst`
  - Added CORS map for Azure Blob Storage domain
  - Supports both specific domain and wildcard pattern matching

**Benefits:**
- ✅ **Fixes CORS Errors**: Frontend can now fetch blob resources without CORS blocks
- ✅ **Flexible Configuration**: Domain configurable per environment
- ✅ **Production Ready**: Works with any Azure storage account

### 3. Docker Compose Configuration

**What changed:**
- All docker-compose files updated with new environment variables
- Backend receives SAS token expiry configuration
- Nginx receives blob domain for CORS configuration

**Files modified:**
- `docker-compose.yml`
- `dev.docker-compose.yml`
- `cloud-test.docker-compose.yml`
- `azure-debug.docker-compose.yml`

## Configuration

### Environment Variables

Add these to your `.env` file or Azure Container Apps environment:

#### Backend (Required for Azure Blob Storage)
```bash
# Enable Azure Blob Storage
USE_AZURE_STORAGE=true
AZURE_CONN_STRING="DefaultEndpointsProtocol=https;AccountName=...;AccountKey=...;EndpointSuffix=core.windows.net"
AZURE_CONTAINER=data

# SAS token expiry (optional, default: 24 hours)
AZURE_SAS_EXPIRY_HOURS=24
```

#### Nginx (Required for CORS)
```bash
# Azure Blob Storage domain for CORS
AZURE_BLOB_DOMAIN=stnalamapdev.blob.core.windows.net

# DNS resolver (optional, default: 8.8.8.8)
DNS_RESOLVER=168.63.129.16
```

### Azure Storage Account Configuration

With SAS URLs, your storage account can have more restrictive settings:

**Recommended Terraform Configuration:**
```hcl
resource "azurerm_storage_container" "data" {
  name                  = "data"
  storage_account_name  = azurerm_storage_account.main.name
  
  # Container can be private since we use SAS URLs
  container_access_type = "private"  # More secure than "blob"
}
```

**If you prefer public access (simpler but less secure):**
```hcl
resource "azurerm_storage_container" "data" {
  name                  = "data"
  storage_account_name  = azurerm_storage_account.main.name
  container_access_type = "blob"  # Public blob access
}

# Must allow public access at storage account level
resource "azurerm_storage_account" "main" {
  # ... other config ...
  allow_nested_items_to_be_public = true
}
```

## Usage Examples

### Upload File and Get SAS URL

```python
from services.storage.file_management import store_file

# Upload file
content = b"GeoJSON content..."
url, file_id = store_file("mydata.json", content)

# URL is now a time-limited SAS URL:
# https://stnalamapdev.blob.core.windows.net/data/abc123_mydata.json?sv=2021-06-08&se=2025-10-06T10%3A30%3A00Z&sr=b&sp=r&sig=...
```

### Stream Upload with SAS URL

```python
from services.storage.file_management import store_file_stream

# Stream large file
with open("large-file.geojson", "rb") as f:
    url, file_id = store_file_stream("large-file.geojson", f)

# Returns SAS URL valid for 24 hours (or configured duration)
```

### Frontend Usage (No Changes Required)

The frontend continues to work as before, but now receives secure SAS URLs:

```javascript
// Upload file
const formData = new FormData();
formData.append('file', file);

const response = await fetch('/api/upload', {
  method: 'POST',
  body: formData
});

const { url, id } = await response.json();

// url is now a SAS URL - frontend can access it directly
// CORS is handled by nginx configuration
fetch(url)  // Works! No CORS error
  .then(res => res.json())
  .then(data => console.log(data));
```

## Security Considerations

### SAS URL Security

**Advantages:**
- ✅ Time-limited access (URLs expire automatically)
- ✅ Specific permissions (read-only in this implementation)
- ✅ Revocable (regenerate storage account keys to invalidate all SAS tokens)
- ✅ No public container required
- ✅ Audit trail via storage account logs

**Limitations:**
- ⚠️ URLs can still be shared (anyone with the URL can access until expiry)
- ⚠️ URL contains token query parameters (longer URLs)
- ⚠️ Not cacheable by CDN (token changes each time)

**Best Practices:**
- Set appropriate expiry time (default 24h is reasonable for most use cases)
- Shorter expiry for sensitive data (e.g., 1-2 hours)
- Longer expiry for public/shared data (e.g., 7 days)
- Monitor storage account metrics for unusual access patterns
- Rotate storage account keys periodically

### CORS Security

**Current Configuration:**
- Nginx allows requests from configured Azure Blob domain
- Uses origin-based matching for security
- Automatically includes all `*.blob.core.windows.net` subdomains

**Recommendations:**
- Always set `AZURE_BLOB_DOMAIN` to your specific storage account domain
- Do not expose blob URLs in public APIs if they contain sensitive data
- Consider implementing blob name obfuscation (already done with UUID prefixes)

## Troubleshooting

### CORS Errors Still Occurring

1. **Verify environment variable is set:**
   ```bash
   echo $AZURE_BLOB_DOMAIN
   # Should output: stnalamapdev.blob.core.windows.net
   ```

2. **Check nginx logs:**
   ```bash
   docker-compose logs nginx | grep CORS
   ```

3. **Test CORS headers:**
   ```bash
   curl -H "Origin: https://your-frontend-domain.com" \
        -I https://stnalamapdev.blob.core.windows.net/data/somefile.json
   ```

### SAS URL Generation Failing

1. **Check connection string format:**
   ```bash
   # Should contain AccountName and AccountKey
   echo $AZURE_CONN_STRING | grep -o "AccountName=[^;]*"
   echo $AZURE_CONN_STRING | grep -o "AccountKey=[^;]*"
   ```

2. **Review backend logs:**
   ```bash
   docker-compose logs backend | grep "Failed to generate SAS"
   ```

3. **Verify azure-storage-blob is installed:**
   ```bash
   docker-compose exec backend pip show azure-storage-blob
   ```

### URLs Expiring Too Quickly/Slowly

Adjust the expiry time:
```bash
# In .env file
AZURE_SAS_EXPIRY_HOURS=48  # 2 days
```

Or pass it to docker-compose:
```bash
AZURE_SAS_EXPIRY_HOURS=12 docker-compose up
```

## Migration Guide

### From Public Blob URLs to SAS URLs

If you're migrating from public blob URLs:

1. **Update environment variables:**
   - Set `AZURE_BLOB_DOMAIN` in nginx config
   - Optionally set `AZURE_SAS_EXPIRY_HOURS` (default: 24)

2. **Deploy changes:**
   - Rebuild and redeploy containers
   - No frontend changes required

3. **Test:**
   - Upload a test file
   - Verify returned URL contains SAS token (`?sv=...&sp=r&sig=...`)
   - Verify frontend can access the URL without CORS errors

4. **Optional: Restrict container access:**
   - Update Terraform to set `container_access_type = "private"`
   - Re-apply Terraform configuration

### Rollback Plan

If issues occur, you can quickly roll back:

1. **Remove SAS URL generation** (temporary fix):
   ```python
   # In file_management.py, revert to public URLs:
   url = f"{container.url}/{unique_name}"  # Instead of _generate_sas_url()
   ```

2. **Ensure container is public:**
   ```hcl
   container_access_type = "blob"
   ```

## Performance Impact

- **SAS URL Generation**: Minimal overhead (~1-2ms per file)
- **No Runtime Impact**: SAS tokens generated once at upload time
- **Frontend**: No performance difference (URLs are the same once generated)
- **Caching**: CDN caching less effective due to query parameters in URL

## Future Improvements

Potential enhancements for consideration:

1. **User-specific SAS tokens**: Different expiry times per user role
2. **Write SAS tokens**: For direct client-side uploads
3. **Container SAS**: For bulk operations
4. **Token refresh endpoint**: Allow frontend to refresh expiring tokens
5. **Blob lifecycle policies**: Auto-delete expired blobs
6. **CDN integration**: Use Azure CDN with SAS token support

## References

- [Azure Blob Storage SAS Documentation](https://learn.microsoft.com/en-us/azure/storage/common/storage-sas-overview)
- [Azure Storage Security Best Practices](https://learn.microsoft.com/en-us/azure/storage/blobs/security-recommendations)
- [CORS Configuration for Azure Storage](https://learn.microsoft.com/en-us/rest/api/storageservices/cross-origin-resource-sharing--cors--support-for-the-azure-storage-services)
