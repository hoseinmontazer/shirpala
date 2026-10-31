.PHONY: all build up down restart logs run-pipeline stats clean

all: build up

build:
	docker compose build

up:
	docker compose up -d

down:
	docker compose down

restart:
	docker compose restart

logs:
	docker compose logs -f

logs-pipeline:
	docker compose logs -f pipeline

run-pipeline:
	docker compose exec pipeline python3 -m pipeline.runner run

stats:
	docker compose exec pipeline python3 -m pipeline.runner stats

clean:
	rm -rf pipeline.db pipeline.db-journal *.log
