# tv-api

FastAPI service that powers PickleTV. The app ships with basic health/readiness
checks and an initial `user` endpoint that currently echoes an email payload for
integration testing.

## Requirements

- Python 3.11+
- [Poetry](https://python-poetry.org/) 1.8+

## Getting Started

```bash
poetry install --with dev
poetry run uvicorn tv_api.main:app --host 0.0.0.0 --port 8280 --reload
```

The API is now available at `http://127.0.0.1:8280`. Interactive docs live at
`/docs` and `/redoc`.

### Available Endpoints

| Method | Path                     | Description                                     |
| ------ | ------------------------ | ----------------------------------------------- |
| GET    | `/health`                | Liveness probe                                  |
| GET    | `/readiness`             | Readiness probe                                 |
| GET    | `/privacy`               | Static privacy policy for store submissions     |
| GET    | `/content`               | List downloadable assets in the `assets/` folder |
| GET    | `/content/{filename}`    | Download a specific asset                       |
| POST   | `/user`                  | Accepts `{"email": str}` and echoes back       |

## Running Tests

```bash
poetry run pytest
```

## Makefile Shortcuts

Common workflows also have Make targets:

```bash
make install      # install dependencies with Poetry
make run          # start the API locally on port 8280
make test         # run pytest suite
make docker-build # build container image
make docker-run   # run container exposing 8280
```

## Docker

```bash
docker build -t tv-api .
docker run -p 8280:8280 tv-api
```

The container leverages Poetry for dependency management and exposes port 8280.

## Observability

- Structured request logs are emitted via middleware for every HTTP call,
	including method, path, status code, duration, and a correlation ID that is
	echoed back in the `x-request-id` header.
- Control verbosity with the `TV_API_LOG_LEVEL` environment variable (defaults
	to `INFO`). Example: `TV_API_LOG_LEVEL=DEBUG make run`.

## Assets Directory

- Place downloadable media inside the repository-level `assets/` folder (the
	`/content` endpoints expose whatever files exist there).
- Override the source folder with `TV_API_ASSETS_DIR=/path/to/assets make run`
	if your media lives elsewhere.

## Asset creation

to make a thumbnail from mp4 - the -ss is how many seconds in the grab the frame
```
ffmpeg -ss 5 -i berlin.mp4 -vframes 1 -q:v 2 -vf "scale=640:-2" berlin-640.jpg
```