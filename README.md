# MQTT History Injector for Home Assistant

[![Open your Home Assistant instance and show the add add-on repository dialog with a specific repository URL pre-filled.](https://my.home-assistant.io/badges/supervisor_add_addon_repository.svg)](https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2FDreamThemeGH%2Fmqtt-history-injector)

## О проекте

Этот аддон для Home Assistant позволяет принимать исторические данные от датчиков через MQTT и записывать их напрямую в базу данных Home Assistant с сохранением оригинальных временных меток.

### Ключевые возможности:

- Приём исторических данных через MQTT
- Автоматическое создание отсутствующих датчиков
- Добавление данных в историю Home Assistant с правильными временными метками
- Поддержка как одиночных записей, так и пакетной отправки нескольких записей
- Интеграция с REST API Home Assistant для создания датчиков

## Установка

1. Перейдите в раздел "Supervisor" -> "Add-on Store" в Home Assistant
2. Нажмите на меню (три точки) в правом верхнем углу и выберите "Repositories"
3. Добавьте URL репозитория: `https://github.com/DreamThemeGH/mqtt-history-injector`
4. После добавления репозитория, аддон "MQTT History Injector" появится в списке доступных аддонов
5. Нажмите на него и выберите "Install"

## Настройка

После установки, требуется настроить аддон через интерфейс Home Assistant:

```yaml
mqtt_host: core-mosquitto  # Адрес MQTT брокера
mqtt_port: 1883            # Порт MQTT брокера
mqtt_username: ""          # Имя пользователя для MQTT (если требуется)
mqtt_password: ""          # Пароль для MQTT (если требуется)
mqtt_topic: "homeassistant/history/#"  # Топик для подписки
ha_database_path: "/config/home-assistant_v2.db"  # Путь к базе данных HA
ha_api_url: "http://supervisor/core/api"  # URL для API HA
ha_token: ""               # Токен для доступа к API HA (опционально)
max_timestamp_offset_days: 30  # Максимальная "древность" данных в днях
default_entity_id_prefix: "sensor."  # Префикс по умолчанию для новых сущностей
create_missing_entities: true  # Создавать ли отсутствующие датчики
```

## Использование

### Формат сообщений MQTT

#### Одиночная запись:
```json
{
    "state": "23.5",
    "timestamp": "2023-04-15T02:30:00",
    "attributes": {
        "unit_of_measurement": "°C",
        "friendly_name": "Спальня Температура"
    }
}
```

#### Несколько записей:
```json
{
    "records": [
        {
            "state": "23.5", 
            "timestamp": "2023-04-15T02:30:00",
            "attributes": {"unit_of_measurement": "°C", "friendly_name": "Спальня Температура"}
        },
        {
            "state": "23.1", 
            "timestamp": "2023-04-15T03:30:00",
            "attributes": {"unit_of_measurement": "°C", "friendly_name": "Спальня Температура"}
        }
    ]
}
```

### Топики MQTT

Используйте формат `homeassistant/history/sensor.имя_датчика` для отправки данных. Например:
- `homeassistant/history/sensor.bedroom_temperature`
- `homeassistant/history/sensor.living_room_humidity`

## Примеры

### Пример для ESP8266/ESP32 с датчиком температуры

```cpp
#include <ESP8266WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>

// ... Код подключения к WiFi и MQTT ...

void sendHistoricalData() {
  StaticJsonDocument<1024> doc;
  JsonArray records = doc.createNestedArray("records");
  
  // Добавление нескольких исторических записей
  JsonObject record1 = records.createNestedObject();
  record1["state"] = "22.5";
  record1["timestamp"] = "2023-04-15T01:00:00";
  JsonObject attrs1 = record1.createNestedObject("attributes");
  attrs1["unit_of_measurement"] = "°C";
  attrs1["friendly_name"] = "Комнатная температура";
  
  JsonObject record2 = records.createNestedObject();
  record2["state"] = "22.1";
  record2["timestamp"] = "2023-04-15T02:00:00";
  JsonObject attrs2 = record2.createNestedObject("attributes");
  attrs2["unit_of_measurement"] = "°C";
  attrs2["friendly_name"] = "Комнатная температура";
  
  // Сериализация в строку
  String output;
  serializeJson(doc, output);
  
  // Отправка в MQTT
  client.publish("homeassistant/history/sensor.room_temperature", output.c_str());
}
```

## Поддержка

Если у вас возникли проблемы или есть предложения по улучшению аддона, пожалуйста, создайте issue в репозитории на GitHub.