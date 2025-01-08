#!/usr/bin/env python3

import time, dateparser, subprocess, shlex
from datetime import datetime, timedelta
from colorama import Fore, Style

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
    def send_notification():
        command = 'notify-send "Будильник" "Пора вставать!"'
        try:
            subprocess.run(shlex.split(command), check=True)
        except (subprocess.CalledProcessError, OSError) as e:
            print(f"{Fore.RED}Ошибка при отправке уведомления:{Style.RESET_ALL} {str(e)}")

    # Дожидаюсь времени будильника
    while True:
        now = datetime.now()
        if now >= alarm_time:
            send_notification()
            print(f"{Fore.YELLOW}Будильник сработал!{Style.RESET_ALL}")
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
    alarm_time = set_alarm(alarm_time)
    if alarm_time:
        start_alarm(alarm_time)