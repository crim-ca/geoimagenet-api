FROM python:3.7-alpine3.8

LABEL Description="GeoImageNet API" Vendor="CRIM" Maintainer="david.caron@crim.ca"

WORKDIR /code
COPY geoimagenet_api/__init__.py geoimagenet_api/__about__.py ./geoimagenet_api/
COPY requirements* setup.py README.md ./

RUN apk update && \
    apk add postgresql-libs && \
    apk add --virtual .build-deps gcc musl-dev postgresql-dev make && \
    pip install --upgrade pip setuptools gunicorn && \
    pip install --no-cache-dir -e . && \
    apk --purge del .build-deps gcc musl-dev postgresql-dev make

EXPOSE 8080

COPY . .

CMD gunicorn -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8080 geoimagenet_api:base_app
