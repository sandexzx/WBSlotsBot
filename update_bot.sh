#!/bin/bash

set -e

echo "🤖 Обновление WBSlotsBot..."

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

BOT_DIR="/opt/wbslotsbot"
SERVICE_NAME="wbslotsbot.service"
LOG_SERVICE_NAME="coupletodobot.service"

echo -e "${YELLOW}Остановка процессов бота...${NC}"

# Находим процесс бота и убиваем его
BOT_PID=$(ps aux | grep "/opt/wbslotsbot/venv/bin/python /opt/wbslotsbot/main.py" | grep -v grep | awk '{print $2}' || true)

if [ ! -z "$BOT_PID" ]; then
    echo "Найден процесс бота с PID: $BOT_PID"
    kill -9 $BOT_PID
    echo -e "${GREEN}Процесс бота завершен${NC}"
else
    echo "Процесс бота не найден"
fi

# Останавливаем сервис на всякий случай
echo "Остановка сервиса..."
systemctl stop $SERVICE_NAME || true

# Переходим в директорию бота
echo -e "${YELLOW}Переход в директорию бота...${NC}"
cd $BOT_DIR

# Обновляем код
echo -e "${YELLOW}Обновление кода...${NC}"
git pull

# Проверяем статус обновления
if [ $? -eq 0 ]; then
    echo -e "${GREEN}Код успешно обновлен${NC}"
else
    echo -e "${RED}Ошибка при обновлении кода${NC}"
    exit 1
fi

# Запускаем бота
echo -e "${YELLOW}Запуск бота...${NC}"
systemctl restart $SERVICE_NAME

# Проверяем статус сервиса
sleep 2
if systemctl is-active --quiet $SERVICE_NAME; then
    echo -e "${GREEN}Бот успешно запущен${NC}"
else
    echo -e "${RED}Ошибка запуска бота${NC}"
    systemctl status $SERVICE_NAME
    exit 1
fi

echo -e "${GREEN}Обновление завершено!${NC}"
echo -e "${YELLOW}Просмотр логов (Ctrl+C для выхода):${NC}"

# Показываем логи
journalctl -u $LOG_SERVICE_NAME -f