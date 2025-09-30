# Runtime Environment Configuration

This document explains how the runtime environment configuration works for cloud deployments where the `/app/public` directory may not have write permissions.

## Problem

In cloud environments, the frontend container may not have write permissions to the `/app/public` directory, preventing the entrypoint script from creating the `runtime-env.js` file that provides dynamic environment configuration to the client-side application.

## Solution

The entrypoint script now supports a configurable path for the runtime environment file:

1. **Environment Variable**: `RUNTIME_ENV_PATH` - specifies where to write the runtime environment file
2. **Fallback Behavior**: If `RUNTIME_ENV_PATH` is not set, it falls back to `/app/public/runtime-env.js`
3. **Symlink Creation**: When using a custom path, a symlink is created from `/app/public/runtime-env.js` to the custom location for backward compatibility

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
5. **Symlink Creation**: If using a custom path, creates a symlink for compatibility
6. **Logging**: Outputs debug information showing which file was created and what values were injected

## File Structure

```
/app/
├── public/
│   └── runtime-env.js -> /app/runtime-env/runtime-env.js (symlink)
└── runtime-env/        (mounted volume in cloud)
    └── runtime-env.js  (actual file)
```

## Testing

The configuration has been tested with:
- Default behavior (writing to `/app/public/runtime-env.js`)
- Custom path behavior (writing to mounted volume)
- Symlink creation for backward compatibility
- Environment variable substitution

## Implementation Status

✅ **Completed**:
- Updated `frontend/entrypoint.sh` with flexible path support
- Added `RUNTIME_ENV_PATH` environment variable to docker-compose configurations
- Added missing `NEXT_PUBLIC_API_UPLOAD_URL` to environment configuration
- Created test configuration for cloud deployment scenario
- Verified functionality with test scripts

🔄 **Next Steps for Cloud Deployment**:
- Configure volume mounting in your cloud infrastructure
- Set `RUNTIME_ENV_PATH=/app/runtime-env/runtime-env.js` environment variable
- Mount writable volume to `/app/runtime-env`