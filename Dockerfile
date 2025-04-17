FROM registry.tsl.io/base/base-django:3.11.0 AS base

FROM base AS baseos
# set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

RUN mkdir -p /usr/src/app

COPY . /usr/src/app

WORKDIR /usr/src/app

RUN pip install --no-cache-dir -r testproject/requirements.txt
