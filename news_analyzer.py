#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🚀 Анализатор торговых сигналов с отправкой в Telegram
Собирает BUY/SELL сигналы и отправляет в Telegram каждые 30 минут
"""

import requests
from bs4 import BeautifulSoup
import json
import re
from datetime import datetime, timedelta
import time
import os
import logging
from urllib.parse import urljoin, urlparse, quote_plus
import hashlib
from collections import defaultdict, Counter

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class TradingSignalBot:
    def __init__(self):
        # Telegram настройки
        self.telegram_token = "8023307419:AAEepsXhohQJXZD1PLB5WJBxgu4DdqUco7s"
        self.telegram_user_id = "7463905425"
        self.telegram_api = f"https://api.telegram.org/bot{self.telegram_token}"
        
        # Настройки запросов
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })
        
        # Источники торговых сигналов
        self.signal_sources = {
            'fear_greed': {
                'url': 'https://alternative.me/crypto/fear-and-greed-index/',
                'name': '😱 Fear & Greed Index',
                'type': 'index'
            },
            'messari': {
                'url': 'https://messari.io/screener',
                'name': '📊 Messari Ratings',
                'type': 'ratings'
            },
            'cryptorank': {
                'url': 'https://cryptorank.io/',
                'name': '🏆 CryptoRank',
                'type': 'rankings'
            },
            'tradingview_btc': {
                'url': 'https://www.tradingview.com/symbols/BTCUSDT/technicals/',
                'name': '📈 TradingView BTC',
                'type': 'technical'
            },
            'tradingview_eth': {
                'url': 'https://www.tradingview.com/symbols/ETHUSDT/technicals/',
                'name': '📈 TradingView ETH', 
                'type': 'technical'
            }
        }
        
        # Кеш обработанных сигналов
        self.processed_signals = self.load_processed_signals()
        
        # Эмодзи для сигналов
        self.signal_emojis = {
            'BUY': '🟢',
            'SELL': '🔴', 
            'HOLD': '🟡',
            'STRONG_BUY': '💚',
            'STRONG_SELL': '❤️',
            'NEUTRAL': '⚪'
        }
        
    def load_processed_signals(self):
        """Загружаем кеш обработанных сигналов"""
        try:
            with open('processed_signals.json', 'r') as f:
                return set(json.load(f))
        except FileNotFoundError:
            return set()
    
    def save_processed_signals(self):
        """Сохраняем кеш обработанных сигналов"""
        with open('processed_signals.json', 'w') as f:
            json.dump(list(self.processed_signals), f)
    
    def send_telegram_message(self, message):
        """Отправляем сообщение в Telegram"""
        try:
            # Ограничиваем длину сообщения (Telegram лимит 4096 символов)
            if len(message) > 4000:
                message = message[:3950] + "\n\n✂️ *Сообщение обрезано*"
            
            url = f"{self.telegram_api}/sendMessage"
            payload = {
                'chat_id': self.telegram_user_id,
                'text': message,
                'parse_mode': 'Markdown',
                'disable_web_page_preview': True
            }
            
            response = requests.post(url, json=payload, timeout=10)
            response.raise_for_status()
            
            logger.info("✅ Сообщение отправлено в Telegram")
            return True
            
        except Exception as e:
            logger.error(f"❌ Ошибка отправки в Telegram: {e}")
            return False
    
    def get_fear_greed_index(self):
        """Получаем индекс страха и жадности"""
        try:
            url = "https://api.alternative.me/fng/"
            response = self.session.get(url, timeout=10)
            data = response.json()
            
            if data['data']:
                value = int(data['data'][0]['value'])
                classification = data['data'][0]['value_classification']
                
                # Определяем сигнал
                if value <= 25:
                    signal = 'STRONG_BUY'
                    advice = 'Время покупать! Экстремальный страх'
                elif value <= 45:
                    signal = 'BUY'
                    advice = 'Хорошее время для покупки'
                elif value >= 75:
                    signal = 'SELL'
                    advice = 'Осторожно! Рынок в жадности'
                else:
                    signal = 'NEUTRAL'
                    advice = 'Нейтральное состояние рынка'
                
                return {
                    'source': '😱 Fear & Greed',
                    'signal': signal,
                    'value': f"{value}/100",
                    'description': classification,
                    'advice': advice,
                    'timestamp': datetime.now().isoformat()
                }
        except Exception as e:
            logger.error(f"Ошибка получения Fear & Greed: {e}")
        
        return None
    
    def get_tradingview_signals(self, symbol='BTCUSDT'):
        """Получаем сигналы с TradingView (упрощенная версия)"""
        try:
            # Используем публичное API для получения технических индикаторов
            url = f"https://scanner.tradingview.com/crypto/scan"
            
            payload = {
                "filter": [{"left": "name", "operation": "match", "right": symbol}],
                "columns": ["name", "Recommend.All", "RSI", "MACD.macd", "close"]
            }
            
            response = self.session.post(url, json=payload, timeout=15)
            data = response.json()
            
            if data.get('data') and len(data['data']) > 0:
                row = data['data'][0]
                recommendation = row['d'][1]  # Общая рекомендация
                rsi = row['d'][2]
                price = row['d'][4]
                
                # Преобразуем числовую рекомендацию в сигнал
                if recommendation > 0.5:
                    signal = 'BUY'
                elif recommendation > 0.1:
                    signal = 'HOLD'
                elif recommendation < -0.5:
                    signal = 'SELL'
                else:
                    signal = 'NEUTRAL'
                
                return {
                    'source': f'📈 TradingView {symbol[:3]}',
                    'symbol': symbol,
                    'signal': signal,
                    'price': f"${price:,.2f}",
                    'rsi': f"{rsi:.1f}",
                    'recommendation': f"{recommendation:.2f}",
                    'timestamp': datetime.now().isoformat()
                }
                
        except Exception as e:
            logger.error(f"Ошибка получения TradingView сигналов для {symbol}: {e}")
        
        return None
    
    def get_simple_price_signals(self):
        """Получаем простые ценовые сигналы"""
        signals = []
        
        try:
            # Получаем данные по топ криптовалютам
            url = "https://api.coingecko.com/api/v3/coins/markets"
            params = {
                'vs_currency': 'usd',
                'order': 'market_cap_desc',
                'per_page': 10,
                'page': 1,
                'sparkline': False,
                'price_change_percentage': '24h'
            }
            
            response = self.session.get(url, params=params, timeout=10)
            data = response.json()
            
            for coin in data[:5]:  # Топ 5 монет
                change_24h = coin.get('price_change_percentage_24h', 0)
                price = coin.get('current_price', 0)
                name = coin.get('name', '')
                symbol = coin.get('symbol', '').upper()
                
                # Генерируем простые сигналы на основе изменения цены
                if change_24h > 10:
                    signal = 'STRONG_BUY'
                    advice = f"Сильный рост +{change_24h:.1f}%"
                elif change_24h > 5:
                    signal = 'BUY'
                    advice = f"Рост +{change_24h:.1f}%"
                elif change_24h < -10:
                    signal = 'STRONG_SELL'
                    advice = f"Сильное падение {change_24h:.1f}%"
                elif change_24h < -5:
                    signal = 'SELL'
                    advice = f"Падение {change_24h:.1f}%"
                else:
                    signal = 'NEUTRAL'
                    advice = f"Изменение {change_24h:.1f}%"
                
                signals.append({
                    'source': '💰 Price Alert',
                    'symbol': symbol,
                    'name': name,
                    'signal': signal,
                    'price': f"${price:,.2f}",
                    'change_24h': f"{change_24h:.1f}%",
                    'advice': advice,
                    'timestamp': datetime.now().isoformat()
                })
                
        except Exception as e:
            logger.error(f"Ошибка получения ценовых сигналов: {e}")
        
        return signals
    
    def collect_all_signals(self):
        """Собираем все торговые сигналы"""
        all_signals = []
        
        logger.info("🔍 Собираем торговые сигналы...")
        
        # 1. Fear & Greed Index
        logger.info("📊 Получаем Fear & Greed Index...")
        fg_signal = self.get_fear_greed_index()
        if fg_signal:
            all_signals.append(fg_signal)
        
        # 2. TradingView сигналы для BTC и ETH
        logger.info("📈 Получаем сигналы TradingView...")
        for symbol in ['BTCUSDT', 'ETHUSDT']:
            tv_signal = self.get_tradingview_signals(symbol)
            if tv_signal:
                all_signals.append(tv_signal)
            time.sleep(1)  # Пауза между запросами
        
        # 3. Простые ценовые сигналы
        logger.info("💰 Получаем ценовые сигналы...")
        price_signals = self.get_simple_price_signals()
        all_signals.extend(price_signals)
        
        logger.info(f"✅ Собрано {len(all_signals)} сигналов")
        return all_signals
    
    def filter_new_signals(self, signals):
        """Фильтруем только новые сигналы"""
        new_signals = []
        
        for signal in signals:
            # Создаем уникальный хеш для сигнала
            signal_key = f"{signal['source']}_{signal.get('symbol', '')}_{signal['signal']}"
            signal_hash = hashlib.md5(signal_key.encode()).hexdigest()
            
            if signal_hash not in self.processed_signals:
                new_signals.append(signal)
                self.processed_signals.add(signal_hash)
        
        return new_signals
    
    def format_telegram_message(self, signals):
        """Форматируем сообщение для Telegram"""
        if not signals:
            return None
        
        # Заголовок с временем
        current_time = datetime.now().strftime("%H:%M %d.%m.%Y")
        message = f"🚀 *Торговые сигналы* {current_time}\n\n"
        
        # Группируем сигналы по типу
        strong_signals = []
        regular_signals = []
        info_signals = []
        
        for signal in signals:
            if signal['signal'] in ['STRONG_BUY', 'STRONG_SELL']:
                strong_signals.append(signal)
            elif signal['signal'] in ['BUY', 'SELL']:
                regular_signals.append(signal)
            else:
                info_signals.append(signal)
        
        # Сначала сильные сигналы
        if strong_signals:
            message += "🔥 *СИЛЬНЫЕ СИГНАЛЫ:*\n"
            for signal in strong_signals:
                emoji = self.signal_emojis.get(signal['signal'], '⚪')
                message += f"{emoji} *{signal['source']}*\n"
                
                if 'symbol' in signal:
                    message += f"   💎 {signal['symbol']} - {signal.get('price', 'N/A')}\n"
                
                message += f"   📊 Сигнал: *{signal['signal']}*\n"
                
                if 'advice' in signal:
                    message += f"   💡 {signal['advice']}\n"
                elif 'change_24h' in signal:
                    message += f"   📈 24ч: {signal['change_24h']}\n"
                
                message += "\n"
        
        # Обычные сигналы
        if regular_signals:
            message += "📊 *ОБЫЧНЫЕ СИГНАЛЫ:*\n"
            for signal in regular_signals:
                emoji = self.signal_emojis.get(signal['signal'], '⚪')
                message += f"{emoji} {signal['source']}"
                
                if 'symbol' in signal:
                    message += f" | {signal['symbol']}: {signal.get('price', 'N/A')}"
                
                if 'change_24h' in signal:
                    message += f" ({signal['change_24h']})"
                
                message += "\n"
        
        # Информационные сигналы (кратко)
        if info_signals:
            message += "\n📋 *ОБЩАЯ ИНФОРМАЦИЯ:*\n"
            for signal in info_signals:
                if 'value' in signal:  # Fear & Greed
                    message += f"😱 Индекс страха: {signal['value']} - {signal['description']}\n"
        
        message += f"\n⏰ Следующее обновление через 30 мин"
        
        return message
    
    def save_signals_to_file(self, signals):
        """Сохраняем сигналы в файл для анализа"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M')
        
        # Детальные данные
        with open(f'signals_{timestamp}.json', 'w', encoding='utf-8') as f:
            json.dump(signals, f, ensure_ascii=False, indent=2)
        
        # Последние сигналы
        with open('latest_signals.json', 'w', encoding='utf-8') as f:
            json.dump(signals, f, ensure_ascii=False, indent=2)
        
        logger.info(f"💾 Сигналы сохранены: signals_{timestamp}.json")
    
    def run_analysis(self):
        """Запускаем полный цикл анализа"""
        logger.info("🚀 Начинаем анализ торговых сигналов...")
        
        try:
            # Собираем сигналы
            all_signals = self.collect_all_signals()
            
            if not all_signals:
                logger.warning("⚠️ Сигналы не найдены")
                return
            
            # Фильтруем новые сигналы
            new_signals = self.filter_new_signals(all_signals)
            
            # Сохраняем все сигналы
            self.save_signals_to_file(all_signals)
            self.save_processed_signals()
            
            # Если есть новые сигналы - отправляем в Telegram
            if new_signals:
                message = self.format_telegram_message(new_signals)
                if message:
                    self.send_telegram_message(message)
                    logger.info(f"✅ Отправлено {len(new_signals)} новых сигналов")
                else:
                    logger.info("📝 Нет новых сигналов для отправки")
            else:
                # Отправляем краткую сводку, если новых сигналов нет
                summary_message = f"📊 *Сводка {datetime.now().strftime('%H:%M')}*\n\n"
                summary_message += f"Всего проанализировано: {len(all_signals)} сигналов\n"
                summary_message += "🔄 Новых сигналов нет\n\n"
                summary_message += "⏰ Следующая проверка через 30 мин"
                
                self.send_telegram_message(summary_message)
                logger.info("📋 Отправлена сводка (новых сигналов нет)")
            
        except Exception as e:
            error_msg = f"❌ Ошибка анализа: {str(e)}"
            logger.error(error_msg)
            self.send_telegram_message(f"🚨 *Ошибка бота:*\n{error_msg}")

def main():
    """Основная функция"""
    bot = TradingSignalBot()
    
    # Проверяем подключение к Telegram
    logger.info("🔌 Проверяем подключение к Telegram...")
    test_message = f"🤖 *Бот торговых сигналов запущен!*\n\n⏰ {datetime.now().strftime('%H:%M %d.%m.%Y')}\n\n📡 Первый анализ через 30 секунд..."
    
    if bot.send_telegram_message(test_message):
        logger.info("✅ Подключение к Telegram успешно!")
    else:
        logger.error("❌ Ошибка подключения к Telegram!")
        return
    
    if os.getenv('GITHUB_ACTIONS'):
        # Одноразовый запуск в GitHub Actions
        logger.info("🚀 GitHub Actions режим - одноразовый запуск")
        time.sleep(30)  # Даем время на инициализацию
        bot.run_analysis()
    else:
        # Непрерывный режим для локального запуска
        logger.info("🔄 Локальный режим - запуск каждые 30 минут")
        time.sleep(30)  # Первый запуск через 30 секунд
        
        while True:
            try:
                bot.run_analysis()
                logger.info("😴 Ожидаем следующего цикла (30 минут)...")
                time.sleep(1800)  # 30 минут = 1800 секунд
            except KeyboardInterrupt:
                logger.info("👋 Остановка бота...")
                bot.send_telegram_message("🛑 *Бот остановлен*\n\nДо встречи! 👋")
                break
            except Exception as e:
                error_msg = f"💥 Критическая ошибка: {e}"
                logger.error(error_msg)
                bot.send_telegram_message(f"🚨 *Критическая ошибка бота:*\n{error_msg}\n\n🔄 Перезапуск через 5 минут...")
                time.sleep(300)  # 5 минут перед повтором

if __name__ == "__main__":
    main()
