import logging
import os
import sys
import time
from logging import StreamHandler

import requests
from dotenv import load_dotenv
from telebot import TeleBot

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}
HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = StreamHandler(sys.stdout)
logger.addHandler(handler)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)


class ApiResponseError(Exception):
    """Исключение при некорректном ответе от API."""


def check_tokens():
    """Проверка доступности переменных окружения."""
    if (
        PRACTICUM_TOKEN is None
        or TELEGRAM_TOKEN is None
        or TELEGRAM_CHAT_ID is None
    ):
        logging.critical('Не все переменные окружения заданы корректно')
        sys.exit()


def send_message(bot, message):
    """Отправка сообщения в чат."""
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        logging.debug('Сообщение отправлено')
    except Exception as error:
        logging.error(error)


def get_api_answer(timestamp):
    """Запрос к API-cервису."""
    try:
        response = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params={'from_date': timestamp}
        )
        if response.status_code != 200:
            logging.error(f'Ошибка {response.status_code} при запросе к API')
            raise ApiResponseError(
                f'Ошибка {response.status_code} при запросе к API'
            )
        return response.json()
    except requests.RequestException as error:
        logging.error(error)
        raise Exception(f'Ошибка при запросе к API: {error}')


def check_response(response):
    """Проверка API на соответсвие."""
    try:
        if not isinstance(response, dict):
            raise TypeError('Значение "response" должно быть словарем')
        if 'homeworks' not in response or 'current_date' not in response:
            raise KeyError('Отсутствуют необходимые ключи')
        if not isinstance(response['homeworks'], list):
            raise TypeError('Значение "homeworks" должно быть списком')
        for homework in response['homeworks']:
            if not isinstance(homework, dict):
                raise TypeError('Элементы в "homeworks" должны быть словарями')
        if len(response['homeworks']) == 0:
            logging.debug('Проверенных работ пока нет')
    except KeyError as error:
        logging.error(error)
        raise Exception(error)


def parse_status(homework):
    """Извлечение статуса домашней работы."""
    try:
        if 'homework_name' not in homework:
            raise KeyError('Отсутствует название работы')
        if (
            'status' not in homework
            or homework['status'] not in ['approved', 'reviewing', 'rejected']
        ):
            raise KeyError('Отсутствие статуса работы')
        for verdict in HOMEWORK_VERDICTS:
            if homework['status'] == verdict:
                return (
                    f'Изменился статус проверки работы '
                    f'"{homework["homework_name"]}". '
                    f'{HOMEWORK_VERDICTS[verdict]}'
                )
    except Exception as error:
        logging.error(f'Неожиданный статус домашней работы: {error}')
        raise Exception(error)


def main():
    """Основная логика работы бота."""
    bot = TeleBot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    while True:
        try:
            check_tokens()
            response = get_api_answer(timestamp)
            check_response(response)
            if 'homeworks' in response:
                for homework in response['homeworks']:
                    message = parse_status(homework)
                    send_message(bot, message)
            time.sleep(RETRY_PERIOD)
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logging.error(message)


if __name__ == '__main__':
    main()
