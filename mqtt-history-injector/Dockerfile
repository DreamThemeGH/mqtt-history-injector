ARG BUILD_FROM
FROM $BUILD_FROM

# Установка зависимостей только из репозитория Alpine
# py3-paho-mqtt и py3-requests доступны в репозитории Alpine
RUN apk add --no-cache python3 py3-pip sqlite py3-requests py3-paho-mqtt

# Copy data
COPY run.py /
RUN chmod a+x /run.py

CMD [ "python3", "/run.py" ]