FROM python:3.6-alpine
LABEL Description="GeoImageNet API" Vendor="CRIM" Maintainer="david.caron@crim.ca"

RUN apk update && apk add postgresql-dev gcc python3-dev musl-dev

WORKDIR /code

RUN pip install --upgrade pip && pip install gunicorn

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

RUN python setup.py develop

EXPOSE 8080

CMD ["gunicorn", "--bind=0.0.0.0:8080", "--workers=4", "geoimagenet_api:application.app"]
