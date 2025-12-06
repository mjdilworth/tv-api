.PHONY: help install run test docker-build docker-run clean

help:
	@echo "Available targets:"
	@printf "  %-15s%s\n" "install" "Install dependencies via Poetry"
	@printf "  %-15s%s\n" "run" "Start the API locally on port 8280"
	@printf "  %-15s%s\n" "test" "Run pytest suite"
	@printf "  %-15s%s\n" "docker-build" "Build the tv-api Docker image"
	@printf "  %-15s%s\n" "docker-run" "Run the Docker image exposing 8280"
	@printf "  %-15s%s\n" "clean" "Remove Python caches"

install:
	poetry install --with dev

run:
	@export TV_API_DATABASE_URL="postgresql://tv_api_app:dilly@localhost:5432/tv_dbase" && \
	cd $(shell pwd) && \
	poetry run uvicorn tv_api.main:app --host 0.0.0.0 --port 8280 --reload

test:
	poetry run pytest

docker-build:
	docker build -t tv-api .

docker-run:
	docker run --rm -p 8280:8280 tv-api

clean:
	rm -rf __pycache__ .pytest_cache
