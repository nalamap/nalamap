# Azure Storage Account CORS Configuration

## Problem

When the frontend fetches files directly from Azure Blob Storage (e.g., GeoJSON files), the browser blocks the request due to CORS policy:

```
Access to fetch at 'https://stnalamapdev.blob.core.windows.net/data/...' 
from origin 'https://nginx-nalamap-dev.gentlesmoke-040f68e8.germanywestcentral.azurecontainerapps.io' 
has been blocked by CORS policy: No 'Access-Control-Allow-Origin' header is present
```

## Why Nginx CORS Config Doesn't Work

- The frontend makes **direct requests** to Azure Blob Storage
- These requests **never go through nginx**
- Nginx cannot add CORS headers to external services it doesn't proxy

## Solution: Configure CORS on Azure Storage Account

### Option A: Via Azure Portal (Quick Fix)

1. Go to [Azure Portal](https://portal.azure.com)
2. Navigate to your Storage Account (`stnalamapdev`)
3. In the left menu, under **Settings**, click **Resource sharing (CORS)**
4. Select the **Blob service** tab
5. Click **+ Add a rule**
6. Configure:
   - **Allowed origins**: `https://nginx-nalamap-dev.gentlesmoke-040f68e8.germanywestcentral.azurecontainerapps.io`
     - Or use `*` for development (not recommended for production)
   - **Allowed methods**: `GET, HEAD, OPTIONS`
   - **Allowed headers**: `*`
   - **Exposed headers**: `*`
   - **Max age**: `3600` (1 hour)
7. Click **Save**

### Option B: Via Azure CLI

```bash
az storage cors add \
  --services b \
  --methods GET HEAD OPTIONS \
  --origins "https://nginx-nalamap-dev.gentlesmoke-040f68e8.germanywestcentral.azurecontainerapps.io" \
  --allowed-headers "*" \
  --exposed-headers "*" \
  --max-age 3600 \
  --account-name stnalamapdev
```

For multiple origins (dev + prod):
```bash
az storage cors add \
  --services b \
  --methods GET HEAD OPTIONS \
  --origins "https://nginx-nalamap-dev.gentlesmoke-040f68e8.germanywestcentral.azurecontainerapps.io" "https://nginx-nalamap-prod.germanywestcentral.azurecontainerapps.io" \
  --allowed-headers "*" \
  --exposed-headers "*" \
  --max-age 3600 \
  --account-name stnalamapdev
```

### Option C: Via Terraform (Infrastructure as Code)

Add to your storage account Terraform configuration:

```hcl
resource "azurerm_storage_account" "main" {
  name                     = "stnalamapdev"
  resource_group_name      = azurerm_resource_group.main.name
  location                 = azurerm_resource_group.main.location
  account_tier             = "Standard"
  account_replication_type = "LRS"
  
  # Enable public blob access if using SAS URLs
  allow_nested_items_to_be_public = true
  
  # CORS configuration for Blob service
  blob_properties {
    cors_rule {
      allowed_origins    = [
        "https://nginx-nalamap-dev.gentlesmoke-040f68e8.germanywestcentral.azurecontainerapps.io",
        # Add production URL when ready:
        # "https://nginx-nalamap-prod.germanywestcentral.azurecontainerapps.io"
      ]
      allowed_methods    = ["GET", "HEAD", "OPTIONS"]
      allowed_headers    = ["*"]
      exposed_headers    = ["*"]
      max_age_in_seconds = 3600
    }
  }
}
```

Then apply:
```bash
terraform plan
terraform apply
```

## Alternative Solution: Proxy Blob Requests Through Nginx

If you prefer not to configure CORS on Azure Storage (or want more control), you can proxy blob requests through nginx.

### Step 1: Add Nginx Proxy Location

Add to `nginx/nginx.conf.envsubst`:

```nginx
# Proxy Azure Blob Storage requests (alternative to direct access)
location /blob-proxy/ {
  # Remove /blob-proxy/ prefix
  rewrite ^/blob-proxy/(.*)$ /$1 break;
  
  # Proxy to Azure Blob Storage
  proxy_pass https://${AZURE_BLOB_DOMAIN}/;
  
  proxy_http_version 1.1;
  proxy_set_header Host ${AZURE_BLOB_DOMAIN};
  proxy_ssl_server_name on;
  proxy_ssl_name ${AZURE_BLOB_DOMAIN};
  
  # Add CORS headers
  add_header 'Access-Control-Allow-Origin' "$http_origin" always;
  add_header 'Access-Control-Allow-Credentials' 'true' always;
  add_header 'Access-Control-Allow-Methods' 'GET, HEAD, OPTIONS' always;
  add_header 'Access-Control-Allow-Headers' '*' always;
  
  # Handle OPTIONS preflight
  if ($request_method = OPTIONS) {
    add_header 'Access-Control-Allow-Origin' "$http_origin" always;
    add_header 'Access-Control-Allow-Methods' 'GET, HEAD, OPTIONS' always;
    add_header 'Access-Control-Allow-Headers' '*' always;
    add_header 'Access-Control-Max-Age' 86400 always;
    return 204;
  }
  
  # Cache blob responses
  proxy_cache_valid 200 1h;
  proxy_buffering on;
}
```

### Step 2: Update Backend to Return Proxied URLs

Modify `backend/services/storage/file_management.py`:

```python
def _generate_sas_url(blob_url: str, blob_name: str, use_proxy: bool = False) -> str:
    """Generate a time-limited SAS URL for secure blob access.
    
    Args:
        blob_url: The base blob URL
        blob_name: The blob name/path
        use_proxy: If True, return URL through nginx proxy instead of direct
        
    Returns:
        SAS URL with time-limited access token (or proxied URL)
    """
    if use_proxy:
        # Return URL that goes through nginx proxy
        from core.config import BASE_URL
        return f"{BASE_URL}/blob-proxy/{AZ_CONTAINER}/{blob_name}"
    
    # ... existing SAS URL generation code ...
```

### Step 3: Enable Proxy Mode

Add environment variable:
```bash
USE_BLOB_PROXY=true  # Routes blob URLs through nginx
```

## Comparison: Direct Access vs Proxy

| Aspect | Direct Access (CORS on Storage) | Nginx Proxy |
|--------|--------------------------------|-------------|
| **Performance** | ✅ Faster (direct connection) | ⚠️ Slower (extra hop) |
| **Caching** | ✅ CDN/Browser caching works | ✅ Can cache in nginx |
| **Security** | ✅ SAS tokens provide security | ✅ Can add additional auth |
| **CORS Setup** | ⚠️ Need to configure Azure | ✅ Controlled in nginx |
| **Cost** | ✅ Lower bandwidth costs | ⚠️ Higher (goes through nginx) |
| **Complexity** | ✅ Simple (direct URLs) | ⚠️ More complex routing |

## Recommended Approach

**For Production**: Configure CORS on Azure Storage Account (Option C - Terraform)
- Better performance
- Lower costs  
- Proper caching
- Infrastructure as code

**For Quick Testing**: Use Azure Portal (Option A)
- Fastest to implement
- Good for debugging

**For Special Cases**: Use Nginx Proxy
- Need request logging
- Want to add authentication
- Need to transform responses

## Testing CORS Configuration

After configuring CORS on Azure Storage:

### Test with curl
```bash
curl -I \
  -H "Origin: https://nginx-nalamap-dev.gentlesmoke-040f68e8.germanywestcentral.azurecontainerapps.io" \
  "https://stnalamapdev.blob.core.windows.net/data/test.json"

# Should see:
# Access-Control-Allow-Origin: https://nginx-nalamap-dev.gentlesmoke-040f68e8.germanywestcentral.azurecontainerapps.io
```

### Test preflight (OPTIONS)
```bash
curl -X OPTIONS \
  -H "Origin: https://nginx-nalamap-dev.gentlesmoke-040f68e8.germanywestcentral.azurecontainerapps.io" \
  -H "Access-Control-Request-Method: GET" \
  -v \
  "https://stnalamapdev.blob.core.windows.net/data/test.json"
```

### Test in browser console
```javascript
fetch('https://stnalamapdev.blob.core.windows.net/data/test.json', {
  method: 'GET',
  mode: 'cors'
})
.then(r => r.json())
.then(d => console.log('Success:', d))
.catch(e => console.error('CORS Error:', e));
```

## Troubleshooting

### Still Getting CORS Errors After Configuration

1. **Wait a few minutes** - CORS changes can take time to propagate
2. **Clear browser cache** - Old CORS preflight responses may be cached
3. **Check exact origin** - Must match exactly (including https:// and no trailing /)
4. **Verify blob service** - Make sure you configured CORS for "Blob service", not "File service"

### Wildcard Origin Not Working

If using `*` for allowed origins:
- Cannot use `Access-Control-Allow-Credentials: true`
- Some browsers may still block
- Not recommended for production

### OPTIONS Requests Failing

- Ensure `OPTIONS` is in allowed methods
- Check that `Access-Control-Request-Headers` matches allowed headers
- Verify max age is set (prevents too many preflight requests)

## Security Considerations

### Production CORS Configuration

For production, be specific with allowed origins:

```hcl
allowed_origins = [
  "https://yourdomain.com",
  "https://www.yourdomain.com"
]
```

**Never use `*` in production** - this allows any website to access your blobs.

### Combined with SAS URLs

CORS + SAS URLs provide defense in depth:
- **CORS**: Prevents unauthorized domains from accessing blobs in browsers
- **SAS URLs**: Prevents access after token expiry
- **Private Container**: Prevents direct URL guessing

## References

- [Azure Storage CORS Documentation](https://learn.microsoft.com/en-us/rest/api/storageservices/cross-origin-resource-sharing--cors--support-for-the-azure-storage-services)
- [Terraform azurerm_storage_account](https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs/resources/storage_account)
- [MDN CORS Guide](https://developer.mozilla.org/en-US/docs/Web/HTTP/CORS)
