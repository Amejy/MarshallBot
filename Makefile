COMPOSE ?= docker-compose
COMPOSE_DEV = $(COMPOSE) -f docker-compose.yml -f docker-compose.dev.yml
COMPOSE_PROD = $(COMPOSE) -f docker-compose.yml -f docker-compose.prod.yml
COMPOSE_TUNNEL = $(COMPOSE) -f docker-compose.yml -f docker-compose.dev.yml -f docker-compose.tunnel.yml

.PHONY: up up-dev down logs ps build rebuild restart clean api tunnel-url

up:
	$(COMPOSE) up --build -d

up-dev:
	$(COMPOSE_DEV) up --build -d

up-tunnel:
	$(COMPOSE_TUNNEL) up --build -d

up-prod:
	$(COMPOSE_PROD) up --build -d

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f --tail=100

logs-prod:
	$(COMPOSE_PROD) logs -f --tail=100

logs-tunnel:
	$(COMPOSE_TUNNEL) logs -f --tail=100

tunnel-url:
	$(COMPOSE_TUNNEL) logs -f cloudflared | python3 backend/scripts/print_tunnel_url.py

ps:
	$(COMPOSE) ps

ps-prod:
	$(COMPOSE_PROD) ps

ps-tunnel:
	$(COMPOSE_TUNNEL) ps

build:
	$(COMPOSE) build

rebuild:
	$(COMPOSE) build --no-cache

restart:
	$(COMPOSE) down && $(COMPOSE) up --build -d

restart-prod:
	$(COMPOSE_PROD) down && $(COMPOSE_PROD) up --build -d

restart-tunnel:
	$(COMPOSE_TUNNEL) down && $(COMPOSE_TUNNEL) up --build -d

clean:
	$(COMPOSE) down -v --remove-orphans

clean-prod:
	$(COMPOSE_PROD) down -v --remove-orphans

clean-tunnel:
	$(COMPOSE_TUNNEL) down -v --remove-orphans

api:
	$(COMPOSE_DEV) up --build -d api

api-prod:
	$(COMPOSE_PROD) up --build -d api

api-tunnel:
	$(COMPOSE_TUNNEL) up --build -d api
