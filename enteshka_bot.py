#!/usr/bin/env python3
"""
ENTeshka Payment Bot
Запусти на любом сервере: python3 enteshka_bot.py
Или бесплатно на: replit.com, railway.app, render.com
"""

import requests
import time
import json
import os
import threading

TOKEN = "8990334231:AAHe3C5nQsxk815fyY8vewIsF-Af90Jejh0"
KASPI_NUMBER = "+7 705 222 21 64"
ADMIN_USERNAME = "panamera770"
DATA_FILE = "data.json"

PLANS = {
    "1": {"name": "1 месяц", "price": "1 190"},
    "2": {"name": "3 месяца", "price": "2 990"},
    "3": {"name": "6 месяцев", "price": "5 590"},
}

# ── Keep-alive ─────────────────────────────────────────────────────────────────

def keep_alive(interval=25 * 60):
    try:
        requests.get(f"https://api.telegram.org/bot{TOKEN}/getMe", timeout=10)
        print(f"[keep-alive] ping sent")
    except Exception as e:
        print(f"[keep-alive] error: {e}")
    threading.Timer(interval, keep_alive, args=[interval]).start()

# ── Persistence ────────────────────────────────────────────────────────────────

def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                raw = json.load(f)
            admin_chat  = raw.get("admin_chat")
            all_users   = set(raw.get("all_users", []))
            sessions    = {int(k): v for k, v in raw.get("user_sessions", {}).items()}
            pending     = {int(k): v for k, v in raw.get("pending_payments", {}).items()}
            print(f"✅ Data loaded: {len(all_users)} users, {len(pending)} pending, admin_chat={admin_chat}")
            return admin_chat, all_users, sessions, pending
        except Exception as e:
            print(f"⚠️  Could not load data: {e}")
    return None, set(), {}, {}

def save_data():
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump({
                "admin_chat":       ADMIN_CHAT,
                "all_users":        list(all_users),
                "user_sessions":    {str(k): v for k, v in user_sessions.items()},
                "pending_payments": {str(k): v for k, v in pending_payments.items()},
            }, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"⚠️  Could not save data: {e}")

# ── State ──────────────────────────────────────────────────────────────────────

ADMIN_CHAT, all_users, user_sessions, pending_payments = load_data()

# ── Helpers ────────────────────────────────────────────────────────────────────

def send(chat_id, text, parse_mode="HTML"):
    requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", json={
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode
    })

def forward_photo(file_id, caption):
    requests.post(f"https://api.telegram.org/bot{TOKEN}/sendPhoto", json={
        "chat_id": ADMIN_CHAT,
        "photo": file_id,
        "caption": caption,
        "parse_mode": "HTML"
    })

def forward_document(file_id, caption):
    requests.post(f"https://api.telegram.org/bot{TOKEN}/sendDocument", json={
        "chat_id": ADMIN_CHAT,
        "document": file_id,
        "caption": caption,
        "parse_mode": "HTML"
    })

def get_updates(offset=0):
    r = requests.get(f"https://api.telegram.org/bot{TOKEN}/getUpdates",
                     params={"offset": offset, "timeout": 30}, timeout=35)
    return r.json().get("result", [])

# ── Admin commands ─────────────────────────────────────────────────────────────

def handle_admin(chat_id, text):
    parts = text.strip().split()
    command = parts[0].lower()

    # /confirm <chat_id>
    if command == "/confirm":
        if len(parts) < 2:
            send(chat_id,
                 "Использование: <code>/confirm &lt;chat_id&gt;</code>\n\n"
                 "Chat ID указан в уведомлении об оплате.")
            return
        try:
            target_id = int(parts[1])
        except ValueError:
            send(chat_id, "❌ Неверный Chat ID.")
            return

        session  = user_sessions.get(target_id, {})
        login    = session.get("login", "неизвестен")
        plan_key = session.get("plan_key", "1")
        plan     = PLANS.get(plan_key, PLANS["1"])

        send(target_id,
             f"🎉 <b>Подписка активирована!</b>\n\n"
             f"Тариф: <b>ENTeshka {plan['name']}</b>\n"
             f"Логин: <code>{login}</code>\n\n"
             f"Вы можете войти на сайт и начать подготовку к ЕНТ.\n"
             f"Удачи! 💪")

        pending_payments.pop(target_id, None)
        save_data()

        send(chat_id,
             f"✅ Подписка подтверждена для Chat ID <code>{target_id}</code>.\n"
             f"Логин: <code>{login}</code> | Тариф: {plan['name']}")

    # /reject <chat_id>
    elif command == "/reject":
        if len(parts) < 2:
            send(chat_id, "Использование: <code>/reject &lt;chat_id&gt;</code>")
            return
        try:
            target_id = int(parts[1])
        except ValueError:
            send(chat_id, "❌ Неверный Chat ID.")
            return

        send(target_id,
             "❌ <b>Оплата не подтверждена.</b>\n\n"
             "К сожалению, мы не смогли подтвердить вашу оплату.\n"
             "Пожалуйста, проверьте скриншот и попробуйте снова или свяжитесь с поддержкой.")

        pending_payments.pop(target_id, None)
        save_data()

        send(chat_id, f"❌ Оплата отклонена для Chat ID <code>{target_id}</code>.")

    # /broadcast <message>
    elif command == "/broadcast":
        if len(parts) < 2:
            send(chat_id,
                 "Использование: <code>/broadcast &lt;текст сообщения&gt;</code>\n\n"
                 "Пример: <code>/broadcast Новый тариф уже доступен!</code>")
            return

        broadcast_text = text[len("/broadcast "):].strip()
        if not all_users:
            send(chat_id, "⚠️ Нет пользователей для рассылки.")
            return

        send(chat_id, f"⏳ Отправляю сообщение {len(all_users)} пользователям...")

        success = 0
        failed  = 0
        for uid in list(all_users):
            try:
                resp = requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", json={
                    "chat_id": uid,
                    "text": f"📢 <b>Сообщение от ENTeshka:</b>\n\n{broadcast_text}",
                    "parse_mode": "HTML"
                }, timeout=10)
                if resp.json().get("ok"):
                    success += 1
                else:
                    failed += 1
            except Exception:
                failed += 1

        send(chat_id,
             f"📢 <b>Рассылка завершена.</b>\n\n"
             f"✅ Доставлено: {success}\n"
             f"❌ Не доставлено: {failed}")

    # /pending
    elif command == "/pending":
        if not pending_payments:
            send(chat_id, "✅ Нет ожидающих оплат — все обработаны!")
            return

        lines = [f"⏳ <b>Ожидают проверки: {len(pending_payments)}</b>\n"]
        for uid, p in pending_payments.items():
            tag      = p.get("user_tag", "—")
            login    = p.get("login", "неизвестен")
            plan_key = p.get("plan_key", "1")
            plan     = PLANS.get(plan_key, PLANS["1"])
            ts       = p.get("time", "")
            lines.append(
                f"👤 {tag}\n"
                f"   Логин: <code>{login}</code>\n"
                f"   Тариф: {plan['name']} — {plan['price']} ₸\n"
                f"   Время: {ts}\n"
                f"   ✅ <code>/confirm {uid}</code>   ❌ <code>/reject {uid}</code>"
            )

        send(chat_id, "\n\n".join(lines))

    # /list [N]
    elif command == "/list":
        if not user_sessions:
            send(chat_id, "📋 Пока нет ни одного пользователя.")
            return

        try:
            limit = int(parts[1]) if len(parts) > 1 else 10
            limit = max(1, min(limit, 50))
        except ValueError:
            limit = 10

        items = list(user_sessions.items())[-limit:]
        items.reverse()

        lines = [f"📋 <b>Последние {len(items)} пользователей:</b>\n"]
        for uid, s in items:
            uname    = s.get("username", "")
            name     = s.get("name", "")
            login    = s.get("login", "неизвестен")
            plan_key = s.get("plan_key", "1")
            plan     = PLANS.get(plan_key, PLANS["1"])
            tag      = f"@{uname}" if uname else name or "—"
            lines.append(
                f"👤 {tag}\n"
                f"   Логин: <code>{login}</code>\n"
                f"   Тариф: {plan['name']}\n"
                f"   Chat ID: <code>{uid}</code>"
            )

        send(chat_id, "\n\n".join(lines))

    # /stats
    elif command == "/stats":
        send(chat_id,
             f"📊 <b>Статистика бота:</b>\n\n"
             f"👥 Всего пользователей: <b>{len(all_users)}</b>\n"
             f"🗂 Активных сессий: <b>{len(user_sessions)}</b>\n"
             f"⏳ Ожидают проверки: <b>{len(pending_payments)}</b>")

    # /help
    elif command == "/help":
        send(chat_id,
             "<b>Команды администратора:</b>\n\n"
             "/confirm &lt;chat_id&gt; — активировать подписку пользователя\n"
             "/reject &lt;chat_id&gt; — отклонить оплату\n"
             "/pending — список оплат, ожидающих проверки\n"
             "/broadcast &lt;текст&gt; — отправить сообщение всем пользователям\n"
             "/list [N] — последние N пользователей (по умолч. 10, макс. 50)\n"
             "/stats — статистика бота\n"
             "/help — показать эту справку\n\n"
             "Chat ID пользователя указан в каждом уведомлении об оплате.")

    else:
        send(chat_id, "Неизвестная команда. Напишите /help для списка команд.")

# ── Message handler ────────────────────────────────────────────────────────────

def handle(msg):
    global ADMIN_CHAT

    chat_id    = msg["chat"]["id"]
    text       = msg.get("text", "")
    username   = msg["from"].get("username", "")
    first_name = msg["from"].get("first_name", "")

    is_admin = (username == ADMIN_USERNAME) or (ADMIN_CHAT and chat_id == ADMIN_CHAT)

    # Auto-capture admin chat_id on first contact
    if username == ADMIN_USERNAME and ADMIN_CHAT is None:
        ADMIN_CHAT = chat_id
        save_data()
        print(f"✅ Admin chat captured: {ADMIN_CHAT}")
        send(chat_id,
             "✅ <b>Вы зарегистрированы как администратор.</b>\n\n"
             "Теперь вы будете получать уведомления о каждой оплате.\n\n"
             "<b>Команды:</b>\n"
             "/confirm &lt;chat_id&gt; — активировать подписку пользователя\n"
             "/reject &lt;chat_id&gt; — отклонить оплату\n"
             "/broadcast &lt;текст&gt; — рассылка всем пользователям\n"
             "/stats — статистика\n"
             "/help — справка")
        return

    # Route admin commands
    if is_admin and text.startswith("/"):
        handle_admin(chat_id, text)
        return

    # /start
    if text.startswith("/start"):
        parts    = text.split(" ")
        login    = "неизвестен"
        plan_key = "1"

        if len(parts) > 1:
            try:
                param = parts[1]
                if "_" in param:
                    login, plan_key = param.rsplit("_", 1)
            except:
                pass

        plan = PLANS.get(plan_key, PLANS["1"])

        user_sessions[chat_id] = {
            "login": login,
            "plan_key": plan_key,
            "username": username,
            "name": first_name,
        }
        all_users.add(chat_id)
        save_data()

        send(chat_id,
             f"👋 <b>Здравствуйте!</b>\n\n"
             f"Вы выбрали подписку <b>ENTeshka на {plan['name']}</b>\n\n"
             f"💳 Переведите <b>{plan['price']} ₸</b> на Kaspi:\n"
             f"<code>{KASPI_NUMBER}</code>\n\n"
             f"📸 После оплаты отправьте <b>скриншот</b> сюда\n\n"
             f"⏱ В течение <b>5 минут</b> мы активируем вашу подписку!\n\n"
             f"Ваш логин: <code>{login}</code>")

    # Payment screenshot
    elif msg.get("photo"):
        send(chat_id,
             "✅ <b>Скриншот получен!</b>\n\n"
             "Проверяем оплату — подписка будет активирована в течение 5 минут.\n"
             "Спасибо за оплату! 🎉")

        session  = user_sessions.get(chat_id, {})
        login    = session.get("login", "неизвестен")
        plan_key = session.get("plan_key", "1")
        user_tag = f"@{username}" if username else first_name

        # Track as pending
        pending_payments[chat_id] = {
            "login":    login,
            "plan_key": plan_key,
            "user_tag": user_tag,
            "time":     time.strftime("%d.%m.%Y %H:%M"),
        }
        save_data()

        if ADMIN_CHAT:
            plan     = PLANS.get(plan_key, PLANS["1"])

            caption = (
                f"💰 <b>Новая оплата!</b>\n\n"
                f"👤 Пользователь: {user_tag}\n"
                f"🆔 Логин ENTeshka: <code>{login}</code>\n"
                f"📦 Тариф: {plan['name']} — {plan['price']} ₸\n"
                f"🔗 Chat ID: <code>{chat_id}</code>\n\n"
                f"Для активации:\n<code>/confirm {chat_id}</code>\n\n"
                f"Для отклонения:\n<code>/reject {chat_id}</code>"
            )
            file_id = msg["photo"][-1]["file_id"]
            forward_photo(file_id, caption)
        else:
            print(f"⚠️  Admin not registered yet. Screenshot from {chat_id} not forwarded.")

    # Payment document (PDF, etc.)
    elif msg.get("document"):
        send(chat_id,
             "✅ <b>Документ получен!</b>\n\n"
             "Проверяем оплату — подписка будет активирована в течение 5 минут.\n"
             "Спасибо за оплату! 🎉")

        session  = user_sessions.get(chat_id, {})
        login    = session.get("login", "неизвестен")
        plan_key = session.get("plan_key", "1")
        user_tag = f"@{username}" if username else first_name

        pending_payments[chat_id] = {
            "login":    login,
            "plan_key": plan_key,
            "user_tag": user_tag,
            "time":     time.strftime("%d.%m.%Y %H:%M"),
        }
        save_data()

        if ADMIN_CHAT:
            plan    = PLANS.get(plan_key, PLANS["1"])
            caption = (
                f"💰 <b>Новая оплата (документ)!</b>\n\n"
                f"👤 Пользователь: {user_tag}\n"
                f"🆔 Логин ENTeshka: <code>{login}</code>\n"
                f"📦 Тариф: {plan['name']} — {plan['price']} ₸\n"
                f"🔗 Chat ID: <code>{chat_id}</code>\n\n"
                f"Для активации:\n<code>/confirm {chat_id}</code>\n\n"
                f"Для отклонения:\n<code>/reject {chat_id}</code>"
            )
            file_id = msg["document"]["file_id"]
            forward_document(file_id, caption)
        else:
            print(f"⚠️  Admin not registered yet. Document from {chat_id} not forwarded.")

    # Any other text
    elif text and not text.startswith("/"):
        send(chat_id,
             "Напишите /start чтобы начать оформление подписки\n\n"
             "Или отправьте скриншот оплаты если уже перевели деньги.")

# ── Main loop ──────────────────────────────────────────────────────────────────

def main():
    keep_alive()
    print("✅ ENTeshka bot started!")
    print(f"ℹ️  Users in database: {len(all_users)}")
    if ADMIN_CHAT:
        print(f"ℹ️  Admin already registered: {ADMIN_CHAT}")
    else:
        print(f"ℹ️  Send any message as @{ADMIN_USERNAME} to register as admin.")

    offset = 0
    while True:
        try:
            updates = get_updates(offset)
            for upd in updates:
                offset = upd["update_id"] + 1
                if "message" in upd:
                    handle(upd["message"])
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()
