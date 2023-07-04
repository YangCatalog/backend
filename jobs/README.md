# Celery

This directory contains modules needed for running background jobs from the API.
Besides the normal backend container, another container is started from the image the dockerfile in this repo builds.
The entrypoint is changed in the docker-compose/k8s file to start a [celery](https://docs.celeryq.dev) worker instead of the API server.
RabbitMQ is used both for the task queue and the results backend. When the API server receives a request for a job
that should be run in the background, it queues the job for the worker and returns a job-id.