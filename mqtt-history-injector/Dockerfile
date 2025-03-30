ARG BUILD_FROM
FROM $BUILD_FROM

# Установка необходимых пакетов
RUN apk add --no-cache python3 py3-pip sqlite

# Копирование Python-скрипта
COPY run.py /usr/bin/
RUN chmod a+x /usr/bin/run.py

# Настройка папки для s6-overlay
WORKDIR /
COPY rootfs /

# Сделаем скрипты запуска исполняемыми
RUN chmod +x /etc/services.d/mqtt-history-injector/run \
    && chmod +x /etc/services.d/mqtt-history-injector/finish