ARG BUILD_FROM
FROM $BUILD_FROM

# Install requirements with explicit upgrade of pip first
RUN apk add --no-cache python3 py3-pip sqlite gcc python3-dev musl-dev
RUN pip3 install --no-cache-dir --upgrade pip
RUN pip3 install --no-cache-dir paho-mqtt requests

# Copy data
COPY run.py /
RUN chmod a+x /run.py

CMD [ "python3", "/run.py" ]