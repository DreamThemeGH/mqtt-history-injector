ARG BUILD_FROM
FROM $BUILD_FROM

# Установка системных зависимостей
RUN apk add --no-cache python3 py3-pip sqlite

# Создание директории для приложения
WORKDIR /app

# Копирование Python скрипта
COPY run.py /app/

# Копирование s6-overlay конфигурации
COPY rootfs /

# Установка прав на исполнение
RUN chmod a+x /app/run.py \
    && chmod a+x /etc/services.d/mqtt-history-injector/run \
    && chmod a+x /etc/services.d/mqtt-history-injector/finish