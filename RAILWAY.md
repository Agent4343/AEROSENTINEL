# Deploying AeroSentinel on Railway

## Architecture on Railway

```
┌─────────────────────────────────────────────────────────┐
│                    Railway Project                       │
│                                                         │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────┐ │
│  │ Backend  │  │ Frontend │  │PostgreSQL│  │ Redis  │ │
│  │ (FastAPI)│  │ (React)  │  │ (Plugin) │  │(Plugin)│ │
│  └──────────┘  └──────────┘  └──────────┘  └────────┘ │
│                                                         │
│  Optional:                                              │
│  ┌──────────┐  ┌──────────┐                            │
│  │  EMQX    │  │  MinIO   │                            │
│  │ (Docker) │  │ (Docker) │                            │
│  └──────────┘  └──────────┘                            │
└─────────────────────────────────────────────────────────┘
```

## Step-by-Step Setup

### 1. Create Railway Project

1. Go to [railway.app](https://railway.app) and create a new project
2. Connect your GitHub repo (`agent4343/aerosentinel`)

### 2. Add PostgreSQL

1. Click **"+ New"** → **"Database"** → **"PostgreSQL"**
2. Railway auto-provisions and sets `DATABASE_URL`
3. The backend auto-converts `postgres://` → `postgresql+asyncpg://`

### 3. Add Redis

1. Click **"+ New"** → **"Database"** → **"Redis"**
2. Railway auto-provisions and sets `REDIS_URL`

### 4. Deploy Backend

1. Click **"+ New"** → **"GitHub Repo"** → select `aerosentinel`
2. Set **Root Directory** to `backend`
3. Railway detects the Dockerfile automatically
4. Add these **environment variables**:

| Variable | Value |
|----------|-------|
| `DATABASE_URL` | `${{Postgres.DATABASE_URL}}` (Railway reference) |
| `REDIS_URL` | `${{Redis.REDIS_URL}}` (Railway reference) |
| `SECRET_KEY` | Generate a random 64-char string |
| `ALLOWED_ORIGINS` | `https://your-frontend.up.railway.app` |
| `MQTT_ENABLED` | `false` (unless you deploy EMQX) |
| `REDIS_ENABLED` | `true` |
| `DEBUG` | `false` |

5. Deploy and note the public URL (e.g. `https://aerosentinel-backend.up.railway.app`)

### 5. Deploy Frontend

1. Click **"+ New"** → **"GitHub Repo"** → select `aerosentinel` again
2. Set **Root Directory** to `frontend`
3. Add these **build arguments** as environment variables:

| Variable | Value |
|----------|-------|
| `REACT_APP_API_BASE_URL` | `https://your-backend.up.railway.app` |
| `REACT_APP_WS_BASE_URL` | `wss://your-backend.up.railway.app` |
| `REACT_APP_MAPBOX_TOKEN` | Your Mapbox public token |
| `PORT` | `80` |

### 6. (Optional) Deploy EMQX MQTT Broker

Only needed if connecting real DJI drones:

1. Click **"+ New"** → **"Docker Image"**
2. Image: `emqx/emqx:5.8`
3. Add port mapping: `1883` (MQTT TCP)
4. Set env vars:
   - `EMQX_DASHBOARD__DEFAULT_USERNAME=admin`
   - `EMQX_DASHBOARD__DEFAULT_PASSWORD=your-password`
5. Update backend env vars:
   - `MQTT_ENABLED=true`
   - `MQTT_BROKER_HOST=${{EMQX.RAILWAY_PRIVATE_DOMAIN}}`
   - `MQTT_BROKER_PORT=1883`

### 7. (Optional) Object Storage

For media uploads, use one of:
- **Cloudflare R2** (S3-compatible, generous free tier)
- **AWS S3**
- **MinIO on Railway** (Docker image `minio/minio`)

Set these backend env vars:
```
S3_ENDPOINT_URL=https://your-r2-endpoint.r2.cloudflarestorage.com
S3_ACCESS_KEY=your-access-key
S3_SECRET_KEY=your-secret-key
S3_BUCKET_NAME=aerosentinel-media
S3_REGION=auto
```

## Environment Variable Reference

### Required
| Variable | Service | Description |
|----------|---------|-------------|
| `DATABASE_URL` | Backend | PostgreSQL connection string (auto-set by Railway) |
| `SECRET_KEY` | Backend | App secret for sessions/tokens |
| `ALLOWED_ORIGINS` | Backend | Frontend URL for CORS |
| `REACT_APP_API_BASE_URL` | Frontend | Backend public URL |
| `REACT_APP_MAPBOX_TOKEN` | Frontend | Mapbox GL access token |

### Optional
| Variable | Default | Description |
|----------|---------|-------------|
| `REDIS_URL` | — | Redis connection string (auto-set by Railway) |
| `REDIS_ENABLED` | `true` | Set `false` to skip Redis |
| `MQTT_ENABLED` | `true` | Set `false` to skip MQTT |
| `MQTT_BROKER_HOST` | `localhost` | EMQX hostname |
| `S3_ENDPOINT_URL` | — | S3-compatible storage endpoint |
| `DEBUG` | `false` | Enable debug logging |

## Estimated Costs

| Service | Railway Plan | Est. Cost |
|---------|-------------|-----------|
| PostgreSQL | Hobby | ~$5/mo |
| Redis | Hobby | ~$5/mo |
| Backend | Hobby | ~$5/mo |
| Frontend | Hobby | ~$5/mo |
| **Total (core)** | | **~$20/mo** |
| EMQX (optional) | Hobby | ~$7/mo |
| MinIO (optional) | Hobby | ~$5/mo |

Railway's free trial gives $5 credit which covers initial testing.
