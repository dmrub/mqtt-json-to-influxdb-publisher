FROM alpine:3.9

LABEL maintainer="Dmitri Rubinstein <dmitri.rubinstein@dfki.de>"

COPY requirements.txt /usr/src/app/requirements.txt

RUN set -xe; \
    apk add --update --no-cache --virtual .build-deps \
        git tar curl; \
    apk add --no-cache \
        tini python3 tzdata; \
    python3 -m ensurepip; \
    rm -r /usr/lib/python*/ensurepip; \
    pip3 install --upgrade pip setuptools; \
    if [ ! -e /usr/bin/pip ]; then ln -s pip3 /usr/bin/pip ; fi; \
    if [ ! -e /usr/bin/python ]; then ln -sf /usr/bin/python3 /usr/bin/python; fi; \
    pip3 install -Ur /usr/src/app/requirements.txt; \
    apk del .build-deps; \
    rm -rf /var/cache/apk/*; \
    rm -rf /root/.cache;

COPY main.py /usr/src/app
WORKDIR /usr/src/app

RUN chmod +x main.py

ENTRYPOINT ["/sbin/tini", "--", "/usr/src/app/main.py"]
