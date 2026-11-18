# Единый командный интерфейс проекта. Работает в Windows (GNU make) и Linux.

ifeq ($(OS),Windows_NT)
  PYTHON ?= py
  PY := .venv\Scripts\python.exe
else
  PYTHON ?= python3
  PY := .venv/bin/python
endif

COMPOSE := docker compose

.DEFAULT_GOAL := help
.PHONY: help setup run test quality format migrate seed verify up down logs

help: ## Список команд
	@echo setup   - первоначальная настройка (venv, зависимости, .env)
	@echo run     - локальный запуск приложения
	@echo test    - автоматические тесты
	@echo quality - проверка форматирования и статический анализ
	@echo format  - автоформатирование кода
	@echo migrate - применение миграций БД
	@echo seed    - создание администратора и демо-данных
	@echo verify  - полный набор обязательных локальных проверок
	@echo up      - запуск PostgreSQL в контейнере
	@echo down    - остановка контейнеров

setup:
	$(PYTHON) -m venv .venv
	$(PY) -m pip install --upgrade pip
	$(PY) -m pip install -r requirements-dev.txt
	$(PY) -c "import os, shutil; os.path.exists('.env') or shutil.copy('.env.example', '.env')"

run:
	$(PY) -m app

test:
	$(PY) -m pytest

quality:
	$(PY) -m ruff format --check .
	$(PY) -m ruff check .

format:
	$(PY) -m ruff format .
	$(PY) -m ruff check --fix .

migrate:
	$(PY) -m alembic upgrade head

seed:
	$(PY) -m app.seed --demo

verify: quality test
	@echo All checks passed

up:
	$(COMPOSE) up -d --wait db

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f db
