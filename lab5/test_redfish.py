import pytest
import requests
import json
import logging

from requests.packages.urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

BMC_IP = "localhost" 
BMC_PORT = "2443"    
USERNAME = "root"
PASSWORD = "0penBmc"
BASE_URL = f"https://{BMC_IP}:{BMC_PORT}"

@pytest.fixture(scope="session") 
def session_auth():
    logging.info("Создание сессии Redfish...")
    session = requests.Session()
    session.verify = False
    session.headers.update({"Content-Type": "application/json"})

    auth_url = f"{BASE_URL}/redfish/v1/SessionService/Sessions"
    auth_data = {
        "UserName": USERNAME,
        "Password": PASSWORD
    }

    try:
        response = session.post(auth_url, json=auth_data)
        response.raise_for_status()
        auth_token = response.headers.get('X-Auth-Token')
        if auth_token:
            session.headers.update({"X-Auth-Token": auth_token})
            logging.info("Сессия успешно создана с токеном.")
        else:
             logging.warning("Токен сессии не найден в заголовке X-Auth-Token.")

        yield session 

    except requests.exceptions.RequestException as e:
        logging.error(f"Ошибка при создании сессии: {e}")
        pytest.fail(f"Не удалось создать сессию: {e}")
    finally:
        if 'auth_token' in locals() or 'auth_token' in globals():
            delete_session_url = f"{BASE_URL}/redfish/v1/SessionService/Sessions"
            pass
        logging.info("Сессия завершена.")


def test_authentication(session_auth):
    url = f"{BASE_URL}/redfish/v1/"
    response = session_auth.get(url)
    assert response.status_code == 200, f"Ожидался статус 200, получен {response.status_code}"
    data = response.json()
    assert "@odata.id" in data, "Ответ не содержит ожидаемого поля @odata.id"
    logging.info("Тест аутентификации пройден: корневой ресурс доступен.")


def test_get_system_info(session_auth):
    url = f"{BASE_URL}/redfish/v1/Systems/system"
    response = session_auth.get(url)
    assert response.status_code == 200, f"Ошибка получения информации о системе: {response.status_code}"
    data = response.json()

    assert "Status" in data, "Поле 'Status' отсутствует в ответе"
    assert "PowerState" in data, "Поле 'PowerState' отсутствует в ответе"
    logging.info(f"Информация о системе получена. Статус: {data['Status']}, Состояние питания: {data['PowerState']}")
    

def test_power_control(session_auth):
    system_url = f"{BASE_URL}/redfish/v1/Systems/system"
    response = session_auth.get(system_url)
    assert response.status_code == 200
    initial_state = response.json().get("PowerState", "Unknown")
    logging.info(f"Начальное состояние питания: {initial_state}")

    reset_url = f"{BASE_URL}/redfish/v1/Systems/system/Actions/ComputerSystem.Reset"
    reset_type = "On"
    payload = {"ResetType": reset_type}
    response = session_auth.post(reset_url, json=payload)

    assert response.status_code == 200 or response.status_code == 202 or response.status_code == 204, f"Ошибка управления питанием: {response.status_code}. Ответ: {response.text}"
    logging.info(f"Команда управления питанием '{reset_type}' отправлена.")

    logging.info("Тест управления питанием пройден: команда принята.")
    

def test_cpu_temperature(session_auth):
    thermal_metrics_url = f"{BASE_URL}/redfish/v1/Chassis/chassis/ThermalSubsystem/ThermalMetrics"
    response = session_auth.get(thermal_metrics_url)
    assert response.status_code == 200, f"Ошибка получения данных ThermalMetrics: {response.status_code}"

    data = response.json()
    
    assert "TemperatureReadingsCelsius" in data, "Поле 'TemperatureReadingsCelsius' отсутствует в ответе ThermalMetrics"

    temp_readings = data["TemperatureReadingsCelsius"]
    
    if not temp_readings or data.get("TemperatureReadingsCelsius@odata.count", 0) == 0:
        logging.info("Данные о температуре отсутствуют в эмуляторе. Тест пропущен.")
        pytest.skip("Данные о температуре отсутствуют в эмуляторе romulus.")

    cpu_temps = [t for t in temp_readings if 'CPU' in t.get("Name", "") or 'Tctl' in t.get("Name", "")]
    
    if not cpu_temps:
        logging.info("Датчики температуры CPU не найдены в ThermalMetrics. Проверьте структуру данных.")
        pytest.skip("Датчики температуры CPU не найдены в ThermalMetrics эмулятора romulus.")

    max_allowed_temp = 80.0
    for temp_sensor in cpu_temps:
        current_temp = temp_sensor.get("Reading")
        sensor_name = temp_sensor.get("Name", "Unknown Sensor")
        if current_temp is not None:
            assert current_temp < max_allowed_temp, f"Температура {sensor_name} ({current_temp}°C) превышает допустимую ({max_allowed_temp}°C)"
            logging.info(f"Температура {sensor_name}: {current_temp}°C (в пределах нормы)")
        else:
             logging.warning(f"Температура для датчика {sensor_name} не доступна (Reading is None)")

    logging.info("Тест температуры CPU завершен.")

    
def test_cpu_sensors_redfish_vs_ipmi(session_auth):
    sensors_url = f"{BASE_URL}/redfish/v1/Chassis/chassis/Sensors"
    response = session_auth.get(sensors_url)
    assert response.status_code == 200, f"Ошибка получения данных Sensors: {response.status_code}"
    redfish_data = response.json()

    assert "Members" in redfish_data, "Поле 'Members' отсутствует в ответе Sensors"

    sensors_collection = redfish_data["Members"]
    
    if not sensors_collection or redfish_data.get("Members@odata.count", 0) == 0:
        logging.info("Коллекция датчиков Sensors пуста в эмуляторе. Тест пропущен.")
        pytest.skip("Коллекция датчиков Sensors пуста в эмуляторе romulus.")

    redfish_cpu_sensors = []
    for member in sensors_collection:
        member_id = member.get('@odata.id') or member.get('Id')
        if member_id:
            if member_id.startswith('/'):
                member_full_url = f"{BASE_URL}{member_id}"
            else:
                member_full_url = member_id

            sensor_resp = session_auth.get(member_full_url)
            if sensor_resp.status_code == 200:
                sensor_info = sensor_resp.json()
                if 'CPU' in sensor_info.get("Name", "") or 'Processor' in sensor_info.get("PhysicalContext", ""):
                    redfish_cpu_sensors.append(sensor_info)
            else:
                logging.warning(f"Не удалось получить данные датчика {member_full_url}: {sensor_resp.status_code}")

    if not redfish_cpu_sensors:
        logging.info("Датчики CPU в Redfish не найдены (ожидаемо для romulus).")
        pytest.skip("Датчики CPU в Redfish не найдены в эмуляторе romulus. Сравнение с IPMI не реализовано.")

    logging.info(f"Найдено {len(redfish_cpu_sensors)} датчиков CPU в Redfish.")
    pytest.skip("Сравнение с IPMI требует дополнительной настройки и библиотек (например, pyghmi). Реализация сравнения не завершена.")