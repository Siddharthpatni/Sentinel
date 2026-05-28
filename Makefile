.PHONY: demo up down seed logs test lint

demo:
	./scripts/demo.sh

up:
	docker compose up -d

down:
	docker compose down

seed:
	python examples/seed_demo.py

logs:
	docker compose logs -f gateway dashboard

test:
	cd gateway && pytest tests/ -v

lint:
	ruff check gateway/ sdk/
