# CSV Records UI

React (Vite) dashboard for the CSV Records API: stats, search/filter/sort/paginate,
add / edit / delete employees and CSV export.

## Run locally

```bash
# terminal 1 – the API (from the repo root)
source .venv/bin/activate && uvicorn app.main:app --reload
# or use the one in Minikube:  kubectl -n csv-api port-forward svc/csv-records-api 8000:80

# terminal 2 – the UI
cd frontend
npm install
npm run dev          # http://localhost:5173  (/api is proxied to localhost:8000)
```

## Test & build

```bash
npm test             # unit tests (Vitest)
npm run build        # production files in dist/
```

## Docker

```bash
docker build --target test -t csv-records-ui:test .         # tests + build
docker build --target runtime -t csv-records-ui:local .
docker run --rm -p 3000:8080 -e API_UPSTREAM=host.docker.internal:8000 csv-records-ui:local
# open http://localhost:3000
```

In Kubernetes, nginx forwards `/api/*` to the `csv-records-api` Service, so the browser
only ever talks to one origin (no CORS setup needed).
