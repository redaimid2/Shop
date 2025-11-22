import vk_api
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType
from vk_api.keyboard import VkKeyboard, VkKeyboardColor
import json
import os
import time
import datetime
import requests
import threading
import asyncio
import aiohttp
from typing import Dict, Any, Optional

class WildCoinBot:
    def __init__(self, config_file="config.json"):
        self.config_file = config_file
        self.load_config()
        self.load_database()
        
        print(f"Инициализация WildShop Mini с токеном: {self.config['token'][:10]}...")
        print(f"ID группы: {self.config['id']}")
        
        try:
            self.vk_session = vk_api.VkApi(token=self.config['token'])
            self.longpoll = VkBotLongPoll(self.vk_session, self.config['id'])
            self.vk = self.vk_session.get_api()
            print("✅ Соединение с VK API установлено")
        except Exception as e:
            print(f"❌ Ошибка соединения с VK: {e}")
            raise
        
        self.active_requests = {}
        
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        
        self.payment_checker_task = None
        self.start_background_tasks()
        
        print("✅ Бот инициализирован!")
    
    def start_background_tasks(self):
        """Запускает фоновые асинхронные задачи"""
        def run_async_tasks():
            asyncio.set_event_loop(self.loop)
            self.payment_checker_task = self.loop.create_task(self.payment_checker())
            self.loop.run_forever()
        
        self.background_thread = threading.Thread(target=run_async_tasks, daemon=True)
        self.background_thread.start()
        print("✅ Фоновые задачи запущены")
    
    def load_config(self):
        if os.path.exists(self.config_file):
            with open(self.config_file, 'r', encoding='utf-8') as f:
                self.config = json.load(f)
            print("✅ Конфиг загружен")
            self._migrate_config()
        else:
            print("⚠️ Создаю конфиг по умолчанию...")
            self.config = {
                "token": "your_group_token",
                "id": "your_group_id",
                "admin_id": 123456789,
                "reserve_id": 987654321,
                "token_key": "your_secret_token",
                "number": "0000000000000000",
                "bank": "Тинькофф",
                "bay": 1000.0,
                "sell": 950.0,
                "balance": 1000,
                "balance_rub": 50000,
                "owner_id": 376393143,
                "coin_id": "your_coin_id",
                "coin_token": "your_coin_token",
                "api_url": "http://5.129.200.31/"
            }
            self.save_config()
    
    def _migrate_config(self):
        """Мигрирует старые ключи конфига на новые"""
        if 'bay' in self.config:
            if 'buy_rate' not in self.config:
                self.config['buy_rate'] = self.config['bay']
        if 'sell' in self.config:
            if 'sell_rate' not in self.config:
                self.config['sell_rate'] = self.config['sell']
        self.save_config()
    
    def save_config(self):
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(self.config, f, ensure_ascii=False, indent=4)
    
    def load_database(self):
        self.db_files = ['users.json', 'deals.json', 'transactions.json']
        for db_file in self.db_files:
            if not os.path.exists(db_file):
                print(f"⚠️ Создаю {db_file}...")
                with open(db_file, 'w', encoding='utf-8') as f:
                    json.dump({}, f, ensure_ascii=False, indent=4)
        
        with open('users.json', 'r', encoding='utf-8') as f:
            self.users = json.load(f)
        
        with open('deals.json', 'r', encoding='utf-8') as f:
            self.deals = json.load(f)
        
        with open('transactions.json', 'r', encoding='utf-8') as f:
            self.transactions = json.load(f)
        
        print(f"✅ БД загружена | Пользователей: {len(self.users)}")
    
    def save_database(self, db_name: str):
        if db_name == 'users':
            with open('users.json', 'w', encoding='utf-8') as f:
                json.dump(self.users, f, ensure_ascii=False, indent=4)
        elif db_name == 'deals':
            with open('deals.json', 'w', encoding='utf-8') as f:
                json.dump(self.deals, f, ensure_ascii=False, indent=4)
        elif db_name == 'transactions':
            with open('transactions.json', 'w', encoding='utf-8') as f:
                json.dump(self.transactions, f, ensure_ascii=False, indent=4)
    
    # ========== 🎨 КЛАВИАТУРЫ ==========
    
    def get_main_keyboard(self):
        keyboard = VkKeyboard(one_time=False)
        keyboard.add_button('💎 Купить', color=VkKeyboardColor.POSITIVE)
        keyboard.add_button('📈 Продать', color=VkKeyboardColor.NEGATIVE)
        keyboard.add_line()
        keyboard.add_button('📊 Курсы', color=VkKeyboardColor.PRIMARY)
        keyboard.add_button('👤 Профиль', color=VkKeyboardColor.SECONDARY)
        return keyboard.get_keyboard()
    
    def get_admin_keyboard(self):
        keyboard = VkKeyboard(one_time=False)
        keyboard.add_button('⚙️ Курс', color=VkKeyboardColor.PRIMARY)
        keyboard.add_button('💰 Баланс', color=VkKeyboardColor.PRIMARY)
        keyboard.add_line()
        keyboard.add_button('🏦 Реквизиты', color=VkKeyboardColor.PRIMARY)
        keyboard.add_line()
        keyboard.add_button('📊 Статистика', color=VkKeyboardColor.SECONDARY)
        keyboard.add_line()
        keyboard.add_button('🏠 В меню', color=VkKeyboardColor.NEGATIVE)
        return keyboard.get_keyboard()
    
    def get_deal_keyboard(self, deal_id):
        keyboard = VkKeyboard(inline=True)
        keyboard.add_button(f'✅ #{deal_id}', color=VkKeyboardColor.POSITIVE)
        keyboard.add_button(f'❌ #{deal_id}', color=VkKeyboardColor.NEGATIVE)
        return keyboard.get_keyboard()
    
    def get_process_keyboard(self, deal_id):
        keyboard = VkKeyboard(inline=True)
        keyboard.add_button(f'💸 Выплата #{deal_id}', color=VkKeyboardColor.POSITIVE)
        return keyboard.get_keyboard()
    
    def get_profile_keyboard(self):
        keyboard = VkKeyboard(one_time=False)
        keyboard.add_button('🏦 Банк', color=VkKeyboardColor.PRIMARY)
        keyboard.add_button('💳 Номер', color=VkKeyboardColor.PRIMARY)
        keyboard.add_line()
        keyboard.add_button('🏠 В меню', color=VkKeyboardColor.SECONDARY)
        return keyboard.get_keyboard()
    
    def get_admin_submenu_keyboard(self):
        """Клавиатура с кнопкой отмены для подменю админа"""
        keyboard = VkKeyboard(one_time=False)
        keyboard.add_button('Отмена', color=VkKeyboardColor.NEGATIVE)
        return keyboard.get_keyboard()
    
    def send_message(self, user_id, message, keyboard=None):
        try:
            params = {
                'user_id': user_id,
                'message': message,
                'random_id': 0
            }
            if keyboard:
                params['keyboard'] = keyboard
            result = self.vk.messages.send(**params)
            return result
        except Exception as e:
            print(f"❌ Ошибка отправки: {e}")
    
    # ========== 💻 АСИНХРОННЫЕ ОПЕРАЦИИ ==========
    
    async def get_balance_async(self):
        """Асинхронное получение баланса"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.config['api_url'] + 'balance',
                    json={
                        'user_id': self.config['reserve_id'],
                        'access_token': self.config['coin_token']
                    },
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    data = await response.json()
                    return data.get('data', {}).get('balance', 0)
        except Exception as e:
            print(f"❌ Ошибка баланса: {e}")
            return 0
    
    def get_balance(self):
        """Синхронная обертка"""
        try:
            return asyncio.run_coroutine_threadsafe(self.get_balance_async(), self.loop).result(timeout=10)
        except Exception as e:
            print(f"❌ Ошибка: {e}")
            return 0
    
    async def get_history_async(self, limit=10):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.config['api_url'] + 'transactions',
                    json={
                        'user_id': self.config['reserve_id'],
                        'access_token': self.config['coin_token'],
                        'type': 'in',
                        'limit': limit
                    }
                ) as response:
                    data = await response.json()
                    return data.get('data', {}).get('transactions', [])
        except Exception as e:
            print(f"❌ Ошибка истории: {e}")
            return []
    
    async def send_coins_async(self, recipient_id, amount):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.config['api_url'] + 'send',
                    json={
                        'user_id': self.config['reserve_id'],
                        'access_token': self.config['coin_token'],
                        'recipient_id': recipient_id,
                        'amount': float(amount)
                    }
                ) as response:
                    result = await response.json()
                    return result
        except Exception as e:
            print(f"❌ Ошибка отправки коинов: {e}")
            return {"status": "error", "message": str(e)}
    
    def send_coins(self, recipient_id, amount):
        try:
            return asyncio.run_coroutine_threadsafe(self.send_coins_async(recipient_id, amount), self.loop).result(timeout=30)
        except Exception as e:
            print(f"❌ Ошибка: {e}")
            return {"status": "error", "message": str(e)}
    
    # ========== 🤝 РАБОТА СО СДЕЛКАМИ ==========
    
    def create_deal(self, user_id, amount, deal_type="buy"):
        deal_number = len(self.deals) + 1
        
        if deal_type == "buy":
            amount_coins = amount
            amount_rub = (amount / 1000) * self.config.get('buy_rate', self.config.get('bay', 1000))
        else:
            amount_coins = amount
            amount_rub = (amount / 1000) * self.config.get('sell_rate', self.config.get('sell', 950))
        
        deal = {
            'id': deal_number,
            'user_id': user_id,
            'amount_rub': round(amount_rub, 2),
            'amount_coins': round(amount_coins, 2),
            'type': deal_type,
            'status': 'active',
            'created_at': time.time(),
            'expires_at': time.time() + 1800
        }
        
        self.deals[str(deal_number)] = deal
        self.save_database('deals')
        self.notify_admin(deal)
        
        return deal
    
    def notify_admin(self, deal):
        """Уведомление админу о новой сделке"""
        try:
            user_info = self.get_user_info(deal['user_id'])
            
            if deal['type'] == 'buy':
                message = f"🔔 НОВАЯ ЗАЯВКА НА ПОКУПКУ\n"
                message += f"━━━━━━━━━━━━━━━━━━━━━━━\n"
                message += f"ID заявки: #{deal['id']}\n"
                message += f"👤 Клиент: {user_info}\n"
                message += f"💎 Сумма: {deal['amount_coins']:,} WC\n"
                message += f"💰 К оплате: {deal['amount_rub']:,} RUB\n\n"
                message += f"🏦 Реквизиты для перевода:\n"
                message += f"{self.config['number']}\n"
                message += f"Банк: {self.config['bank']}\n\n"
                message += f"⏰ Создана: {self.format_time(deal['created_at'])}\n"
                message += f"⌛ Истекает: {self.format_time(deal['expires_at'])}\n"
                message += f"━━━━━━━━━━━━━━━━━━━━━━━\n"
                message += f"✋ Статус: Ожидание оплаты"
                
                self.send_message(self.config['admin_id'], message, self.get_deal_keyboard(deal['id']))
                
            else:  # sell
                user_details = self.users.get(str(deal['user_id']), {})
                user_bank = user_details.get('bank', 'Не указан')
                user_number = user_details.get('number', 'Не указан')
                
                message = f"🔔 НОВАЯ ЗАЯВКА НА ПРОДАЖУ\n"
                message += f"━━━━━━━━━━━━━━━━━━━━━━━\n"
                message += f"ID заявки: #{deal['id']}\n"
                message += f"👤 Клиент: {user_info}\n"
                message += f"💎 Продает: {deal['amount_coins']:,} WC\n"
                message += f"💰 Получит: {deal['amount_rub']:,} RUB\n\n"
                message += f"💳 Реквизиты клиента:\n"
                message += f"{user_number} ({user_bank})\n\n"
                message += f"⏰ Создана: {self.format_time(deal['created_at'])}\n"
                message += f"⌛ Истекает: {self.format_time(deal['expires_at'])}\n"
                message += f"━━━━━━━━━━━━━━━━━━━━━━━\n"
                message += f"✋ Статус: Ожидание коинов"
                
                self.send_message(self.config['admin_id'], message)
                
        except Exception as e:
            print(f"❌ Ошибка уведомления админу: {e}")
    
    def notify_sell_payment_received(self, deal):
        """Уведомление о получении коинов для продажи"""
        try:
            user_info = self.get_user_info(deal['user_id'])
            user_details = self.users.get(str(deal['user_id']), {})
            user_bank = user_details.get('bank', 'Не указан')
            user_number = user_details.get('number', 'Не указан')
            
            message = f"✅ КОИНЫ ПОЛУЧЕНЫ\n"
            message += f"━━━━━━━━━━━━━━━━━━━━━━━\n"
            message += f"ID заявки: #{deal['id']}\n"
            message += f"👤 Клиент: {user_info}\n"
            message += f"💎 Получено коинов: {deal['amount_coins']:,} WC\n"
            message += f"💰 К выплате: {deal['amount_rub']:,} RUB\n\n"
            message += f"💳 Выплата на реквизиты:\n"
            message += f"{user_number} ({user_bank})\n"
            message += f"━━━━━━━━━━━━━━━━━━━━━━━\n"
            message += f"⏳ Статус: Ожидает выплаты"
            
            self.send_message(self.config['admin_id'], message, self.get_process_keyboard(deal['id']))
        except Exception as e:
            print(f"❌ Ошибка уведомления: {e}")
    
    def get_user_info(self, user_id):
        try:
            user = self.vk.users.get(user_ids=user_id)[0]
            return f"{user['first_name']} {user['last_name']} (id{user_id})"
        except Exception as e:
            return f"id{user_id}"
    
    def format_time(self, timestamp):
        dt = datetime.datetime.fromtimestamp(timestamp)
        return dt.strftime("%H:%M %d.%m.%Y")
    
    def process_payment(self, bank: str, message: str, key: str):
        if key != self.config['token_key']:
            return {"status": "error", "message": "Invalid token"}
        
        import re
        amount_match = re.search(r'(\d+[.,]\d{2})', message)
        if not amount_match:
            return {"status": "error", "message": "Amount not found"}
        
        amount = float(amount_match.group(1).replace(',', '.'))
        
        for deal_id, deal in self.deals.items():
            if (deal['status'] == 'active' and 
                deal['type'] == 'buy' and
                deal['amount_rub'] == amount and
                time.time() < deal['expires_at']):
                
                self.complete_buy_deal_sync(deal)
                return {"status": "success", "message": "Payment processed"}
        
        return {"status": "error", "message": "No active deal found"}
    
    def complete_buy_deal_sync(self, deal):
        """Синхронное завершение заявки на покупку"""
        try:
            result = self.send_coins(deal['user_id'], deal['amount_coins'])
            
            if result.get('status') == 'success':
                deal['status'] = 'completed'
                deal['completed_at'] = time.time()
                self.save_database('deals')
                
                user_msg = f"✅ ЗАЯВКА #{deal['id']} ВЫПОЛНЕНА\n"
                user_msg += f"━━━━━━━━━━━━━━━━━━━━━━━\n"
                user_msg += f"💎 Получено: {deal['amount_coins']:,} WC\n"
                user_msg += f"💰 Оплачено: {deal['amount_rub']:,} RUB\n"
                user_msg += f"━━━━━━━━━━━━━━━━━━━━━━━\n"
                user_msg += f"⭐ Спасибо за покупку!"
                
                admin_msg = f"✅ СДЕЛКА ЗАВЕРШЕНА #{deal['id']}\n"
                admin_msg += f"━━━━━━━━━━━━━━━━━━━━━━━\n"
                admin_msg += f"💎 Переведено: {deal['amount_coins']:,} WC\n"
                admin_msg += f"👤 Клиент: {self.get_user_info(deal['user_id'])}"
                
                self.send_message(deal['user_id'], user_msg)
                self.send_message(self.config['admin_id'], admin_msg)
            else:
                deal['status'] = 'error'
                deal['error'] = result.get('message', 'Unknown error')
                self.save_database('deals')
                
                error_msg = f"❌ ОШИБКА В СДЕЛКЕ #{deal['id']}\n"
                error_msg += f"━━━━━━━━━━━━━━━━━━━━━━━\n"
                error_msg += f"⚠️ Ошибка: {deal['error']}\n"
                error_msg += f"━━━━━━━━━━━━━━━━━━━━━━━\n"
                error_msg += f"Обратитесь в поддержку"
                
                self.send_message(deal['user_id'], error_msg)
                
        except Exception as e:
            print(f"❌ Ошибка: {e}")
    
    async def payment_checker(self):
        """Проверяет переводы для заявок на продажу"""
        while True:
            try:
                history = await self.get_history_async(50)
                for transaction in history:
                    tx_id = transaction.get('id')
                    amount = transaction.get('amount', 0)
                    
                    for deal_id, deal in self.deals.items():
                        if (deal['type'] == 'sell' and 
                            deal['status'] == 'active' and
                            deal['amount_coins'] == amount and
                            not deal.get('tx_checked')):
                            
                            deal['tx_checked'] = True
                            deal['tx_id'] = tx_id
                            self.save_database('deals')
                            
                            self.notify_sell_payment_received(deal)
                            
                            user_msg = f"✅ КОИНЫ ПОЛУЧЕНЫ!\n"
                            user_msg += f"━━━━━━━━━━━━━━━━━━━━━━━\n"
                            user_msg += f"💎 Заявка: #{deal['id']}\n"
                            user_msg += f"📥 Зачислено: {deal['amount_coins']:,} WC\n"
                            user_msg += f"💰 К выплате: {deal['amount_rub']:,} RUB\n"
                            user_msg += f"━━━━━━━━━━━━━━━━━━━━━━━\n"
                            user_msg += f"⏳ Статус: В обработке"
                            
                            self.send_message(deal['user_id'], user_msg)
                            break
                
                await asyncio.sleep(60)
                        
            except Exception as e:
                print(f"❌ Ошибка проверки: {e}")
                await asyncio.sleep(60)
    
    def process_sell_deal(self, deal_id):
        """Обработка заявки на продажу после нажатия кнопки"""
        deal = self.deals.get(str(deal_id))
        if not deal:
            return
        
        try:
            deal['status'] = 'completed'
            deal['completed_at'] = time.time()
            self.save_database('deals')
            
            user_details = self.users.get(str(deal['user_id']), {})
            user_bank = user_details.get('bank', 'Не указан')
            user_number = user_details.get('number', 'Не указан')
            
            user_msg = f"✅ ЗАЯВКА #{deal['id']} ВЫПОЛНЕНА\n"
            user_msg += f"━━━━━━━━━━━━━━━━━━━━━━━\n"
            user_msg += f"💰 Выплачено: {deal['amount_rub']:,} RUB\n"
            user_msg += f"💳 На счет: {user_bank} {user_number}\n"
            user_msg += f"💎 Продано коинов: {deal['amount_coins']:,} WC\n"
            user_msg += f"━━━━━━━━━━━━━━━━━━━━━━━\n"
            user_msg += f"⭐ Спасибо за продажу!"
            
            admin_msg = f"✅ ВЫПЛАТА ВЫПОЛНЕНА #{deal['id']}\n"
            admin_msg += f"━━━━━━━━━━━━━━━━━━━━━━━\n"
            admin_msg += f"💰 Сумма: {deal['amount_rub']:,} RUB\n"
            admin_msg += f"💎 Получено коинов: {deal['amount_coins']:,} WC"
            
            self.send_message(deal['user_id'], user_msg)
            self.send_message(self.config['admin_id'], admin_msg)
                                
        except Exception as e:
            print(f"❌ Ошибка: {e}")
    
    # ========== 🛍️ ГЛАВНОЕ МЕНЮ ==========
    
    def handle_buy(self, user_id):
        self.show_buy_info(user_id)
    
    def show_buy_info(self, user_id):
        try:
            balance = self.get_balance()
            buy_rate = self.config.get('buy_rate', self.config.get('bay', 1000))
            balance_rub = self.config['balance_rub']
            
            message = f"💎 WILD SHOP - ПОКУПКА\n"
            message += f"━━━━━━━━━━━━━━━━━━━━━━━\n"
            message += f"📦 Можем продать: {balance:,} WC\n"
            message += f"💵 Резерв рублей: {balance_rub:,} RUB\n"
            message += f"💹 Курс: 1000 WC = {buy_rate:,} RUB\n"
            message += f"━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            message += f"📝 Введите количество коинов:\n"
            message += f"Пример: 1000\n"
            message += f"Или: 10к (10 тыс.)\n"
            message += f"Или: 1кк (1 млн.)"
            
            self.send_message(user_id, message)
            self.users[str(user_id)]['waiting_for'] = 'buy_amount'
            self.save_database('users')
        except Exception as e:
            print(f"❌ Ошибка: {e}")
            self.send_message(user_id, "❌ Ошибка получения курса", self.get_main_keyboard())
    
    def handle_sell(self, user_id):
        self.show_sell_info(user_id)
    
    def show_sell_info(self, user_id):
        try:
            balance = self.get_balance()
            sell_rate = self.config.get('sell_rate', self.config.get('sell', 950))
            balance_rub = self.config['balance_rub']
            
            message = f"📈 WILD SHOP - ПРОДАЖА\n"
            message += f"━━━━━━━━━━━━━━━━━━━━━━━\n"
            message += f"📦 Можем купить: {balance:,} WC\n"
            message += f"💵 Резерв рублей: {balance_rub:,} RUB\n"
            message += f"💹 Курс: 1000 WC = {sell_rate:,} RUB\n"
            message += f"━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            message += f"📝 Введите количество коинов:\n"
            message += f"Пример: 1000\n"
            message += f"Или: 10к (10 тыс.)\n"
            message += f"Или: 1кк (1 млн.)"
            
            self.send_message(user_id, message)
            self.users[str(user_id)]['waiting_for'] = 'sell_amount'
            self.save_database('users')
        except Exception as e:
            print(f"❌ Ошибка: {e}")
            self.send_message(user_id, "❌ Ошибка", self.get_main_keyboard())
    
    def handle_buy_amount(self, user_id, amount_text):
        if any(keyword in amount_text for keyword in ['Купить', 'Продать', 'Курсы', 'Профиль', 'меню']):
            self.send_message(user_id, "⚠️ Введите количество коинов", self.get_main_keyboard())
            self.users[str(user_id)]['waiting_for'] = None
            self.save_database('users')
            return
            
        try:
            if amount_text.endswith('к'):
                amount = float(amount_text[:-1].strip()) * 1000
            elif amount_text.endswith('кк'):
                amount = float(amount_text[:-2].strip()) * 1000000
            else:
                amount = float(amount_text)
            
            if amount <= 0:
                self.send_message(user_id, "❌ Сумма должна быть больше 0", self.get_main_keyboard())
                self.users[str(user_id)]['waiting_for'] = None
                self.save_database('users')
                return
            
            deal = self.create_deal(user_id, amount, "buy")
            
            message = f"✅ ЗАЯВКА #{deal['id']} СОЗДАНА\n"
            message += f"━━━━━━━━━━━━━━━━━━━━━━━\n"
            message += f"💎 Коины: {deal['amount_coins']:,} WC\n"
            message += f"💰 К оплате: {deal['amount_rub']:,} RUB\n\n"
            message += f"🏦 Реквизиты для перевода:\n"
            message += f"{self.config['number']}\n"
            message += f"Банк: {self.config['bank']}\n\n"
            message += f"⏰ Действительно до: {self.format_time(deal['expires_at'])}\n"
            message += f"━━━━━━━━━━━━━━━━━━━━━━━\n"
            message += f"⚡ Коины придут автоматически!"
            
            self.send_message(user_id, message, self.get_main_keyboard())
            
            self.users[str(user_id)]['waiting_for'] = None
            self.save_database('users')
            
        except ValueError as e:
            self.send_message(user_id, "❌ Неверный формат. Пример: 1000, 10к, 1кк", self.get_main_keyboard())
            self.users[str(user_id)]['waiting_for'] = None
            self.save_database('users')
    
    def handle_sell_amount(self, user_id, amount_text):
        if any(keyword in amount_text for keyword in ['Купить', 'Продать', 'Курсы', 'Профиль', 'меню']):
            self.send_message(user_id, "⚠️ Введите количество коинов", self.get_main_keyboard())
            self.users[str(user_id)]['waiting_for'] = None
            self.save_database('users')
            return
            
        try:
            if amount_text.endswith('к'):
                amount = float(amount_text[:-1].strip()) * 1000
            elif amount_text.endswith('кк'):
                amount = float(amount_text[:-2].strip()) * 1000000
            else:
                amount = float(amount_text)
            
            if amount <= 0:
                self.send_message(user_id, "❌ Сумма должна быть больше 0", self.get_main_keyboard())
                self.users[str(user_id)]['waiting_for'] = None
                self.save_database('users')
                return
            
            user_details = self.users.get(str(user_id), {})
            user_bank = user_details.get('bank', 'Не указан')
            user_number = user_details.get('number', 'Не указан')
            
            if user_bank == 'Не указан' or user_number == 'Не указан':
                self.send_message(user_id, "⚠️ Укажите реквизиты в профиле перед продажей", self.get_main_keyboard())
                self.users[str(user_id)]['waiting_for'] = None
                self.save_database('users')
                return
            
            deal = self.create_deal(user_id, amount, "sell")
            
            message = f"✅ ЗАЯВКА #{deal['id']} СОЗДАНА\n"
            message += f"━━━━━━━━━━━━━━━━━━━━━━━\n"
            message += f"💎 Коины: {deal['amount_coins']:,} WC\n"
            message += f"💰 Получите: {deal['amount_rub']:,} RUB\n\n"
            message += f"💳 Ваши реквизиты:\n"
            message += f"{user_number} ({user_bank})\n\n"
            message += f"🔄 Переведите коины на:\n"
            message += f"vk.com/id{self.config['reserve_id']}\n\n"
            message += f"⏰ Действительно до: {self.format_time(deal['expires_at'])}\n"
            message += f"━━━━━━━━━━━━━━━━━━━━━━━\n"
            message += f"⚡ Выплата за 5 минут!"
            
            self.send_message(user_id, message, self.get_main_keyboard())
            
            self.users[str(user_id)]['waiting_for'] = None
            self.save_database('users')
            
        except ValueError as e:
            self.send_message(user_id, "❌ Неверный формат. Пример: 1000, 10к, 1кк", self.get_main_keyboard())
            self.users[str(user_id)]['waiting_for'] = None
            self.save_database('users')
    
    def handle_profile(self, user_id):
        user_data = self.users.get(str(user_id), {})
        bank = user_data.get('bank', 'Не указан')
        number = user_data.get('number', 'Не указан')
        
        message = f"👤 ВАШ ПРОФИЛЬ\n"
        message += f"━━━━━━━━━━━━━━━━━━━━━━━\n"
        message += f"🏦 Банк: {bank}\n"
        message += f"💳 Номер счета: {number}"
        
        self.send_message(user_id, message, self.get_profile_keyboard())
        self.users[str(user_id)]['waiting_for'] = 'profile_menu'
        self.save_database('users')
    
    def send_info(self, user_id):
        try:
            balance = self.get_balance()
        except:
            balance = "Ошибка"
        
        buy_rate = self.config.get('buy_rate', self.config.get('bay', 1000))
        sell_rate = self.config.get('sell_rate', self.config.get('sell', 950))
        balance_rub = self.config['balance_rub']
        
        message = f"📊 WILD SHOP\n"
        message += f"━━━━━━━━━━━━━━━━━━━━━━━\n"
        message += f"📦 Можем купить: {balance:,} WC\n"
        message += f"💵 Резерв рублей: {balance_rub:,} RUB\n\n"
        message += f"💹 Курсы:\n"
        message += f"💎 Покупка: 1000 WC = {buy_rate:,} RUB\n"
        message += f"📈 Продажа: 1000 WC = {sell_rate:,} RUB\n"
        message += f"━━━━━━━━━━━━━━━━━━━━━━━\n"
        message += f"✅ Быстро, безопасно, надежно"
        
        self.send_message(user_id, message)
    
    def handle_admin_command(self, user_id):
        if user_id != self.config['admin_id']:
            self.send_message(user_id, "❌ Нет доступа")
            return
        
        try:
            balance = self.get_balance()
        except:
            balance = "Ошибка"
        
        buy_rate = self.config.get('buy_rate', self.config.get('bay', 1000))
        sell_rate = self.config.get('sell_rate', self.config.get('sell', 950))
        
        message = f"👑 АДМИН-ПАНЕЛЬ\n"
        message += f"━━━━━━━━━━━━━━━━━━━━━━━\n"
        message += f"💎 Баланс WC: {balance:,}\n"
        message += f"💰 Баланс RUB: {self.config['balance_rub']:,}\n\n"
        message += f"💹 Курс:\n"
        message += f"🔼 Покупка: {buy_rate:,} RUB/1000 WC\n"
        message += f"🔽 Продажа: {sell_rate:,} RUB/1000 WC\n\n"
        message += f"🏦 Реквизиты:\n"
        message += f"Банк: {self.config['bank']}\n"
        message += f"Номер: {self.config['number']}"
        
        self.send_message(user_id, message, self.get_admin_keyboard())
        self.users[str(user_id)]['waiting_for'] = 'admin_menu'
        self.save_database('users')
    
    def handle_admin_settings(self, user_id, command):
        if '⚙️' in command or 'Курс' in command:
            buy_rate = self.config.get('buy_rate', self.config.get('bay', 1000))
            sell_rate = self.config.get('sell_rate', self.config.get('sell', 950))
            
            message = f"⚙️ ИЗМЕНЕНИЕ СТАВОК\n"
            message += f"━━━━━━━━━━━━━━━━━━━━━━━\n"
            message += f"🔼 Покупка: {buy_rate:,} RUB/1000 WC\n"
            message += f"🔽 Продажа: {sell_rate:,} RUB/1000 WC\n"
            message += f"━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            message += f"Введите в формате:\n"
            message += f"0.75 0.7\n"
            message += f"(покупка продажа)"
            
            self.send_message(user_id, message, self.get_admin_submenu_keyboard())
            self.users[str(user_id)]['waiting_for'] = 'admin_change_rate'
        
        elif '💰' in command or 'Баланс' in command:
            message = f"💰 ИЗМЕНЕНИЕ БАЛАНСА\n"
            message += f"━━━━━━━━━━━━━━━━━━━━━━━\n"
            message += f"Текущий баланс RUB: {self.config['balance_rub']:,}\n"
            message += f"━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            message += f"Введите новое значение:"
            
            self.send_message(user_id, message, self.get_admin_submenu_keyboard())
            self.users[str(user_id)]['waiting_for'] = 'admin_change_balance'
        
        elif '🏦' in command or 'Реквизиты' in command:
            message = f"🏦 ИЗМЕНЕНИЕ РЕКВИЗИТОВ\n"
            message += f"━━━━━━━━━━━━━━━━━━━━━━━\n"
            message += f"Банк: {self.config['bank']}\n"
            message += f"Номер: {self.config['number']}\n"
            message += f"━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            message += f"Введите название банка:"
            
            self.send_message(user_id, message, self.get_admin_submenu_keyboard())
            self.users[str(user_id)]['waiting_for'] = 'admin_change_bank'
        
        elif '📊' in command or 'Статистика' in command:
            self.show_statistics(user_id)
        
        elif '🏠' in command or 'В меню' in command:
            self.send_message(user_id, "🏠 Главное меню", self.get_main_keyboard())
            self.users[str(user_id)]['waiting_for'] = None
            self.save_database('users')
        
        self.save_database('users')
    
    def show_statistics(self, user_id):
        """Подробная статистика"""
        total_users = len(self.users)
        total_deals = len(self.deals)
        
        waiting = sum(1 for d in self.deals.values() if d['status'] == 'active')
        completed = sum(1 for d in self.deals.values() if d['status'] == 'completed')
        cancelled = sum(1 for d in self.deals.values() if d['status'] == 'cancelled')
        error = sum(1 for d in self.deals.values() if d['status'] == 'error')
        
        buy_deals = sum(1 for d in self.deals.values() if d['type'] == 'buy')
        sell_deals = sum(1 for d in self.deals.values() if d['type'] == 'sell')
        
        total_coins = sum(d['amount_coins'] for d in self.deals.values() if d['status'] == 'completed')
        total_rub = sum(d['amount_rub'] for d in self.deals.values() if d['status'] == 'completed')
        
        message = f"📊 СТАТИСТИКА\n"
        message += f"━━━━━━━━━━━━━━━━━━━━━━━\n"
        message += f"👥 Пользователей: {total_users}\n"
        message += f"📋 Всего заявок: {total_deals}\n\n"
        message += f"🔄 ЗАЯВКИ:\n"
        message += f"💎 Покупок: {buy_deals}\n"
        message += f"📈 Продаж: {sell_deals}\n\n"
        message += f"📌 СТАТУСЫ:\n"
        message += f"⏳ В обработке: {waiting}\n"
        message += f"✅ Выполнено: {completed}\n"
        message += f"❌ Отменено: {cancelled}\n"
        message += f"⚠️ Ошибка: {error}\n\n"
        message += f"💵 ВЫПОЛНЕННЫЕ СДЕЛКИ:\n"
        message += f"💎 Коинов: {total_coins:,} WC\n"
        message += f"💰 Рублей: {total_rub:,} RUB"
        
        self.send_message(user_id, message)
    
    def handle_deal_action(self, user_id, message_text):
        """Обработка действий с заявками"""
        try:
            if '✅' in message_text:
                deal_id = int(message_text.split('#')[1])
                self.confirm_deal(user_id, deal_id)
            elif '❌' in message_text:
                deal_id = int(message_text.split('#')[1])
                self.cancel_deal(user_id, deal_id)
            elif '💸' in message_text:
                deal_id = int(message_text.split('#')[1])
                self.process_sell_deal(deal_id)
        except (ValueError, IndexError) as e:
            print(f"❌ Ошибка: {e}")
    
    def confirm_deal(self, user_id, deal_id):
        if user_id != self.config['admin_id']:
            return
        
        deal = self.deals.get(str(deal_id))
        if not deal:
            return
        
        if deal['type'] == 'buy':
            self.complete_buy_deal_sync(deal)
    
    def cancel_deal(self, user_id, deal_id):
        if user_id != self.config['admin_id']:
            return
        
        deal = self.deals.get(str(deal_id))
        if not deal:
            return
        
        deal['status'] = 'cancelled'
        deal['cancelled_at'] = time.time()
        deal['cancelled_by'] = user_id
        self.save_database('deals')
        
        self.send_message(deal['user_id'], f"❌ Заявка #{deal_id} отменена")
        self.send_message(self.config['admin_id'], f"❌ Заявка #{deal_id} отменена")
    
    def handle_admin_input(self, user_id, message_text):
        user_state = self.users[str(user_id)]['waiting_for']
        
        # ОТМЕНА
        if '❌' in message_text or message_text.lower() == 'отмена':
            self.users[str(user_id)]['waiting_for'] = 'admin_menu'
            self.save_database('users')
            self.handle_admin_command(user_id)
            return
        
        try:
            if user_state == 'admin_change_rate':
                parts = message_text.split()
                if len(parts) == 2:
                    try:
                        buy = float(parts[0])
                        sell = float(parts[1])
                        self.config['buy_rate'] = buy
                        self.config['sell_rate'] = sell
                        self.config['bay'] = buy
                        self.config['sell'] = sell
                        self.save_config()
                        message = f"✅ Курс обновлен:\n"
                        message += f"━━━━━━━━━━━━━━━━━━━━━━━\n"
                        message += f"🔼 Покупка: {buy:,} RUB/1000 WC\n"
                        message += f"🔽 Продажа: {sell:,} RUB/1000 WC"
                        self.send_message(user_id, message)
                    except ValueError:
                        self.send_message(user_id, "❌ Ошибка формата")
                else:
                    self.send_message(user_id, "❌ Формат: 1000 950")
            
            elif user_state == 'admin_change_balance':
                try:
                    value = float(message_text)
                    self.config['balance_rub'] = value
                    self.save_config()
                    self.send_message(user_id, f"✅ Баланс RUB: {value:,}")
                except ValueError:
                    self.send_message(user_id, "❌ Ошибка значения")
            
            elif user_state == 'admin_change_bank':
                self.config['bank'] = message_text
                self.save_config()
                self.send_message(user_id, f"✅ Банк: {message_text}\n\nТеперь введите номер счета:", self.get_admin_submenu_keyboard())
                self.users[str(user_id)]['waiting_for'] = 'admin_change_number'
                self.save_database('users')
                return
            
            elif user_state == 'admin_change_number':
                self.config['number'] = message_text
                self.save_config()
                self.send_message(user_id, f"✅ Номер: {message_text}\n\n🏦 Реквизиты обновлены")
        
        except Exception as e:
            print(f"❌ Ошибка: {e}")
            self.send_message(user_id, f"❌ Ошибка: {e}")
        
        self.users[str(user_id)]['waiting_for'] = 'admin_menu'
        self.save_database('users')
        self.handle_admin_command(user_id)
    
    def update_user_bank(self, user_id, bank_name):
        self.users[str(user_id)]['bank'] = bank_name
        self.save_database('users')
        self.send_message(user_id, f"✅ Банк: {bank_name}")
        self.handle_profile(user_id)
    
    def update_user_number(self, user_id, number):
        self.users[str(user_id)]['number'] = number
        self.save_database('users')
        self.send_message(user_id, f"✅ Номер: {number}")
        self.handle_profile(user_id)
    
    def run(self):
        print("\n" + "━"*40)
        print("🚀 WILD SHOP MINI - ЗАПУЩЕНА")
        print("━"*40)
        print("📡 Начало прослушивания сообщений...\n")
        
        for event in self.longpoll.listen():
            if event.type == VkBotEventType.MESSAGE_NEW:
                self.handle_message(event)
    
    def handle_message(self, event):
        user_id = event.object.message['from_id']
        message_text = event.object.message['text']
        
        if str(user_id) not in self.users:
            self.users[str(user_id)] = {
                'waiting_for': None,
                'created_at': time.time(),
                'bank': 'Не указан',
                'number': 'Не указан'
            }
            self.save_database('users')
        
        user_state = self.users[str(user_id)]['waiting_for']
        
        # Действия с заявками
        if any(x in message_text for x in ['✅', '❌', '💸']):
            self.handle_deal_action(user_id, message_text)
            return
        
        # Админ меню
        if user_state == 'admin_menu':
            admin_commands = ['⚙️', '💰', '🏦', '📊', '🏠', 'Курс', 'Баланс', 'Реквизиты', 'Статистика', 'В меню']
            if any(cmd in message_text for cmd in admin_commands):
                self.handle_admin_settings(user_id, message_text)
                return
        
        # Профиль
        if user_state == 'profile_menu':
            if '🏦' in message_text or 'Банк' in message_text:
                self.send_message(user_id, "Введите название вашего банка:")
                self.users[str(user_id)]['waiting_for'] = 'profile_bank'
                self.save_database('users')
                return
            elif '💳' in message_text or 'Номер' in message_text:
                self.send_message(user_id, "Введите номер вашего счета:")
                self.users[str(user_id)]['waiting_for'] = 'profile_number'
                self.save_database('users')
                return
            elif '🏠' in message_text or 'меню' in message_text.lower():
                self.send_message(user_id, "🏠 Главное меню", self.get_main_keyboard())
                self.users[str(user_id)]['waiting_for'] = None
                self.save_database('users')
                return
        
        if user_state and user_state.startswith('admin_'):
            self.handle_admin_input(user_id, message_text)
        elif user_state == 'profile_bank':
            self.update_user_bank(user_id, message_text)
        elif user_state == 'profile_number':
            self.update_user_number(user_id, message_text)
        elif user_state == 'buy_amount':
            self.handle_buy_amount(user_id, message_text)
        elif user_state == 'sell_amount':
            self.handle_sell_amount(user_id, message_text)
        else:
            if message_text.lower() == 'админка':
                self.handle_admin_command(user_id)
            elif '💎' in message_text:
                self.handle_buy(user_id)
            elif '📈' in message_text:
                self.handle_sell(user_id)
            elif '📊' in message_text:
                self.send_info(user_id)
            elif '👤' in message_text:
                self.handle_profile(user_id)
            else:
                self.send_message(user_id, "WILD SHOP\n\nИспользуйте кнопки", self.get_main_keyboard())


# ========== 🌐 ВЕБ-СЕРВЕР ==========

from flask import Flask, request, jsonify

app = Flask(__name__)

try:
    bot = WildCoinBot()
except Exception as e:
    print(f"\n❌ КРИТИЧЕСКАЯ ОШИБКА ИНИЦИАЛИЗАЦИИ:\n{e}")
    import traceback
    traceback.print_exc()
    exit(1)

@app.route('/payment', methods=['POST'])
def handle_payment():
    try:
        data = request.get_json()
        bank = data.get('bank')
        message = data.get('message')
        key = data.get('key')
        
        result = bot.process_payment(bank, message, key)
        return jsonify(result)
    except Exception as e:
        print(f"❌ Ошибка платежа: {e}")
        return jsonify({"status": "error", "message": str(e)})

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({
        "status": "ok",
        "message": "WildShop Mini is running"
    })

if __name__ == "__main__":
    print("\n" + "━"*50)
    print("    ⚡ WILD SHOP MINI v2.0 - PRODUCTION START ⚡")
    print("━"*50 + "\n")
    
    def run_flask():
        try:
            app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False, threaded=True)
        except Exception as e:
            print(f"❌ Ошибка Flask сервера: {e}")
    
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    print("✅ Flask сервер запущен на порту 5000\n")
    
    try:
        bot.run()
    except KeyboardInterrupt:
        print("\n\n⚠️ Бот остановлен пользователем (CTRL+C)")
