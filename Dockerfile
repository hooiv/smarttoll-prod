# Hugging Face Spaces Docker SDK image.
# Local `docker compose` does not use this file. It builds the three service
# Dockerfiles instead. This image runs those three processes plus nginx on
# port 7860, as uid 1000, which Spaces requires.
FROM python:3.11-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends nginx \
    && rm -rf /var/lib/apt/lists/* \
    && useradd -m -u 1000 user \
    && mkdir -p /var/log/nginx /var/lib/nginx /var/cache/nginx \
    && chown -R user:user /var/log/nginx /var/lib/nginx /var/cache/nginx

ENV HOME=/home/user \
    PATH=/home/user/.local/bin:/usr/local/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    KAFKA_SECURITY_PROTOCOL=SASL_SSL \
    KAFKA_SASL_MECHANISM=SCRAM-SHA-256 \
    SIM_SEND_INTERVAL_SECONDS=10 \
    PORT=7860

WORKDIR /home/user/app

COPY --chown=user billing_service/requirements.txt /tmp/billing-requirements.txt
COPY --chown=user toll_processor/requirements.txt /tmp/processor-requirements.txt
COPY --chown=user obu_simulator/requirements.txt /tmp/simulator-requirements.txt
RUN pip install --no-cache-dir \
        -r /tmp/billing-requirements.txt \
        -r /tmp/processor-requirements.txt \
        -r /tmp/simulator-requirements.txt \
        supervisor \
    && mkdir -p /tmp/client_temp /tmp/proxy_temp \
    && chown -R user:user /tmp/client_temp /tmp/proxy_temp

COPY --chown=user billing_service /home/user/app/billing_service
COPY --chown=user toll_processor /home/user/app/toll_processor
COPY --chown=user obu_simulator /home/user/app/obu_simulator
COPY --chown=user common /home/user/app/common
COPY --chown=user deploy/huggingface/nginx.conf /home/user/app/deploy/huggingface/nginx.conf
COPY --chown=user deploy/huggingface/supervisord.conf /home/user/app/deploy/huggingface/supervisord.conf
COPY --chown=user deploy/huggingface/entrypoint.sh /home/user/app/entrypoint.sh
RUN chmod 755 /home/user/app/entrypoint.sh && chown user:user /home/user/app

USER user
EXPOSE 7860

CMD ["/home/user/app/entrypoint.sh"]
