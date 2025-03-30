ARG BUILD_FROM
FROM $BUILD_FROM

# Установка системных зависимостей
RUN apk add --no-cache python3 py3-pip sqlite

# Установка Python зависимостей
RUN pip3 install --no-cache-dir paho-mqtt requests

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