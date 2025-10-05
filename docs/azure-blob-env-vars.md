# Azure Blob Storage - Environment Variable Reference

Quick reference for configuring Azure Blob Storage with SAS URLs and CORS support.

## Required Environment Variables

### For Backend (Azure Blob Storage)

```bash
# Enable Azure Blob Storage
USE_AZURE_STORAGE=true

# Azure Storage Account connection string (from Azure Portal)
AZURE_CONN_STRING="DefaultEndpointsProtocol=https;AccountName=stnalamapdev;AccountKey=your-key-here;EndpointSuffix=core.windows.net"

# Container name (created in Terraform/Azure Portal)
AZURE_CONTAINER=data
```

### For Nginx (CORS Support)

```bash
# Azure Blob Storage domain (format: <account-name>.blob.core.windows.net)
AZURE_BLOB_DOMAIN=stnalamapdev.blob.core.windows.net

# DNS resolver for Azure Container Apps (optional)
DNS_RESOLVER=168.63.129.16
```

## Optional Environment Variables

### Backend

```bash
# SAS token expiry time in hours (default: 24)
# Shorter for sensitive data, longer for public data
AZURE_SAS_EXPIRY_HOURS=24

# Local fallback directory (when not using Azure)
LOCAL_UPLOAD_DIR=./uploads

# Base URL for local uploads (when not using Azure)
BASE_URL=http://localhost:8000
```

## Example `.env` File

Create a `.env` file in the project root:

```bash
# Azure Blob Storage Configuration
USE_AZURE_STORAGE=true
AZURE_CONN_STRING="DefaultEndpointsProtocol=https;AccountName=stnalamapdev;AccountKey=abcdef1234567890...;EndpointSuffix=core.windows.net"
AZURE_CONTAINER=data
AZURE_SAS_EXPIRY_HOURS=24

# Nginx CORS Configuration
AZURE_BLOB_DOMAIN=stnalamapdev.blob.core.windows.net
DNS_RESOLVER=168.63.129.16

# Other configuration...
DATABASE_AZURE_URL=postgresql://...
OPENAI_API_KEY=sk-...
```

## Azure Container Apps Configuration

When deploying to Azure Container Apps, set these as container environment variables:

### Backend Container

| Variable | Value | Secret? |
|----------|-------|---------|
| `USE_AZURE_STORAGE` | `true` | No |
| `AZURE_CONN_STRING` | `DefaultEndpointsProtocol=https;AccountName=...` | **Yes** |
| `AZURE_CONTAINER` | `data` | No |
| `AZURE_SAS_EXPIRY_HOURS` | `24` | No |

### Nginx Container

| Variable | Value | Secret? |
|----------|-------|---------|
| `AZURE_BLOB_DOMAIN` | `stnalamapdev.blob.core.windows.net` | No |
| `DNS_RESOLVER` | `168.63.129.16` | No |
| `BACKEND_PROTOCOL` | `http` | No |
| `BACKEND_URL` | `backend:8000` | No |
| `FRONTEND_PROTOCOL` | `http` | No |
| `FRONTEND_URL` | `frontend:3000` | No |

## Getting Your Azure Connection String

### Via Azure Portal

1. Navigate to your Storage Account
2. Go to **Security + networking** → **Access keys**
3. Click **Show keys**
4. Copy **Connection string** from key1 or key2

### Via Azure CLI

```bash
az storage account show-connection-string \
  --name stnalamapdev \
  --resource-group rg-nalamap-dev \
  --query connectionString \
  --output tsv
```

## Determining Your Blob Domain

The blob domain follows this pattern:
```
<storage-account-name>.blob.core.windows.net
```

For example:
- Storage account name: `stnalamapdev`
- Blob domain: `stnalamapdev.blob.core.windows.net`

### Via Azure CLI

```bash
az storage account show \
  --name stnalamapdev \
  --resource-group rg-nalamap-dev \
  --query "primaryEndpoints.blob" \
  --output tsv
```

Output: `https://stnalamapdev.blob.core.windows.net/`

Use the domain without `https://` and trailing `/`:
```bash
AZURE_BLOB_DOMAIN=stnalamapdev.blob.core.windows.net
```

## Testing Configuration

### Test Backend Connection

```bash
# Start containers
docker-compose up -d backend

# Check backend logs
docker-compose logs backend | grep -i azure

# Test by uploading a file via API
curl -X POST http://localhost:8000/api/upload \
  -F "file=@test.json"

# Response should contain SAS URL with token
# Example: https://stnalamapdev.blob.core.windows.net/data/abc123_test.json?sv=2021...
```

### Test CORS Configuration

```bash
# Start nginx
docker-compose up -d nginx

# Test CORS preflight
curl -X OPTIONS http://localhost/api/upload \
  -H "Origin: https://your-frontend-domain.com" \
  -H "Access-Control-Request-Method: POST" \
  -v

# Should see Access-Control-Allow-Origin header in response
```

### Test SAS URL Access

```bash
# Upload a file
UPLOAD_RESPONSE=$(curl -s -X POST http://localhost:8000/api/upload -F "file=@test.json")
SAS_URL=$(echo $UPLOAD_RESPONSE | jq -r '.url')

# Access the SAS URL
curl -I "$SAS_URL"

# Should return 200 OK (or 404 if file doesn't exist)
```

## Troubleshooting

### Error: "Public access is not permitted"

**Problem**: Container access type is set to private, but trying to use public URLs.

**Solution**: Ensure SAS URL generation is working (check for `?sv=` in URLs).

### Error: "CORS policy: No 'Access-Control-Allow-Origin' header"

**Problem**: `AZURE_BLOB_DOMAIN` not set or nginx not restarted.

**Solution**:
```bash
# Set environment variable
export AZURE_BLOB_DOMAIN=stnalamapdev.blob.core.windows.net

# Restart nginx
docker-compose restart nginx

# Verify environment variable is passed
docker-compose exec nginx env | grep AZURE_BLOB_DOMAIN
```

### Error: "Failed to generate SAS URL"

**Problem**: Connection string missing `AccountName` or `AccountKey`.

**Solution**: Verify connection string format:
```bash
echo $AZURE_CONN_STRING | grep "AccountName="
echo $AZURE_CONN_STRING | grep "AccountKey="
```

### SAS URLs Not Generated (Public URLs Returned)

**Problem**: `azure-storage-blob` package not installed or import failing.

**Solution**:
```bash
# Check if package is installed
docker-compose exec backend pip show azure-storage-blob

# Rebuild backend if needed
docker-compose build backend
docker-compose up -d backend
```

## Security Checklist

- [ ] `AZURE_CONN_STRING` stored as secret (not in version control)
- [ ] `AZURE_SAS_EXPIRY_HOURS` set appropriately for your use case
- [ ] Storage account access keys rotated regularly
- [ ] Container access type set based on your security requirements
- [ ] Blob domain configured correctly in nginx
- [ ] Test SAS URLs expire as expected
- [ ] Monitor storage account for unusual access patterns

## Environment-Specific Examples

### Development (Local Docker)

```bash
USE_AZURE_STORAGE=false
LOCAL_UPLOAD_DIR=./uploads
BASE_URL=http://localhost:8000
```

### Development (Azure Dev)

```bash
USE_AZURE_STORAGE=true
AZURE_CONN_STRING="DefaultEndpointsProtocol=https;AccountName=stnalamapdev;AccountKey=..."
AZURE_CONTAINER=data
AZURE_SAS_EXPIRY_HOURS=24
AZURE_BLOB_DOMAIN=stnalamapdev.blob.core.windows.net
```

### Production

```bash
USE_AZURE_STORAGE=true
AZURE_CONN_STRING="DefaultEndpointsProtocol=https;AccountName=stnalamapprod;AccountKey=..."
AZURE_CONTAINER=data
AZURE_SAS_EXPIRY_HOURS=48
AZURE_BLOB_DOMAIN=stnalamapprod.blob.core.windows.net
DNS_RESOLVER=168.63.129.16
```

## Related Documentation

- [Azure Blob Storage Security Improvements](./azure-blob-storage-security.md) - Detailed documentation
- [Runtime Environment](./runtime-environment.md) - Environment variable handling
- [Azure Container Apps Config](./azure-container-apps-config.md) - Deployment configuration
