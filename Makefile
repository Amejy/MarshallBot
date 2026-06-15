COMPOSE ?= docker-compose
COMPOSE_DEV = $(COMPOSE) -f docker-compose.yml -f docker-compose.dev.yml
COMPOSE_PROD = $(COMPOSE) -f docker-compose.yml -f docker-compose.prod.yml

.PHONY: up up-dev down logs ps build rebuild restart clean api

up:
	$(COMPOSE) up --build -d

up-dev:
	$(COMPOSE_DEV) up --build -d

up-prod:
	$(COMPOSE_PROD) up --build -d

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f --tail=100

logs-prod:
	$(COMPOSE_PROD) logs -f --tail=100

ps:
	$(COMPOSE) ps

ps-prod:
	$(COMPOSE_PROD) ps

build:
	$(COMPOSE) build

rebuild:
	$(COMPOSE) build --no-cache

restart:
	$(COMPOSE) down && $(COMPOSE) up --build -d

restart-prod:
	$(COMPOSE_PROD) down && $(COMPOSE_PROD) up --build -d

clean:
	$(COMPOSE) down -v --remove-orphans

clean-prod:
	$(COMPOSE_PROD) down -v --remove-orphans

api:
	$(COMPOSE_DEV) up --build -d api

api-prod:
	$(COMPOSE_PROD) up --build -d api
