# Runtime Environment Configuration

This document explains how the runtime environment configuration works for cloud deployments where the `/app/public` directory may not have write permissions.

## Problem

In cloud environments, the frontend container may not have write permissions to the `/app/public` directory, preventing the entrypoint script from creating the `runtime-env.js` file that provides dynamic environment configuration to the client-side application.

## Solution

The entrypoint script now supports a configurable path for the runtime environment file, and the frontend uses an API route to serve the configuration:

1. **Environment Variable**: `RUNTIME_ENV_PATH` - specifies where to write the runtime environment file
2. **Fallback Behavior**: If `RUNTIME_ENV_PATH` is not set, it falls back to `/app/public/runtime-env.js`
3. **API Route**: `/runtime-env.js` route serves the configuration from the correct location, eliminating the need for symlinks
4. **Permission Safe**: No symlink creation needed, avoiding permission issues in cloud environments

## Usage

### Local Development
No changes needed. The script will continue to write to `/app/public/runtime-env.js` by default.

### Cloud Deployment
Set the `RUNTIME_ENV_PATH` environment variable and mount a writable volume:

```yaml
services:
  frontend:
    environment:
      - RUNTIME_ENV_PATH=/app/runtime-env/runtime-env.js
    volumes:
      # Mount a writable directory for runtime environment files
      - runtime-env-data:/app/runtime-env
```

### Environment Variables

The script processes these environment variables:

- `NEXT_PUBLIC_API_BASE_URL` - API base URL for the frontend
- `NEXT_PUBLIC_API_UPLOAD_URL` - Upload endpoint URL  
- `NEXT_PUBLIC_BACKEND_URL` - Backend service URL
- `RUNTIME_ENV_PATH` - Custom path for runtime environment file (optional)

## How It Works

1. **Entrypoint Execution**: When the container starts, `entrypoint.sh` runs before the main application
2. **Path Determination**: The script checks if `RUNTIME_ENV_PATH` is set, otherwise uses the default path
3. **Directory Creation**: Ensures the target directory exists using `mkdir -p`
4. **File Generation**: Creates the JavaScript file with runtime configuration
5. **API Route Serving**: The `/runtime-env.js` API route reads from the correct location and serves the configuration
6. **Fallback Handling**: If the file can't be read, the API route provides fallback configuration using environment variables
7. **Logging**: Outputs debug information showing which file was created and what values were injected

## File Structure

```
/app/
├── app/
│   └── runtime-env.js/
│       └── route.ts        (API route that serves the configuration)
├── public/
│   └── (no runtime-env.js needed - served by API route)
└── runtime-env/           (mounted volume in cloud)
    └── runtime-env.js     (actual file written by entrypoint)
```

## Testing

The configuration has been tested with:
- Default behavior (writing to `/app/public/runtime-env.js`)
- Custom path behavior (writing to mounted volume)
- Symlink creation for backward compatibility
- Environment variable substitution

## Implementation Status

✅ **Completed**:
- Updated `frontend/entrypoint.sh` with flexible path support (no symlink creation)
- Added `RUNTIME_ENV_PATH` environment variable to docker-compose configurations
- Created `/runtime-env.js` API route to serve configuration from any location
- Added missing `NEXT_PUBLIC_API_UPLOAD_URL` to environment configuration
- Created test configuration for cloud deployment scenario
- Eliminated permission issues with symlink creation
- Added fallback configuration in API route for robustness

🔄 **Next Steps for Cloud Deployment**:
- Configure volume mounting in your cloud infrastructure
- Set `RUNTIME_ENV_PATH=/app/runtime-env/runtime-env.js` environment variable
- Mount writable volume to `/app/runtime-env`