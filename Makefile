APP_VERSION ?= v0.1.0
IMAGE_REGISTRY ?= quay.io/opstree
IMAGE_NAME ?= notification-api

#########################################################
# Build
#########################################################

build:
	pip install --no-cache-dir -r requirements.txt

#########################################################
# Test
#########################################################

test:
	python -m pytest

#########################################################
# Docker
#########################################################

docker-build:
	docker build -t ${IMAGE_REGISTRY}/${IMAGE_NAME}:${APP_VERSION} -f Dockerfile .

docker-push:
	docker push ${IMAGE_REGISTRY}/${IMAGE_NAME}:${APP_VERSION}

#########################################################
# Run
#########################################################

run:
	python notification_api.py