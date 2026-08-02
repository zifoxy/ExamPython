# FireBite

Веб-приложение доставки еды на **Django**: меню, корзина, заказы, роли пользователей, складской учёт и чат поддержки.

## Стек

- Python 3 + Django 5/6
- PostgreSQL 16 (Docker)
- Bootstrap 5
- Pillow (изображения блюд)
- python-dotenv

## Возможности

### Клиент
- Просмотр меню и карточек блюд (состав без граммов)
- Регистрация / вход; корзина только для авторизованных
- Оформление заказа и тестовая оплата
- Личный кабинет и отслеживание статуса своего заказа
- Чат с поддержкой (уведомление при подключении оператора)

### Модератор
- CRUD блюд с рецептурой
- Управление статусами заказов
- Ручное списание ингредиентов с обязательной причиной (остаток склада уменьшается сразу)

### Бухгалтер
- Склад: остатки, ревизия, приход, журнал движений
- Просмотр списаний (в т.ч. от модераторов)
- Полные рецептуры с граммами
- Отчёты: расход ингредиентов, доходы, бланк ревизии (с выбором периода/дат, CSV)

### Поддержка
- Очередь чатов, подключение к диалогу, история заказов клиента

Роль задаётся в модели `Profile` (админка Django).

## Быстрый старт

### 1. Клонирование и окружение

```bash
git clone <url-репозитория>
cd ExamPython
python -m venv .venv

# Windows
.venv\Scripts\activate

# Linux / macOS
source .venv/bin/activate

pip install -r requirements.txt
```

### 2. База данных

Скопируйте пример переменных окружения:

```bash
cp .env.example .env
```

Содержимое `.env` по умолчанию:

```env
POSTGRES_DB=exampython
POSTGRES_USER=postgres
POSTGRES_PASSWORD=qwerty123
POSTGRES_HOST=localhost
POSTGRES_PORT=5433
```

Запустите PostgreSQL:

```bash
docker compose up -d
```

Контейнер слушает порт **5433** на хосте (внутри контейнера — 5432).

### 3. Миграции и суперпользователь

```bash
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Сайт: [http://127.0.0.1:8000/](http://127.0.0.1:8000/)  
Админка: [http://127.0.0.1:8000/admin/](http://127.0.0.1:8000/admin/)

В админке назначьте роль в **Профиль** пользователя (`moderator` / `accountant` / `support`).

## Структура проекта

```
ExamPython/
├── config/                 # настройки Django, urls, wsgi/asgi
├── restaurant/             # основное приложение
│   ├── models.py           # заказы, блюда, склад, чат, профили
│   ├── views.py
│   ├── forms.py
│   ├── cart.py             # корзина в сессии
│   ├── decorators.py       # доступ по ролям
│   ├── stock_reports.py
│   ├── templates/restaurant/
│   └── static/
├── media/                  # загруженные фото и фоны
├── docker-compose.yml
├── .env.example
├── manage.py
└── requirements.txt
```

## Роли и основные URL

| Роль | Примеры разделов |
|------|------------------|
| Пользователь | `/`, `/cart/`, `/checkout/`, `/cabinet/`, `/support/chat/` |
| Модератор | `/moderator/orders/`, `/moderator/write-off/`, `/moderator/dishes/add/` |
| Бухгалтер | `/accountant/ingredients/`, `/accountant/write-offs/`, `/accountant/report/income/` |
| Поддержка | `/support/inbox/` |

## Заказы: статусы

`Новый` → `Готовится` → `Доставляется` → `Выполнен` (также `Отменён`).

Меняет модератор; клиент видит прогресс на странице своего заказа.

## Склад

Движения (`StockMovement`) синхронизируют `stock_quantity` ингредиента:

- **Приход** — увеличение остатка
- **Ревизия** — остаток = фактическое количество
- **Списание** — уменьшение (модератор; бухгалтер видит журнал)

Отрицательные остатки подсвечиваются красным в интерфейсе бухгалтера.

## Полезные команды

```bash
# Остановить БД
docker compose down

# Проверка стиля
flake8

# Создать миграции после смены моделей
python manage.py makemigrations
python manage.py migrate
```

## Замечания

- Оплата на `/checkout/payment/` — заглушка (успех / ошибка / отмена).
- `DEBUG=True` и ключ в `settings.py` рассчитаны на учебный запуск; для продакшена смените `SECRET_KEY`, отключите DEBUG и настройте `ALLOWED_HOSTS`.
- Файл `.env` не коммитится (см. `.gitignore`); используйте `.env.example` как шаблон.

## Лицензия

Учебный проект (Top Academy).
