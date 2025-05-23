import logging
import os
import sys
import time
from logging import FileHandler, StreamHandler
from http import HTTPStatus

import requests
from dotenv import load_dotenv
from telebot import TeleBot

from exceptions import ApiResponseError, EmptyAPIResponse, MissingTokenError

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
formatter = logging.Formatter(
    '%(asctime)s - %(levelname)s - %(lineno)d - %(message)s'
)
handler.setFormatter(formatter)
log_file = __file__ + '.log'
file_handler = FileHandler(log_file, encoding='utf-8')
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)


def check_tokens():
    """Проверка доступности переменных окружения."""
    required_tokens = (
        ('PRACTICUM_TOKEN', PRACTICUM_TOKEN),
        ('TELEGRAM_TOKEN', TELEGRAM_TOKEN),
        ('TELEGRAM_CHAT_ID', TELEGRAM_CHAT_ID),
    )
    missing_tokens = []
    for name, value in required_tokens:
        if not value:
            logger.critical(f'Переменная окружения {name} не найдена')
            missing_tokens.append(name)
    if missing_tokens:
        raise MissingTokenError(
            f'Отсутствуют обязательные токены: {", ".join(missing_tokens)}'
        )


def send_message(bot, message):
    """Отправка сообщения в чат."""
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        logger.debug(f'Сообщение {message} отправлено')
        return True
    except Exception as error:
        logger.error(f'Сообщение {message} не отправлено: {error}')
        return False


def get_api_answer(timestamp):
    """Запрос к API-cервису."""
    request_data = {
        'url': ENDPOINT,
        'headers': HEADERS,
        'params': {'from_date': timestamp}
    }
    logger.debug(
        f'Запрос к API {request_data["url"]} '
        f'с параметром {request_data["params"]} '
        f'и заголовком {request_data["headers"]}'
    )
    try:
        response = requests.get(
            request_data['url'],
            headers=request_data['headers'],
            params=request_data['params']
        )
    except requests.RequestException as error:
        raise ConnectionError(
            f'Ошибка {error} при запросе к API {request_data["url"]} '
            f'с параметром {request_data["params"]} '
            f'и заголовком {request_data["headers"]}'
        )
    if response.status_code != HTTPStatus.OK:
        raise ApiResponseError(
            f'Ошибка {response.status_code} {response.reason}: {response.text}'
        )
    return response.json()


def check_response(response):
    """Проверка API на соответсвие."""
    logger.debug('Начало проверки ответа от API')
    if not isinstance(response, dict):
        raise TypeError('Значение "response" должно быть словарем')
    if 'homeworks' not in response or 'current_date' not in response:
        raise EmptyAPIResponse('Отсутствуют необходимые ключи')
    homeworks = response.get('homeworks')
    if not isinstance(homeworks, list):
        raise TypeError('Значение "homeworks" должно быть списком')
    return homeworks


def parse_status(homework):
    """Извлечение статуса домашней работы."""
    if 'homework_name' not in homework:
        raise KeyError('Отсутствует название работы')
    if 'status' not in homework:
        raise KeyError('Отсутствие статуса работы')
    homework_name = homework['homework_name']
    status = homework['status']
    if status not in HOMEWORK_VERDICTS:
        raise ValueError('Cтатус {status} отсутствует')
    verdict = HOMEWORK_VERDICTS[status]
    return (
        f'Изменился статус проверки работы "{homework_name}". {verdict}'
    )


def main():
    """Основная логика работы бота."""
    check_tokens()
    bot = TeleBot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    previous_message = None
    while True:
        try:
            response = get_api_answer(timestamp)
            homeworks = check_response(response)
            if not homeworks:
                logger.debug('Проверенных работ пока нет')
            homework = homeworks[0]
            new_message = parse_status(homework)
            if new_message != previous_message:
                if send_message(bot, new_message):
                    previous_message = new_message
            timestamp = response.get('current_date', timestamp)
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(message)
            if message != previous_message:
                if send_message(bot, message):
                    previous_message = message
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
