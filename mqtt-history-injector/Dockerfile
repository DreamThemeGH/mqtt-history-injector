ARG BUILD_FROM
FROM $BUILD_FROM

# Install requirements
RUN apk add --no-cache python3 py3-pip sqlite
RUN pip3 install paho-mqtt requests

# Copy data
COPY run.py /
RUN chmod a+x /run.py

CMD [ "python3", "/run.py" ]