#!/usr/bin/env python3

import time
import dateparser
from datetime import datetime, timedelta
import pygame
import os
from colorama import Fore, Style
import logging

# Инициализация pygame для воспроизведения звука
pygame.mixer.init()

def get_current_time():
    current_time = datetime.now()
    return f"Текущее время: {current_time.strftime('%H:%M')}"

def set_alarm(alarm_time_str):
    """
    Устанавливаю будильник на основе предоставленной временной строки (формат ЧЧ:ММ, 24-часовой формат).
    """
    try:
        # Анализ времени будильника
        now = datetime.now()
        alarm_time = datetime.strptime(alarm_time_str, "%H:%M").replace(year=now.year, month=now.month, day=now.day)

        # Если время будильника на следующий день
        if alarm_time <= now:
            alarm_time += timedelta(days=1)

        print(f"{Fore.RED}Будильник {Style.RESET_ALL}установлен на {alarm_time.strftime('%H:%M')}.")
        return alarm_time

    except ValueError:
        print(f"{Fore.RED}Ошибка:{Style.RESET_ALL} неверный формат времени. Попробуйте снова.")
        return None

def start_alarm(alarm_time):
    """
    Запускаю обратный отсчет будильника и оповещаю, когда наступит время.
    """
    # Путь к звуковому файлу будильника (относительно корня проекта)
    alarm_sound_path = os.path.join("sounds", "alarm.mp3")
    
    try:
        pygame.mixer.music.load(alarm_sound_path)
    except pygame.error:
        print(f"{Fore.RED}Ошибка:{Style.RESET_ALL} не удалось загрузить звук будильника")
        return

    while True:
        now = datetime.now()
        if now >= alarm_time:
            print(f"{Fore.YELLOW}Будильник сработал!{Style.RESET_ALL}")
            # Воспроизводим звук 3 раза
            for _ in range(3):
                pygame.mixer.music.play()
                while pygame.mixer.music.get_busy():
                    pygame.time.Clock().tick(10)
                time.sleep(1)
            break
        time.sleep(30)  # Проверка каждые 30 секунд


def parse_time_from_text(text):
    parsed_time = dateparser.parse(text, settings={'PREFER_DATES_FROM': 'future'})
    if parsed_time:
        return parsed_time.strftime("%H:%M")
    return None


def start_alarm_thread(alarm_time):
    """
    Отдельный поток для запуска будильника.
    """
    logging.info(f"Попытка установки будильника на {alarm_time}")
    alarm_datetime = set_alarm(alarm_time)
    if alarm_datetime:
        logging.info(f"Будильник успешно установлен на {alarm_datetime}")
        start_alarm(alarm_datetime)
    else:
        logging.error("Не удалось установить будильник")