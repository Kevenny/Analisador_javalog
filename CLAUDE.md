# Java Heap Dump & Thread Dump Analyzer

## Objetivo

Construir um sistema web completo para análise de Heap Dumps e Thread Dumps Java, rodando inteiramente em Docker. O usuário acessa via browser, faz upload dos arquivos e recebe análises detalhadas.

---

## Tarefa

Crie o scaffold completo do projeto conforme a arquitetura abaixo. Gere **todos os arquivos** com código funcional — não use placeholders como `# TODO` ou `pass`. Cada serviço deve estar pronto para rodar com `docker compose up`.

---

## Arquitetura

### Containers (docker-compose.yml)

| Container  | Porta | Responsabilidade |
|------------|-------|-----------------|
| frontend   | 80    | React + Vite servido por Nginx. Proxy /api/* → backend:8000 |
| api        | 8000  | FastAPI (Python 3.12). Upload, jobs, histórico |
| worker     | —     | Celery worker. Consome jobs do Redis, aciona analyzer |
| analyzer   | —     | JVM (OpenJDK 17) + Eclipse MAT headless + parser Python |
| redis      | 6379  | Broker Celery + cache |
| postgres   | 5432  | Metadados, histórico, resultados JSON |
| minio      | 9000  | Object storage S3-compatible para arquivos .hprof e .txt |

---

## Estrutura de pastas a criar

```
java-dump-analyzer/
├── docker-compose.yml
├── .env.example
├── README.md
├── frontend/
│   ├── Dockerfile
│   ├── nginx.conf
│   ├── package.json
│   ├── vite.config.ts
│   ├── tailwind.config.js
│   ├── index.html
│   └── src/
│       ├── main.tsx
│       ├── App.tsx
│       ├── api/
│       │   └── client.ts          # React Query hooks: useUpload, useAnalysis, useHistory
│       ├── components/
│       │   ├── UploadZone.tsx      # drag & drop com progresso de upload
│       │   ├── AnalysisStatus.tsx  # polling de status do job
│       │   ├── HeapReport.tsx      # dashboard heap dump
│       │   └── ThreadReport.tsx    # dashboard thread dump
│       └── pages/
│           ├── Home.tsx
│           └── Analysis.tsx
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app/
│       ├── main.py                 # FastAPI app, CORS, routers
│       ├── config.py               # settings via pydantic-settings
│       ├── database.py             # SQLAlchemy engine + session
│       ├── models.py               # Analysis model (id, filename, type, status, result_json, created_at)
│       ├── schemas.py              # Pydantic schemas
│       ├── routers/
│       │   ├── upload.py           # POST /api/upload (multipart, salva no MinIO, cria job)
│       │   ├── analysis.py         # GET /api/analysis/{id}, GET /api/analyses
│       │   └── ws.py               # WebSocket /api/ws/{job_id} para status em tempo real
│       ├── tasks/
│       │   ├── celery_app.py       # Celery config com Redis broker
│       │   ├── heap_task.py        # task: baixa do MinIO, chama analyzer, salva resultado
│       │   └── thread_task.py      # task: baixa do MinIO, chama parser, salva resultado
│       └── services/
│           ├── storage.py          # MinIO client: upload_file, download_file, get_url
│           └── analyzer_client.py  # chama o container analyzer via subprocess ou HTTP
├── analyzer/
│   ├── Dockerfile                  # FROM openjdk:17-slim + Python 3.12 + baixa Eclipse MAT
│   ├── requirements.txt
│   ├── run_analysis.py             # entry point: recebe path do arquivo e tipo (heap/thread)
│   └── parsers/
│       ├── heap_parser.py          # executa MAT headless, parseia relatório HTML, retorna JSON
│       └── thread_parser.py        # parser regex para jstack: threads, estados, deadlocks, stacks
└── nginx/
    └── nginx.conf
```

---

## Especificações por serviço

### docker-compose.yml
- Usar `depends_on` com `condition: service_healthy` para postgres e redis
- Healthchecks em todos os serviços
- Volume persistente para postgres data e minio data
- Rede interna `dump-net`
- Variáveis via `.env`

### .env.example
```
POSTGRES_DB=dumpanalyzer
POSTGRES_USER=admin
POSTGRES_PASSWORD=changeme
POSTGRES_HOST=postgres
POSTGRES_PORT=5432

REDIS_URL=redis://redis:6379/0

MINIO_ENDPOINT=minio:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
MINIO_BUCKET=dumps

SECRET_KEY=changeme-secret-key

MAX_UPLOAD_SIZE_MB=4096
```

### Backend FastAPI (backend/app/main.py)
- CORS liberado para desenvolvimento
- Lifespan handler: criar tabelas no startup, criar bucket MinIO se não existir
- Routers: `/api/upload`, `/api/analysis`, `/api/ws`
- Documentação Swagger em `/docs`

### POST /api/upload
```
Body: multipart/form-data
  - file: UploadFile (.hprof ou .txt)
Returns: { "job_id": "uuid", "analysis_id": int, "status": "queued" }
```
- Detecta tipo pelo mime type ou extensão (.hprof = heap, .txt = thread)
- Salva no MinIO com key `{uuid}/{filename}`
- Cria registro no PostgreSQL com status `queued`
- Envia task Celery correspondente

### GET /api/analysis/{id}
```
Returns: {
  "id": int,
  "filename": str,
  "type": "heap" | "thread",
  "status": "queued" | "processing" | "done" | "error",
  "result": { ... },   # null enquanto processando
  "created_at": str,
  "error_message": str | null
}
```

### GET /api/analyses
```
Returns: [{ id, filename, type, status, created_at }]  # lista paginada, 20 por página
```

### WebSocket /api/ws/{job_id}
- Envia mensagens JSON: `{ "status": "processing", "progress": 45 }`
- Fecha com `{ "status": "done", "analysis_id": 123 }` ou `{ "status": "error", "message": "..." }`

### Celery Tasks

**heap_task.py**
```python
@celery.task(bind=True)
def analyze_heap(self, analysis_id: int, minio_key: str):
    # 1. Atualiza status para 'processing'
    # 2. Baixa arquivo do MinIO para /tmp/{uuid}.hprof
    # 3. Executa: python /analyzer/run_analysis.py --type heap --file /tmp/{uuid}.hprof
    # 4. Parseia stdout JSON
    # 5. Salva resultado no PostgreSQL
    # 6. Atualiza status para 'done'
    # 7. Em caso de erro: status 'error' com mensagem
```

**thread_task.py** — mesmo padrão mas `--type thread`

### analyzer/parsers/thread_parser.py

Deve extrair de um arquivo jstack:
```python
{
  "summary": {
    "total_threads": int,
    "states": { "RUNNABLE": int, "BLOCKED": int, "WAITING": int, "TIMED_WAITING": int },
    "deadlocks_found": bool
  },
  "deadlocks": [
    {
      "threads": ["Thread-1", "Thread-2"],
      "description": str
    }
  ],
  "threads": [
    {
      "name": str,
      "state": str,
      "priority": int,
      "stack_trace": [str],  # lista de frames
      "waiting_on": str | None,
      "locked": [str]
    }
  ],
  "hotspots": [
    { "frame": str, "count": int }  # frames mais frequentes
  ],
  "stack_groups": [
    { "stack_hash": str, "count": int, "sample_thread": str, "frames": [str] }
  ]
}
```

### analyzer/parsers/heap_parser.py

Executa Eclipse MAT em modo headless:
```bash
./MemoryAnalyzer -consolelog -application org.eclipse.mat.api.parse \
  <hprof_file> \
  org.eclipse.mat.api.leak \
  org.eclipse.mat.api.top_consumers \
  -vmargs -Xmx4g
```

Parseia o relatório gerado e retorna:
```python
{
  "summary": {
    "heap_size_bytes": int,
    "total_objects": int,
    "analysis_date": str
  },
  "leak_suspects": [
    { "description": str, "retained_bytes": int, "percentage": float }
  ],
  "top_consumers": [
    { "class_name": str, "instances": int, "retained_bytes": int, "percentage": float }
  ],
  "dominator_tree": [
    { "object": str, "retained_bytes": int, "percentage": float }
  ]
}
```

Se Eclipse MAT não estiver disponível, retornar análise básica via `jhat` ou parsing direto do .hprof.

### Frontend — componentes principais

**UploadZone.tsx**
- Drag & drop usando `react-dropzone`
- Aceita `.hprof` e `.txt`
- Barra de progresso durante upload (axios com `onUploadProgress`)
- Após upload bem-sucedido, redireciona para `/analysis/{id}` e inicia polling

**AnalysisStatus.tsx**
- Mostra spinner e mensagem de status enquanto `status !== 'done'`
- Polling a cada 3 segundos via React Query `refetchInterval`
- Ou usa WebSocket se disponível

**HeapReport.tsx** — quando `type === 'heap'`
- Cards com: heap total, total de objetos
- Tabela de Leak Suspects com percentual em barra visual
- Tabela de Top Consumers (gráfico de pizza com Recharts)
- Dominator Tree como tabela expandível

**ThreadReport.tsx** — quando `type === 'thread'`
- Cards com: total de threads, breakdown por estado (RUNNABLE/BLOCKED/WAITING)
- Badge de alerta vermelho se deadlocks detectados
- Seção de deadlocks com descrição
- Tabela de hotspots (frames mais frequentes)
- Lista de thread groups (stacks agrupadas por similaridade)

### analyzer/Dockerfile
```dockerfile
FROM openjdk:17-slim

RUN apt-get update && apt-get install -y python3 python3-pip wget unzip curl

# Download Eclipse MAT headless
RUN wget -q https://download.eclipse.org/mat/latest/rcp/MemoryAnalyzer-linux.gtk.x86_64.zip \
    -O /tmp/mat.zip && \
    unzip /tmp/mat.zip -d /opt/ && \
    rm /tmp/mat.zip

WORKDIR /analyzer
COPY requirements.txt .
RUN pip3 install -r requirements.txt --break-system-packages

COPY . .

ENTRYPOINT ["python3", "run_analysis.py"]
```

---

## README.md

Incluir:
1. Pré-requisitos: Docker 24+, Docker Compose v2
2. Como rodar: `cp .env.example .env && docker compose up --build`
3. URLs: Frontend http://localhost, API docs http://localhost:8000/docs, MinIO console http://localhost:9001
4. Como gerar um heap dump de teste: `jmap -dump:format=b,file=heap.hprof <pid>`
5. Como gerar um thread dump de teste: `jstack <pid> > threads.txt`

---

## Restrições importantes

- Python: sempre usar `--break-system-packages` no pip dentro de Dockerfiles
- Não usar `asyncio.run()` dentro de tasks Celery (usar `sync_to_async` ou código síncrono)
- Upload de arquivos grandes: usar `shutil.copyfileobj` em streaming, não carregar tudo em memória
- Eclipse MAT download: se o link falhar, fazer fallback para análise básica sem MAT
- Celery: configurar `task_serializer = 'json'` e `result_serializer = 'json'`
- Frontend: não usar `localStorage` — estado em React Query cache
- CORS: em produção, restringir origins

## Comando para iniciar após clonar

```bash
cd java-dump-analyzer
cp .env.example .env
docker compose up --build
# Acesse http://localhost
```
