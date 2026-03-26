# Java Heap Dump & Thread Dump Analyzer

A web-based tool for analyzing Java Heap Dumps (`.hprof`) and Thread Dumps (`.txt` / jstack output), running entirely in Docker.

## Prerequisites

- Docker 24+
- Docker Compose v2

## How to Run

```bash
cp .env.example .env
docker compose up --build
```

## URLs

| Service       | URL                                      |
|--------------|------------------------------------------|
| Frontend      | http://localhost                         |
| API Docs      | http://localhost:8000/docs               |
| MinIO Console | http://localhost:9001                    |

## Generating Test Files

### Heap Dump

```bash
# Find the PID of the Java process
jps -l

# Generate heap dump
jmap -dump:format=b,file=heap.hprof <pid>
```

### Thread Dump

```bash
# Find the PID of the Java process
jps -l

# Generate thread dump
jstack <pid> > threads.txt
```

## Architecture

| Container  | Port | Responsibility                                          |
|------------|------|---------------------------------------------------------|
| frontend   | 80   | React + Vite served by Nginx. Proxy /api/* → backend   |
| api        | 8000 | FastAPI (Python 3.12). Upload, jobs, history            |
| worker     | —    | Celery worker. Consumes jobs from Redis, runs analyzer  |
| analyzer   | —    | JVM (OpenJDK 17) + Eclipse MAT headless + Python parser |
| redis      | 6379 | Celery broker + cache                                   |
| postgres   | 5432 | Metadata, history, JSON results                         |
| minio      | 9000 | S3-compatible object storage for .hprof and .txt files  |
