# Deploy the free demo

`docker compose up -d` is the local stack and is unchanged. This page is the hosted portfolio demo: Aiven for Kafka, Postgres, and Valkey, one Hugging Face Space for the Python processes, and Vercel for the console.

You create the accounts and paste the secrets. Nothing in this repo deploys itself.

## What you create

| Account | Plan | Role |
|---|---|---|
| [Aiven](https://aiven.io) | Free Kafka, free PostgreSQL, free Valkey | Broker, database, vehicle state |
| [Hugging Face](https://huggingface.co) | Spaces, Docker SDK, free CPU | Toll processor, billing API, OBU simulator |
| [Vercel](https://vercel.com) | Hobby | Operations console and the API-key proxy |

One Aiven organization can hold one free service of each type. No credit card is required for these free plans.

Postgres stays on Aiven. The free PostgreSQL plan includes extensions, and Aiven lists PostGIS on that plan. The processor already runs `CREATE EXTENSION IF NOT EXISTS postgis` and seeds Kherki Daula and Shahjahanpur. Supabase is not required. If enabling PostGIS on Aiven fails, a Supabase free project also has PostGIS: use its connection string as `DATABASE_URL` with `sslmode=require`. The rest of this page stays the same.

## Topics

Aiven free Kafka allows 5 topics, 2 partitions each, about 250 KiB/s, and replication that fits a single broker. Auto-create is off. These five topics are the whole budget:

| Topic | Partitions | Replication | Who uses it |
|---|---|---|---|
| `smarttoll.gps.raw.v1` | 2 | 1 | Simulator writes, processor reads |
| `smarttoll.toll.events.v1` | 2 | 1 | Processor writes, billing reads |
| `smarttoll.payment.events.v1` | 2 | 1 | Billing writes |
| `smarttoll.billing.dlq.v1` | 2 | 1 | Billing dead letter |
| `smarttoll.processor.errors.v1` | 2 | 1 | Processor errors |

Do not turn on the schema registry in a way that creates a `_schemas` topic. That would be a sixth topic and the plan rejects it.

Create them once, from this repo, after Kafka is Running. Export the Kafka variables from the table below, then:

```bash
python scripts/create_topics.py
```

The script is safe to run again. A topic that already exists is skipped.

The Space image sets `SIM_SEND_INTERVAL_SECONDS=10`. One small GPS JSON every 10 seconds is far under 250 KiB/s, and the processor keeps consuming, so the broker sees traffic while the Space is awake.

## Wake a service that powered off

Aiven powers a free Kafka service off after 24 hours with no produce and no consume, and the messages on the topics are gone. Free Postgres and Valkey can power off after inactivity too. A free Hugging Face Space sleeps when nobody requests it, which stops the simulator and then the 24 hour Kafka clock can run out.

When the demo is dark:

1. In the Aiven Console, open Kafka, Postgres, and Valkey and choose Power on. Wait until each status is Running.
2. If `python scripts/create_topics.py` reports that a topic is missing, run it again. Empty topics do not need to be recreated. Zones are seeded again by the processor when it connects. Billing migrations run again on startup and are a no-op once applied.
3. Open the Space URL (or the Vercel console, which calls the Space). That wakes the container. The three processes retry Kafka, Postgres, and Valkey until they connect.

## Hugging Face Space

The repo root `Dockerfile` is the Space image. `docker compose` does not use it. The image runs supervisord as uid 1000 and listens on 7860:

- nginx on 7860, proxying `/api`, `/processor`, and `/simulator`
- billing on 127.0.0.1:8000 (Alembic `upgrade head`, then Uvicorn)
- toll processor on 127.0.0.1:8080
- OBU simulator, one fix every 10 seconds

nginx forwards `X-API-KEY`. It does not invent one. A request to the Space's `/api` without that header is rejected by billing. `/processor` and `/simulator` stay open, matching the local processor and simulator ports. `GET /` on the Space returns a short JSON document so the Space page is not blank.

The YAML block at the top of `README.md` sets `sdk: docker` and `app_port: 7860`. Hugging Face reads that when this GitHub repo is the Space.

Create the Space:

1. New Space, SDK Docker, free CPU.
2. Connect this GitHub repository and let it build the root `Dockerfile`.
3. Add the secrets in the next section under Space settings. They are environment variables, not files in the image.
4. Wait until the build is healthy, then open `https://<user>-<space>.hf.space/`.

Paste the CA certificate into `KAFKA_SSL_CA_PEM` as the PEM text. Newlines can be real line breaks or the two characters `\n`. A client certificate is optional. Use it only if you choose SSL instead of SASL.

Enable SASL on the Kafka service if the connection page does not already show a SASL port. New Aiven Kafka services enable SASL, with `SCRAM-SHA-256` and `PLAIN` available. This demo defaults to `SCRAM-SHA-256`. The CA from the Aiven overview is still required, because the project CA is not in the public trust store.

Enable the `postgis` extension on the Postgres service before the first Space boot (service settings, extensions). The processor's `CREATE EXTENSION` then succeeds.

Recommended pool sizes on the Space, because free Postgres allows 20 connections:

- `POSTGRES_POOL_MIN=1`
- `POSTGRES_POOL_MAX=2`
- `POSTGRES_POOL_SIZE=2`
- `POSTGRES_MAX_OVERFLOW=0`

## Vercel

Create a project from this repo. Set the root directory to `frontend`. Framework is Vite. `frontend/vercel.json` builds `dist` and routes `/api` to `frontend/api/[...path].js`. `/processor` and `/simulator` are rewritten onto that function.

Set only these two secrets. Do not create any `VITE_` variable. A `VITE_` value is compiled into the browser bundle.

- `HF_BACKEND_URL`: the Space origin, for example `https://<user>-<space>.hf.space`, with no path and no trailing slash
- `SERVICE_API_KEY`: the same value as on the Space

The browser calls same-origin `/api`, `/processor`, and `/simulator`. The function adds `X-API-KEY` on `/api` and streams the response body. The console's EventSource already reconnects two seconds after an error.

### SSE and the API key

Vercel Hobby functions stream, including Server-Sent Events, and they are capped at 300 seconds. A map or ledger stream therefore drops about every five minutes and the console reconnects. That is the tradeoff that keeps the key on the server.

Sending EventSource straight to the Space would avoid the 300 second cap, but the Space would have to accept those streams without a header the browser cannot safely hold. Billing would then be readable by anyone who knows the Space URL. The proxy keeps billing behind `SERVICE_API_KEY`. Processor map data is still reachable on the Space URL, the same way the local processor port is open.

## Environment variables

Leave these unset for local Compose. `.env.example` lists them as comments.

### Hugging Face Space

| Variable | Example | Required |
|---|---|---|
| `KAFKA_BROKER` | `kafka-demo.aivencloud.com:17000` | yes |
| `KAFKA_SECURITY_PROTOCOL` | `SASL_SSL` (image default) or `SSL` | yes for Aiven |
| `KAFKA_SASL_MECHANISM` | `SCRAM-SHA-256` or `PLAIN` | yes when the protocol is `SASL_SSL` |
| `KAFKA_SASL_USERNAME` | `avnadmin` | yes for SASL |
| `KAFKA_SASL_PASSWORD` | from the Aiven service user | yes for SASL |
| `KAFKA_SSL_CA_PEM` | contents of the Aiven CA PEM | yes for `SASL_SSL` and `SSL` |
| `KAFKA_SSL_CERT_PEM` | Aiven client certificate | only for `SSL` client auth |
| `KAFKA_SSL_KEY_PEM` | Aiven client private key | only for `SSL` client auth |
| `KAFKA_SSL_CHECK_HOSTNAME` | `true` | no |
| `DATABASE_URL` | `postgresql://avnadmin:PASSWORD@HOST:PORT/defaultdb?sslmode=require` | yes |
| `REDIS_URL` | `rediss://default:PASSWORD@HOST:PORT` | yes |
| `SERVICE_API_KEY` | a long random string, same as Vercel | yes |
| `PAYMENT_GATEWAY` | `mock` | no, this is the default |
| `SIM_SEND_INTERVAL_SECONDS` | `10` | no, the image sets 10 |
| `SIM_VEHICLE_ID` | `HR26DK8481` | no |
| `POSTGRES_POOL_MIN` / `POSTGRES_POOL_MAX` | `1` / `2` | recommended |
| `POSTGRES_POOL_SIZE` / `POSTGRES_MAX_OVERFLOW` | `2` / `0` | recommended |

`KAFKA_SSL_CA_FILE`, `KAFKA_SSL_CERT_FILE`, and `KAFKA_SSL_KEY_FILE` work instead of the `*_PEM` values when a path inside the container exists. Secrets on a Space are environment variables, so the PEM form is the one to use.

An Upstash Redis database is the same `REDIS_URL` (`rediss://`). Aiven Valkey is the default so Kafka, Postgres, and Redis live on one account.

### Vercel

| Variable | Example | Required |
|---|---|---|
| `HF_BACKEND_URL` | `https://<user>-<space>.hf.space` | yes |
| `SERVICE_API_KEY` | same string as the Space | yes |

### Laptop, only while creating topics

Export `KAFKA_BROKER`, `KAFKA_SECURITY_PROTOCOL`, `KAFKA_SASL_MECHANISM`, `KAFKA_SASL_USERNAME`, `KAFKA_SASL_PASSWORD`, and `KAFKA_SSL_CA_PEM`, then run `python scripts/create_topics.py`. Those values never go in git.

## Check that it is up

1. Space `GET /` returns JSON.
2. Space `GET /processor/health/live` returns 200. Readiness stays 503 until Kafka, Postgres, and Valkey accept connections.
3. Vercel URL loads the console. Billing live and the map stream show as up. After the simulated car leaves Kherki Daula, the ledger shows a 105 rupee SUCCESS row. Shahjahanpur is 205 rupees. The drive is 97.5 km at one point every 10 seconds, so the first charge is not instant.
4. `curl` to the Space `/api/v1/transactions` without `X-API-KEY` returns 401. The same path on the Vercel domain succeeds, which shows the key was added on the server.
