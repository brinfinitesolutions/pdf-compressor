COMPOSE        = docker compose
SSH_HOST       ?= digibills-prod
REMOTE_DIR     ?= /opt/pdf-compressor
PLATFORM       ?= linux/amd64
BOT_IMAGE      = pdf-compressor-bot:latest
IMAGE_ARCHIVE  = /tmp/pdf-compressor-bot.tar.gz
REMOTE_COMPOSE = docker compose --env-file .env

.PHONY: build up down logs restart run init-bot \
        deploy-build deploy-push deploy-sync deploy-up deploy \
        deploy-ps deploy-logs deploy-logs-f deploy-init-bot deploy-down

build:
	$(COMPOSE) build

up:
	$(COMPOSE) up -d

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f bot

restart:
	$(COMPOSE) up -d --build

run:
	$(COMPOSE) up --build

# Upload the BR Infinite Solutions logo as the Telegram bot profile picture (needs TELEGRAM_BOT_TOKEN in .env).
init-bot:
	$(COMPOSE) run --rm --no-deps --entrypoint python bot -m bot.init_bot

# ─────────────────────────────────────────────
#  REMOTE DEPLOY FROM LAPTOP  (build locally → SCP → load → up)
#  Same droplet as digiBills: SSH host alias $(SSH_HOST)
#  Requires: Docker buildx, images for $(PLATFORM)
#  .env stays on the server — copy it there once before the first deploy
# ─────────────────────────────────────────────

deploy-build:
	@command -v docker >/dev/null || (echo "docker is required"; exit 1)
	docker buildx build --platform $(PLATFORM) --load -t $(BOT_IMAGE) .

deploy-push: deploy-build
	@echo "Packaging image → $(IMAGE_ARCHIVE)"
	docker save $(BOT_IMAGE) | gzip > $(IMAGE_ARCHIVE)
	@echo "Uploading to $(SSH_HOST):$(IMAGE_ARCHIVE)"
	scp $(IMAGE_ARCHIVE) $(SSH_HOST):$(IMAGE_ARCHIVE)
	@echo "Loading image on $(SSH_HOST)"
	ssh $(SSH_HOST) 'gunzip -c $(IMAGE_ARCHIVE) | docker load && rm -f $(IMAGE_ARCHIVE)'
	rm -f $(IMAGE_ARCHIVE)
	@echo "Image loaded on $(SSH_HOST)"

deploy-sync:
	ssh $(SSH_HOST) 'mkdir -p $(REMOTE_DIR)/data'
	rsync -az --exclude '.git' --exclude '.env' --exclude '.venv' --exclude 'venv' \
		--exclude 'data/media.json' --exclude '**/__pycache__' --exclude '.DS_Store' \
		./ $(SSH_HOST):$(REMOTE_DIR)/

deploy-up: deploy-sync
	ssh $(SSH_HOST) 'cd $(REMOTE_DIR) && $(REMOTE_COMPOSE) up -d --no-build'

deploy: deploy-push deploy-up
	@echo "Deploy complete on $(SSH_HOST):$(REMOTE_DIR)"

deploy-ps:
	ssh $(SSH_HOST) 'cd $(REMOTE_DIR) && $(REMOTE_COMPOSE) ps'

deploy-logs:
	ssh $(SSH_HOST) 'cd $(REMOTE_DIR) && $(REMOTE_COMPOSE) logs --tail=100'

deploy-logs-f:
	ssh $(SSH_HOST) 'cd $(REMOTE_DIR) && $(REMOTE_COMPOSE) logs -f'

deploy-init-bot:
	ssh $(SSH_HOST) 'cd $(REMOTE_DIR) && $(REMOTE_COMPOSE) run --rm --no-deps --entrypoint python bot -m bot.init_bot'

deploy-down:
	ssh $(SSH_HOST) 'cd $(REMOTE_DIR) && $(REMOTE_COMPOSE) down'
