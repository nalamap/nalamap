# Azure Container Apps Configuration

## Issue: 502 Bad Gateway with nginx

The 502 errors occur because nginx is trying to connect to HTTPS URLs instead of internal HTTP URLs in Azure Container Apps.

## Root Cause

In Azure Container Apps:
- **External URLs**: HTTPS (e.g., `https://frontend-app.region.azurecontainerapps.io`)
- **Internal URLs**: HTTP (e.g., `http://frontend-app:3000`)

The nginx container must use internal HTTP URLs to communicate with other containers.

## Solution

### 1. Configure nginx Environment Variables

In your Azure Container Apps configuration, ensure nginx uses internal HTTP URLs:

```yaml
# nginx container environment
BACKEND_PROTOCOL=http
BACKEND_URL=backend-app:8000
FRONTEND_PROTOCOL=http  
FRONTEND_URL=frontend-app:3000
```

**NOT** external HTTPS URLs like:
```yaml
# ❌ WRONG - causes 502 errors
BACKEND_PROTOCOL=https
BACKEND_URL=backend-app.region.azurecontainerapps.io
FRONTEND_PROTOCOL=https
FRONTEND_URL=frontend-app.region.azurecontainerapps.io
```

### 2. Container App Names

Make sure the URLs match your actual container app names:
- Backend app name: `backend-nalamap-dev` → URL: `backend-nalamap-dev:8000`
- Frontend app name: `frontend-nalamap-dev` → URL: `frontend-nalamap-dev:3000`

### 3. Updated nginx Configuration

The nginx configuration has been updated with:
- Proper proxy headers for Azure Container Apps
- Increased timeouts for cloud networking
- Better error handling

### 4. Next.js Body Size Limit

Fixed the 413 error by increasing Next.js server action body size limit to 100MB in `next.config.ts`.

## Deployment Steps

1. **Update nginx environment variables** in Azure Container Apps:
   ```bash
   az containerapp update --name nginx-nalamap-dev --resource-group your-rg \
     --set-env-vars \
     BACKEND_PROTOCOL=http \
     BACKEND_URL=backend-nalamap-dev:8000 \
     FRONTEND_PROTOCOL=http \
     FRONTEND_URL=frontend-nalamap-dev:3000
   ```

2. **Rebuild and deploy** the updated nginx image with the new configuration

3. **Verify internal connectivity** by checking nginx logs for successful proxying

## Debugging

### Check nginx logs
```bash
az containerapp logs show --name nginx-nalamap-dev --resource-group your-rg
```

### Check environment variables
```bash
az containerapp show --name nginx-nalamap-dev --resource-group your-rg --query properties.template.containers[0].env
```

### Test internal connectivity
From within the nginx container, test if backend/frontend are reachable:
```bash
curl http://backend-nalamap-dev:8000/health
curl http://frontend-nalamap-dev:3000
```

## Expected nginx Logs After Fix

Should see successful proxy logs like:
```
2025/09/30 21:06:02 [info] upstream: "http://frontend-nalamap-dev:3000/"
200 response codes instead of 502
```

## Container Apps Networking Notes

- Containers within the same Container Apps Environment can communicate via HTTP on internal ports
- Use the container app name as hostname (not external FQDN)
- External traffic to your apps is automatically terminated with HTTPS by Azure
- Internal container-to-container traffic should use HTTP