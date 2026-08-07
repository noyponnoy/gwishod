# GW VPN — Веб-админ-панель

Полноценная веб-админ-панель для управления API-сервером GW VPN.
Работает **параллельно** с Telegram-ботом — оба обращаются к одним
и тем же API-эндпоинтам, поэтому данные всегда синхронизированы.

## Архитектура

```
panel/
├── backend/          # FastAPI: авторизация (JWT) + прокси к API + QR-декодер
│   ├── app.py        # точка входа (uvicorn backend.app:app)
│   ├── config.py     # конфиг из .env
│   ├── auth.py       # логин/пароль → JWT в HttpOnly-cookie
│   ├── proxy.py      # сквозной прокси /api/proxy/* → /vpn/api/v1/bot/*
│   ├── api_monitor.py# фоновый мониторинг здоровья API
│   ├── qr_decoder.py # расшифровка QR-кодов (RSA+AES, как в боте)
│   └── api_extras.py # эндпоинт /api/qr/decode
├── frontend/         # React SPA (Vite + TypeScript)
│   └── src/
│       ├── pages/    # Dashboard, Users, Tariffs, Invoices, Servers, Settings
│       ├── components/# Layout, Modal, Icon, ConfirmDialog
│       ├── context/  # Auth, Theme, Toast
│       ├── api/      # клиент к бекенду панели
│       └── styles/   # CSS-переменные (тёмная/светлая тема)
└── dist/             # собранная статика (после npm run build)
```

**Ключевое решение:** бекенд панели — тонкий слой авторизации + прокси.
Он не лезёт в MongoDB напрямую, а дёргает те же `/vpn/api/v1/bot/*`
эндпоинты, что и бот. Отсюда 100% перенос функционала без дублирования
логики и полная синхронизация бота и сайта.

## Возможности (полный аналог бота)

- **Дашборд** — аналитика по юзерам и серверам с автообновлением (5 сек),
  индикатор здоровья API.
- **Пользователи** — список с пагинацией, карточка с деталями,
  выдача/отзыв Premium (1/3/7/30/90/180 дней).
- **Поиск** — по Device-ID/Email, по мнемонике (12 слов), по QR-коду.
- **Тарифы** — CRUD (создание/редактирование/удаление).
- **Платежи** — история с пагинацией и фильтром по статусу.
- **IKEv2** — список, вкл/выкл, переименование страны, удаление.
- **VLESS** — список, карточка (8 полей), редактирование, создание, удаление.
- **AWG** — список, toggle status/premium, редактирование, удаление.
- **Настройки** — админы панели (добавление/удаление), смена пароля.

## Запуск (dev)

### 1. Бекенд

```powershell
cd panel\backend
# создайте venv и установите зависимости
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt

# создайте .env (скопируйте из .env.example и заполните)
copy ..\.env.example ..\.env

# запуск
uvicorn app:app --reload --port 8000
```

Первый запуск создаст `panel_admins.json` с дефолтным админом
**admin / admin** — **обязательно смените пароль** после входа
(Настройки → Сменить пароль).

### 2. Фронтенд

```powershell
cd panel\frontend
npm install
npm run dev
```

Vite запустится на `http://localhost:5173` с прокси на бекенд `:8000`.

## Запуск (prod)

```powershell
# Собрать фронтенд
cd panel\frontend
npm run build    # → panel\dist\

# Запустить один процесс uvicorn (отдаёт и API, и статику)
cd panel\backend
uvicorn app:app --host 0.0.0.0 --port 8000
```

Откройте `http://ваш-сервер:8000` — панель готова.

## Безопасность

- JWT хранится в **HttpOnly-cookie** (недоступен из JS).
- Все `/api/*` роуты (кроме `/api/auth/login` и health-check) защищены.
- Пароли — bcrypt-хэши.
- В проде используйте HTTPS (cookie ставится с `secure=True`).

## Темы

Тёмная и светлая темы с автоматическим определением системной.
Ручной переключатель в topbar, выбор сохраняется в `localStorage`.
Полная адаптивность: sidebar → drawer + bottom-nav на мобильных,
таблицы → карточки на узких экранах.
