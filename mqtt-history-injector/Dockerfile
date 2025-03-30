ARG BUILD_FROM
FROM $BUILD_FROM

# Установка системных зависимостей (минимальный набор)
RUN apk add --no-cache \
    python3 \
    py3-pip \
    sqlite

# Альтернатива 1: Установка с использованием предварительно собранных пакетов
RUN pip3 install --no-cache-dir --prefer-binary \
    paho-mqtt==1.6.1 \
    requests==2.31.0

# ИЛИ Альтернатива 2: Если первая не работает, используем этот вариант
# RUN apk add --no-cache --virtual .build-deps \
#     build-base \
#     python3-dev \
#     libffi-dev \
#     openssl-dev \
#     && pip3 install --no-cache-dir \
#     paho-mqtt==1.6.1 \
#     requests==2.31.0 \
#     && apk del .build-deps

# Создание директории для приложения
WORKDIR /app

# Копирование файлов
COPY run.py /app/
COPY rootfs /

# Установка прав на исполнение
RUN chmod a+x /app/run.py \
    && chmod a+x /etc/services.d/mqtt-history-injector/run \
    && chmod a+x /etc/services.d/mqtt-history-injector/finish

# Запуск через s6-overlay
ENTRYPOINT ["/init"]