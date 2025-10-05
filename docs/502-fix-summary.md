# 502 Bad Gateway Fix Summary

## Problem Diagnosis

Based on the nginx logs, the 502 errors were caused by:

1. **Incorrect Protocol Configuration**: nginx was trying to connect to upstream services using HTTPS instead of HTTP
   - Log showed: `upstream: "https://100.100.226.124:443/"`
   - But containers run HTTP internally on ports 3000/8000

2. **Missing Proxy Headers**: Azure Container Apps networking requires proper proxy headers for internal communication

3. **Next.js Body Size Limit**: 413 errors due to 1MB default limit for server actions

## Fixes Applied

### 1. Updated nginx Configuration (`nginx/nginx.conf.envsubst`)
- Added proper proxy headers for Azure Container Apps:
  - `X-Real-IP`
  - `X-Forwarded-For` 
  - `X-Forwarded-Proto`
- Added connection timeouts for cloud networking
- Enhanced upload timeout configuration

### 2. Fixed Next.js Body Size Limit (`frontend/next.config.ts`)
- Increased server action body size limit from 1MB to 100MB
- Matches nginx's `client_max_body_size 100M`

### 3. Added Health Check Endpoint (`backend/main.py`)
- Added `/health` endpoint for container health checks
- Useful for debugging and monitoring

### 4. Created Debug Configuration (`azure-debug.docker-compose.yml`)
- Mirrors Azure Container Apps setup for local testing
- Includes health checks and proper networking
- Uses internal HTTP URLs like Azure Container Apps

## Required Azure Container Apps Configuration

**Critical**: Ensure nginx environment variables use internal HTTP URLs:

```bash
# ✅ CORRECT - Internal container communication
BACKEND_PROTOCOL=http
BACKEND_URL=backend-nalamap-dev:8000
FRONTEND_PROTOCOL=http  
FRONTEND_URL=frontend-nalamap-dev:3000

# ❌ WRONG - External HTTPS URLs cause 502 errors
BACKEND_PROTOCOL=https
BACKEND_URL=backend-nalamap-dev.region.azurecontainerapps.io
```

## Deployment Commands

Update nginx environment in Azure Container Apps:
```bash
az containerapp update --name nginx-nalamap-dev --resource-group your-rg \
  --set-env-vars \
  BACKEND_PROTOCOL=http \
  BACKEND_URL=backend-nalamap-dev:8000 \
  FRONTEND_PROTOCOL=http \
  FRONTEND_URL=frontend-nalamap-dev:3000
```

## Testing

1. **Build and Deploy**: Use the updated Docker images from your PR
2. **Check nginx Logs**: Should show `upstream: "http://..."` instead of `https://...`
3. **Test Endpoints**:
   - Frontend: Should load without 502 errors
   - Backend API: `/api/` requests should proxy correctly
   - Uploads: Large file uploads should work without 413 errors

## Expected Results

After applying these fixes:
- ✅ No more 502 Bad Gateway errors
- ✅ Proper internal HTTP communication between containers
- ✅ Support for file uploads up to 100MB
- ✅ Improved reliability with proper timeouts and headers