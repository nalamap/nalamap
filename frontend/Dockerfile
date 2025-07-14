# syntax=docker/dockerfile:1

### 1) deps stage: install and cache all dependencies ###
FROM node:22-slim AS deps

WORKDIR /app

# Upgrade npm to v11 specifically to fix TailwindCSS v4 Oxide binary issues
RUN npm install -g npm@11.4.2

# Copy lockfiles & package manifests
COPY package.json yarn.lock* package-lock.json* pnpm-lock.yaml* .npmrc* ./

# Install via the available package manager
RUN \
  if [ -f yarn.lock ]; then yarn install --frozen-lockfile; \
  elif [ -f package-lock.json ]; then npm install; \
  elif [ -f pnpm-lock.yaml ]; then corepack enable pnpm && pnpm install --frozen-lockfile; \
  else echo "Lockfile not found." && exit 1; \
  fi


### 2) builder stage: bring down the build deps & build the app ###
FROM node:22-slim AS builder

WORKDIR /app

# Install only what’s needed to compile any native modules (e.g. SWC, image libs, etc.)
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      python3 \
      build-essential \
      libc6-dev \
 && rm -rf /var/lib/apt/lists/*

# Copy node_modules from deps
COPY --from=deps /app/node_modules ./node_modules

# Copy rest of the project
COPY . .

# Set build-time environment variables for Next.js
ARG NEXT_PUBLIC_API_BASE_URL
ARG NEXT_PUBLIC_API_UPLOAD_URL  
ARG NEXT_PUBLIC_API_AUTO_STYLE_URL
ENV NEXT_PUBLIC_API_BASE_URL=$NEXT_PUBLIC_API_BASE_URL
ENV NEXT_PUBLIC_API_UPLOAD_URL=$NEXT_PUBLIC_API_UPLOAD_URL
ENV NEXT_PUBLIC_API_AUTO_STYLE_URL=$NEXT_PUBLIC_API_AUTO_STYLE_URL

# (Optional) ensure the Tailwind/Linux binary is present—
# now that npm is up to date it should pull in @tailwindcss/oxide-linux-x64-gnu automatically

# Build your Next.js app
RUN \
  if [ -f yarn.lock ]; then yarn build; \
  elif [ -f package-lock.json ]; then npm run build; \
  elif [ -f pnpm-lock.yaml ]; then corepack enable pnpm && pnpm build; \
  else echo "Lockfile not found." && exit 1; \
  fi


### 3) runner stage: production image ###
FROM node:22-slim AS runner

WORKDIR /app
ENV NODE_ENV=production
ENV PORT=3000
ENV NEXT_TELEMETRY_DISABLED=1

# Create a non-root user
RUN groupadd --system nodejs && useradd --system --gid nodejs nextjs    # Copy built output from builder
    COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
    COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static
    # Copy public folder if it exists
    COPY --from=builder --chown=nextjs:nodejs /app/public ./public

# Optional: copy next.config.js if you rely on it at runtime
# COPY next.config.js ./

USER nextjs

EXPOSE 3000

CMD ["node", "server.js"]