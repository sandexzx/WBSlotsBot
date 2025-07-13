#!/bin/bash

# WBSlotsBot Deploy Script для Ubuntu Server
# Использование: 
#   ./deploy.sh setup    - первичная настройка (клонирование, venv, зависимости)
#   ./deploy.sh service  - создание systemd сервиса и финальные инструкции

set -e  # Выход при любой ошибке

# Конфигурация
PROJECT_NAME="WBSlotsBot"
REPO_URL="https://github.com/YOUR_USERNAME/WBSlotsBot.git"  # ИЗМЕНИТЬ НА ВАШ РЕПОЗИТОРИЙ!
INSTALL_DIR="/opt/wbslotsbot"
SERVICE_NAME="wbslotsbot"
PYTHON_VERSION="python3"

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Функции для вывода
print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_separator() {
    echo "================================================================="
}

# Проверка root прав
check_root() {
    if [[ $EUID -ne 0 ]]; then
        print_error "Этот скрипт должен запускаться от root"
        exit 1
    fi
}

# Первый этап: setup
setup_stage() {
    print_separator
    print_info "🚀 ЭТАП 1: Первичная настройка $PROJECT_NAME"
    print_separator

    # Обновление системы
    print_info "📦 Обновление системы..."
    apt update && apt upgrade -y

    # Установка необходимых пакетов
    print_info "🔧 Установка необходимых пакетов..."
    apt install -y $PYTHON_VERSION python3-pip python3-venv git curl systemd

    # Проверка Python версии
    print_info "🐍 Проверка Python..."
    $PYTHON_VERSION --version

    # Создание директории для проекта
    print_info "📁 Создание директории $INSTALL_DIR..."
    rm -rf "$INSTALL_DIR"
    mkdir -p "$INSTALL_DIR"
    cd "$INSTALL_DIR"

    # Клонирование репозитория
    print_info "📥 Клонирование репозитория..."
    if [[ "$REPO_URL" == *"YOUR_USERNAME"* ]]; then
        print_warning "⚠️  ВНИМАНИЕ! Нужно изменить REPO_URL в скрипте на ваш репозиторий!"
        print_info "Введите URL вашего репозитория (например: https://github.com/username/WBSlotsBot.git):"
        read -r REPO_URL
    fi
    
    git clone "$REPO_URL" .
    print_success "✅ Репозиторий склонирован"

    # Создание виртуального окружения
    print_info "🔄 Создание виртуального окружения..."
    $PYTHON_VERSION -m venv venv
    print_success "✅ Виртуальное окружение создано"

    # Активация venv и установка зависимостей
    print_info "📚 Установка зависимостей..."
    source venv/bin/activate
    pip install --upgrade pip
    pip install -r requirements.txt
    print_success "✅ Зависимости установлены"

    # Создание директории для логов
    print_info "📝 Создание директории для логов..."
    mkdir -p logs
    chmod 755 logs

    # Создание шаблона .env файла
    print_info "⚙️  Создание шаблона .env файла..."
    cat > .env << 'EOF'
# Telegram Bot Configuration
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here

# WildBerries API Configuration
WB_API_KEY=your_wb_api_key_here

# Google Sheets Configuration
GOOGLE_CREDENTIALS_FILE=credentials.json
GOOGLE_SHEETS_URL=your_google_sheets_url_here

# Optional Configuration
BATCH_SIZE=10
EOF
    print_success "✅ Шаблон .env создан"

    # Установка прав доступа
    print_info "🔐 Настройка прав доступа..."
    chown -R root:root "$INSTALL_DIR"
    chmod 755 "$INSTALL_DIR"
    chmod +x main.py

    print_separator
    print_success "🎉 ЭТАП 1 ЗАВЕРШЕН УСПЕШНО!"
    print_separator
    
    echo
    print_warning "📋 СЛЕДУЮЩИЕ ШАГИ:"
    echo "1. Заполните файл .env:"
    echo "   nano $INSTALL_DIR/.env"
    echo
    echo "2. Скопируйте файл credentials.json в директорию проекта:"
    echo "   scp credentials.json root@your_server:$INSTALL_DIR/"
    echo
    echo "3. После завершения настройки запустите второй этап:"
    echo "   ./deploy.sh service"
    echo
    print_separator
}

# Второй этап: service
service_stage() {
    print_separator
    print_info "🔧 ЭТАП 2: Создание systemd сервиса"
    print_separator

    # Проверка существования необходимых файлов
    if [[ ! -f "$INSTALL_DIR/.env" ]]; then
        print_error "❌ Файл .env не найден! Запустите сначала: ./deploy.sh setup"
        exit 1
    fi

    if [[ ! -f "$INSTALL_DIR/credentials.json" ]]; then
        print_error "❌ Файл credentials.json не найден!"
        print_info "Скопируйте его: scp credentials.json root@your_server:$INSTALL_DIR/"
        exit 1
    fi

    if [[ ! -d "$INSTALL_DIR/venv" ]]; then
        print_error "❌ Виртуальное окружение не найдено! Запустите сначала: ./deploy.sh setup"
        exit 1
    fi

    # Создание systemd service файла
    print_info "📄 Создание systemd service файла..."
    cat > "/etc/systemd/system/${SERVICE_NAME}.service" << EOF
[Unit]
Description=WBSlotsBot - Telegram Bot for WildBerries Slots Monitoring
After=network.target

[Service]
Type=simple
User=root
Group=root
WorkingDirectory=$INSTALL_DIR
Environment=PATH=$INSTALL_DIR/venv/bin
ExecStart=$INSTALL_DIR/venv/bin/python $INSTALL_DIR/main.py
Restart=always
RestartSec=10

# Логирование
StandardOutput=journal
StandardError=journal
SyslogIdentifier=$SERVICE_NAME

# Безопасность
NoNewPrivileges=true

[Install]
WantedBy=multi-user.target
EOF

    # Перезагрузка systemd и включение сервиса
    print_info "🔄 Перезагрузка systemd..."
    systemctl daemon-reload
    systemctl enable "$SERVICE_NAME"
    print_success "✅ Сервис создан и включен"

    # Тестовый запуск
    print_info "🧪 Тестовый запуск сервиса..."
    systemctl start "$SERVICE_NAME"
    sleep 3
    
    if systemctl is-active --quiet "$SERVICE_NAME"; then
        print_success "✅ Сервис запущен успешно!"
    else
        print_warning "⚠️  Сервис не смог запуститься. Проверьте логи: journalctl -u $SERVICE_NAME -f"
    fi

    print_separator
    print_success "🎉 DEPLOYMENT ЗАВЕРШЕН УСПЕШНО!"
    print_separator
    
    echo
    print_info "📋 УПРАВЛЕНИЕ СЕРВИСОМ:"
    echo "  • Запуск:     systemctl start $SERVICE_NAME"
    echo "  • Остановка:  systemctl stop $SERVICE_NAME"
    echo "  • Рестарт:    systemctl restart $SERVICE_NAME"
    echo "  • Статус:     systemctl status $SERVICE_NAME"
    echo "  • Логи:       journalctl -u $SERVICE_NAME -f"
    echo "  • Автозапуск: systemctl enable $SERVICE_NAME"
    echo
    print_info "📋 УПРАВЛЕНИЕ БОТОМ:"
    echo "  • Отправьте /start вашему боту в Telegram"
    echo "  • Бот будет отправлять уведомления о доступных слотах WB"
    echo "  • Данные берутся из Google Sheets"
    echo
    print_info "📂 ФАЙЛЫ ПРОЕКТА:"
    echo "  • Проект:     $INSTALL_DIR"
    echo "  • Логи:       $INSTALL_DIR/logs/"
    echo "  • Конфиг:     $INSTALL_DIR/.env"
    echo "  • Подписки:   $INSTALL_DIR/subscriptions.json"
    echo
    print_separator
}

# Показ help
show_help() {
    echo "WBSlotsBot Deploy Script"
    echo
    echo "Использование:"
    echo "  $0 setup     - Первичная настройка (клонирование, venv, зависимости, .env шаблон)"
    echo "  $0 service   - Создание systemd сервиса и финальные инструкции"
    echo "  $0 help      - Показать эту справку"
    echo
    echo "Примеры:"
    echo "  $0 setup     # Первый запуск для настройки"
    echo "  $0 service   # Второй запуск после заполнения .env и копирования credentials.json"
}

# Основная логика
main() {
    case "${1:-}" in
        "setup")
            check_root
            setup_stage
            ;;
        "service")
            check_root
            service_stage
            ;;
        "help"|"--help"|"-h")
            show_help
            ;;
        *)
            print_error "❌ Неизвестная команда: ${1:-}"
            echo
            show_help
            exit 1
            ;;
    esac
}

# Запуск
main "$@"