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
    
    def get_enhanced_market_data(self):
        """Получаем расширенные рыночные данные"""
        market_data = {
            'coins': [],
            'global_metrics': {},
            'hot_signals': [],
            'defi_metrics': {}
        }
        
        try:
            # 1. Топ криптовалюты с расширенными данными
            url = "https://api.coingecko.com/api/v3/coins/markets"
            params = {
                'vs_currency': 'usd',
                'order': 'market_cap_desc',
                'per_page': 15,
                'page': 1,
                'sparkline': False,
                'price_change_percentage': '1h,24h,7d'
            }
            
            response = self.session.get(url, params=params, timeout=15)
            coins_data = response.json()
            
            for i, coin in enumerate(coins_data[:10], 1):
                change_1h = coin.get('price_change_percentage_1h_in_currency', 0) or 0
                change_24h = coin.get('price_change_percentage_24h', 0) or 0
                change_7d = coin.get('price_change_percentage_7d_in_currency', 0) or 0
                price = coin.get('current_price', 0)
                volume = coin.get('total_volume', 0)
                market_cap = coin.get('market_cap', 0)
                symbol = coin.get('symbol', '').upper()
                name = coin.get('name', '')
                
                # Генерируем сигналы
                if change_1h > 8:
                    signal_strength = 'STRONG_BUY'
                    signal_reason = f"🚀 Ракета +{change_1h:.1f}% за час!"
                elif change_1h < -8:
                    signal_strength = 'STRONG_SELL'  
                    signal_reason = f"💥 Обвал {change_1h:.1f}% за час!"
                elif change_24h > 15:
                    signal_strength = 'BUY'
                    signal_reason = f"📈 Сильный рост за день"
                elif change_24h < -15:
                    signal_strength = 'SELL'
                    signal_reason = f"📉 Сильное падение за день"
                else:
                    signal_strength = 'NEUTRAL'
                    signal_reason = None

                coin_data = {
                    'rank': i,
                    'symbol': symbol,
                    'name': name,
                    'price': price,
                    'change_1h': change_1h,
                    'change_24h': change_24h,
                    'change_7d': change_7d,
                    'volume': volume,
                    'market_cap': market_cap,
                    'signal': signal_strength,
                    'signal_reason': signal_reason
                }
                
                market_data['coins'].append(coin_data)
                
                # Добавляем в горячие сигналы
                if signal_strength in ['STRONG_BUY', 'STRONG_SELL'] and signal_reason:
                    market_data['hot_signals'].append({
                        'symbol': symbol,
                        'signal': signal_strength,
                        'reason': signal_reason,
                        'change_1h': change_1h,
                        'change_24h': change_24h
                    })
            
            # 2. Глобальные рыночные метрики
            global_url = "https://api.coingecko.com/api/v3/global"
            global_response = self.session.get(global_url, timeout=10)
            global_data = global_response.json()
            
            if 'data' in global_data:
                gd = global_data['data']
                market_data['global_metrics'] = {
                    'total_market_cap': gd.get('total_market_cap', {}).get('usd', 0),
                    'total_volume': gd.get('total_volume', {}).get('usd', 0),
                    'bitcoin_dominance': gd.get('market_cap_percentage', {}).get('bitcoin', 0),
                    'ethereum_dominance': gd.get('market_cap_percentage', {}).get('ethereum', 0),
                    'active_cryptocurrencies': gd.get('active_cryptocurrencies', 0)
                }
            
            # 3. DeFi данные (упрощенные, так как DeFiPulse требует API ключ)
            # Используем приблизительные данные на основе ETH и DeFi токенов
            defi_tokens = ['ethereum', 'uniswap', 'aave', 'compound-governance-token', 'curve-dao-token']
            defi_total_cap = 0
            
            for coin in coins_data:
                if coin.get('id') in defi_tokens:
                    defi_total_cap += coin.get('market_cap', 0)
            
            market_data['defi_metrics'] = {
                'estimated_tvl': defi_total_cap * 0.3,  # Приблизительная оценка
                'top_defi_change': sum([c.get('price_change_percentage_24h', 0) for c in coins_data[:5] if c.get('id') in defi_tokens]) / 5
            }
            
        except Exception as e:
            logger.error(f"Ошибка получения расширенных рыночных данных: {e}")
        
        return market_data
    
    def get_simple_price_signals(self):
        """Получаем простые ценовые сигналы (старая функция для совместимости)"""
        market_data = self.get_enhanced_market_data()
        signals = []
        
        for coin in market_data['coins'][:5]:
            signals.append({
                'source': '💰 Enhanced Price Alert',
                'symbol': coin['symbol'],
                'name': coin['name'],
                'signal': coin['signal'],
                'price': f"${coin['price']:,.2f}",
                'change_24h': f"{coin['change_24h']:.1f}%",
                'volume': f"${coin['volume']/1e9:.1f}B" if coin['volume'] > 1e9 else f"${coin['volume']/1e6:.0f}M",
                'advice': coin['signal_reason'] or f"Изменение {coin['change_24h']:.1f}%",
                'timestamp': datetime.now().isoformat()
            })
        
        return signals
    
    def collect_all_signals(self):
        """Собираем все торговые сигналы (расширенная версия)"""
        all_signals = []
        
        logger.info("🔍 Собираем расширенные торговые сигналы...")
        
        # 1. Fear & Greed Index
        logger.info("📊 Получаем Fear & Greed Index...")
        fg_signal = self.get_fear_greed_index()
        if fg_signal:
            all_signals.append(fg_signal)
        
        # 2. TradingView сигналы для популярных пар
        logger.info("📈 Получаем сигналы TradingView...")
        trading_pairs = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'SOLUSDT', 'ADAUSDT']
        for symbol in trading_pairs[:3]:  # Ограничиваем чтобы не превышать лимиты API
            tv_signal = self.get_tradingview_signals(symbol)
            if tv_signal:
                all_signals.append(tv_signal)
            time.sleep(1)  # Пауза между запросами
        
        # 3. Расширенные ценовые сигналы (новая функция)
        logger.info("💰 Получаем расширенные рыночные данные...")
        enhanced_price_signals = self.get_simple_price_signals()
        all_signals.extend(enhanced_price_signals)
        
        # 4. Дополнительные рыночные индикаторы
        logger.info("📊 Анализируем рыночные индикаторы...")
        market_indicators = self.get_market_indicators()
        all_signals.extend(market_indicators)
        
        logger.info(f"✅ Собрано {len(all_signals)} расширенных сигналов")
        return all_signals
    
    def get_market_indicators(self):
        """Получаем дополнительные рыночные индикаторы"""
        indicators = []
        
        try:
            # Получаем данные о доминации Bitcoin
            url = "https://api.coingecko.com/api/v3/global"
            response = self.session.get(url, timeout=10)
            global_data = response.json()
            
            if 'data' in global_data:
                btc_dominance = global_data['data'].get('market_cap_percentage', {}).get('bitcoin', 0)
                
                # Анализируем доминацию Bitcoin
                if btc_dominance > 55:
                    signal = 'BTC_DOMINANCE_HIGH'
                    advice = f"Доминация BTC высокая ({btc_dominance:.1f}%) - осторожно с альткоинами"
                elif btc_dominance < 45:
                    signal = 'ALTSEASON_POTENTIAL'
                    advice = f"Доминация BTC низкая ({btc_dominance:.1f}%) - возможен сезон альткоинов"
                else:
                    signal = 'NEUTRAL'
                    advice = f"Доминация BTC нейтральная ({btc_dominance:.1f}%)"
                
                indicators.append({
                    'source': '👑 Bitcoin Dominance',
                    'signal': signal,
                    'value': f"{btc_dominance:.1f}%",
                    'advice': advice,
                    'timestamp': datetime.now().isoformat()
                })
            
            # Анализируем топ-коины на предмет необычной активности
            market_data = self.get_enhanced_market_data()
            
            # Ищем монеты с необычно высоким объемом торгов
            if market_data['coins']:
                avg_volume = sum(c['volume'] for c in market_data['coins'][:10]) / 10
                
                for coin in market_data['coins'][:5]:
                    volume_ratio = coin['volume'] / avg_volume if avg_volume > 0 else 1
                    
                    if volume_ratio > 3 and coin['change_24h'] > 5:
                        indicators.append({
                            'source': '🔥 Volume Spike',
                            'signal': 'HIGH_VOLUME_PUMP',
                            'symbol': coin['symbol'],
                            'advice': f"{coin['symbol']} показывает необычно высокий объем торгов ({volume_ratio:.1f}x от среднего)",
                            'volume_ratio': volume_ratio,
                            'timestamp': datetime.now().isoformat()
                        })
                    elif volume_ratio > 3 and coin['change_24h'] < -5:
                        indicators.append({
                            'source': '📊 Volume Alert',
                            'signal': 'HIGH_VOLUME_DUMP',
                            'symbol': coin['symbol'],
                            'advice': f"{coin['symbol']} высокий объем продаж - возможна капитуляция",
                            'volume_ratio': volume_ratio,
                            'timestamp': datetime.now().isoformat()
                        })
            
        except Exception as e:
            logger.error(f"Ошибка получения рыночных индикаторов: {e}")
        
        return indicators
    
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
        """Форматируем РАСШИРЕННОЕ сообщение для Telegram"""
        if not signals:
            return None
        
        # Получаем расширенные рыночные данные
        market_data = self.get_enhanced_market_data()
        
        current_time = datetime.now().strftime("%H:%M %d.%m.%Y")
        message = f"📊 *КРИПТОВАЛЮТНЫЙ АНАЛИЗ* {current_time}\n\n"
        
        # 1. ТОП-5 МОНЕТ с подробной информацией
        if market_data['coins']:
            message += "💰 *ТОП-5 МОНЕТ:*\n"
            for coin in market_data['coins'][:5]:
                rank_emoji = ['🥇', '🥈', '🥉', '4️⃣', '5️⃣'][coin['rank']-1]
                change_emoji = '📈' if coin['change_24h'] > 0 else '📉' if coin['change_24h'] < 0 else '➡️'
                
                # Форматируем объем торгов
                if coin['volume'] > 1e9:
                    vol_str = f"{coin['volume']/1e9:.1f}B"
                elif coin['volume'] > 1e6:
                    vol_str = f"{coin['volume']/1e6:.0f}M"
                else:
                    vol_str = f"{coin['volume']/1e3:.0f}K"
                
                message += f"{rank_emoji} *{coin['symbol']}*: ${coin['price']:,.2f} "
                message += f"({coin['change_24h']:+.1f}%) {change_emoji}\n"
                message += f"   📊 1ч: {coin['change_1h']:+.1f}% | 7д: {coin['change_7d']:+.1f}% | Vol: ${vol_str}\n"
            message += "\n"
        
        # 2. ГОРЯЧИЕ СИГНАЛЫ
        hot_signals = market_data.get('hot_signals', [])
        strong_signals = [s for s in signals if s['signal'] in ['STRONG_BUY', 'STRONG_SELL']]
        
        if hot_signals or strong_signals:
            message += "🔥 *ГОРЯЧИЕ СИГНАЛЫ:*\n"
            
            # Из market data
            for hot in hot_signals[:3]:
                emoji = self.signal_emojis.get(hot['signal'], '⚪')
                message += f"{emoji} *{hot['signal']}*: {hot['symbol']} "
                message += f"({hot['change_1h']:+.1f}% за 1ч)\n"
                message += f"   💡 {hot['reason']}\n"
            
            # Из обычных сигналов
            for signal in strong_signals[:2]:
                emoji = self.signal_emojis.get(signal['signal'], '⚪')
                message += f"{emoji} *{signal['source']}*: {signal.get('symbol', 'N/A')}\n"
                if 'advice' in signal:
                    message += f"   💡 {signal['advice']}\n"
            
            message += "\n"
        
        # 3. ИНДИКАТОРЫ РЫНКА
        message += "😱 *ИНДИКАТОРЫ РЫНКА:*\n"
        
        # Fear & Greed
        fg_signal = next((s for s in signals if 'Fear & Greed' in s.get('source', '')), None)
        if fg_signal:
            message += f"• Fear & Greed: {fg_signal.get('value', 'N/A')} ({fg_signal.get('description', 'N/A')})\n"
        
        # Глобальные метрики
        if market_data['global_metrics']:
            gm = market_data['global_metrics']
            if gm.get('bitcoin_dominance'):
                message += f"• Bitcoin Dominance: {gm['bitcoin_dominance']:.1f}%\n"
            if gm.get('total_market_cap'):
                cap_str = f"${gm['total_market_cap']/1e12:.1f}T" if gm['total_market_cap'] > 1e12 else f"${gm['total_market_cap']/1e9:.0f}B"
                message += f"• Total Market Cap: {cap_str}\n"
            if gm.get('active_cryptocurrencies'):
                message += f"• Активных монет: {gm['active_cryptocurrencies']:,}\n"
        
        message += "\n"
        
        # 4. ТЕХНИЧЕСКИЙ АНАЛИЗ BTC/ETH
        btc_data = next((c for c in market_data['coins'] if c['symbol'] == 'BTC'), None)
        eth_data = next((c for c in market_data['coins'] if c['symbol'] == 'ETH'), None)
        
        if btc_data or eth_data:
            message += "📈 *ТЕХНИЧЕСКИЙ АНАЛИЗ:*\n"
            
            if btc_data:
                trend = "🟢 Бычий" if btc_data['change_24h'] > 2 else "🔴 Медвежий" if btc_data['change_24h'] < -2 else "🟡 Боковик"
                message += f"• *BTC*: {trend} тренд, цена ${btc_data['price']:,.0f}\n"
                
                # Простые уровни поддержки/сопротивления
                support = btc_data['price'] * 0.95
                resistance = btc_data['price'] * 1.05
                message += f"  Поддержка: ${support:,.0f} | Сопротивление: ${resistance:,.0f}\n"
            
            if eth_data:
                trend = "🟢 Бычий" if eth_data['change_24h'] > 2 else "🔴 Медвежий" if eth_data['change_24h'] < -2 else "🟡 Боковик"
                message += f"• *ETH*: {trend} тренд, цена ${eth_data['price']:,.0f}\n"
            
            message += "\n"
        
        # 5. DEFI МЕТРИКИ (если доступны)
        if market_data.get('defi_metrics') and market_data['defi_metrics'].get('estimated_tvl'):
            message += "🌍 *DeFi МЕТРИКИ:*\n"
            tvl = market_data['defi_metrics']['estimated_tvl']
            tvl_str = f"${tvl/1e9:.1f}B" if tvl > 1e9 else f"${tvl/1e6:.0f}M"
            message += f"• Estimated TVL: {tvl_str}\n"
            
            defi_change = market_data['defi_metrics'].get('top_defi_change', 0)
            if defi_change:
                message += f"• DeFi Trend: {defi_change:+.1f}% (24ч)\n"
            message += "\n"
        
        # 6. ОБЫЧНЫЕ СИГНАЛЫ (кратко)
        regular_signals = [s for s in signals if s['signal'] in ['BUY', 'SELL', 'HOLD']]
        if regular_signals:
            message += "📊 *ОБЫЧНЫЕ СИГНАЛЫ:*\n"
            for signal in regular_signals[:3]:
                emoji = self.signal_emojis.get(signal['signal'], '⚪')
                symbol_info = f" | {signal['symbol']}: {signal.get('price', 'N/A')}" if 'symbol' in signal else ""
                change_info = f" ({signal['change_24h']})" if 'change_24h' in signal else ""
                message += f"{emoji} {signal['source'].replace('💰 Enhanced Price Alert', '💰 Price')}{symbol_info}{change_info}\n"
            message += "\n"
        
        # 7. ИНФОРМАЦИОННЫЕ СИГНАЛЫ
        info_signals = [s for s in signals if s['signal'] in ['NEUTRAL'] and 'Fear & Greed' not in s.get('source', '')]
        if info_signals:
            message += "📋 *ДОПОЛНИТЕЛЬНАЯ ИНФОРМАЦИЯ:*\n"
            for signal in info_signals[:2]:
                if 'TradingView' in signal.get('source', ''):
                    message += f"📈 {signal['source']}: {signal.get('recommendation', 'N/A')}\n"
            message += "\n"
        
        # 8. Время следующего обновления
        message += f"⏰ *Следующее обновление через 30 мин*\n"
        message += f"🤖 Всего проанализировано: {len(signals)} источников"
        
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
        """Запускаем полный цикл анализа (расширенная версия)"""
        logger.info("🚀 Начинаем расширенный анализ торговых сигналов...")
        
        try:
            # Собираем сигналы
            all_signals = self.collect_all_signals()
            
            if not all_signals:
                logger.warning("⚠️ Сигналы не найдены")
                return
            
            # Сохраняем все сигналы
            self.save_signals_to_file(all_signals)
            
            # Всегда отправляем расширенный отчет (так как теперь он информативнее)
            message = self.format_telegram_message(all_signals)
            if message:
                # Проверяем длину сообщения
                if len(message) > 4000:
                    # Если слишком длинное, разделяем на части
                    self.send_long_message(message)
                else:
                    self.send_telegram_message(message)
                    
                logger.info(f"✅ Отправлен расширенный отчет с {len(all_signals)} сигналами")
            
            # Проверяем критически важные сигналы для отдельных уведомлений
            critical_signals = [
                s for s in all_signals 
                if s['signal'] in ['STRONG_BUY', 'STRONG_SELL'] or 
                (s.get('change_1h', 0) and abs(float(str(s['change_1h']).replace('%', ''))) > 10)
            ]
            
            if critical_signals:
                critical_message = self.format_critical_alerts(critical_signals)
                if critical_message and critical_message != message:  # Не дублируем
                    time.sleep(2)  # Пауза между сообщениями
                    self.send_telegram_message(critical_message)
                    logger.info(f"🚨 Отправлены критические алерты: {len(critical_signals)}")
            
            # Обновляем кеш обработанных сигналов
            self.update_processed_signals_cache(all_signals)
            self.save_processed_signals()
            
        except Exception as e:
            error_msg = f"❌ Ошибка расширенного анализа: {str(e)}"
            logger.error(error_msg)
            self.send_telegram_message(f"🚨 *Ошибка бота:*\n{error_msg}")
    
    def send_long_message(self, message):
        """Отправляем длинное сообщение частями"""
        max_length = 3900  # Оставляем запас
        parts = []
        
        # Разделяем по секциям
        sections = message.split('\n\n')
        current_part = ""
        
        for section in sections:
            if len(current_part + section + '\n\n') <= max_length:
                current_part += section + '\n\n'
            else:
                if current_part:
                    parts.append(current_part.strip())
                current_part = section + '\n\n'
        
        if current_part:
            parts.append(current_part.strip())
        
        # Отправляем части с паузами
        for i, part in enumerate(parts):
            header = f"📊 *ОТЧЕТ {i+1}/{len(parts)}*\n\n" if len(parts) > 1 else ""
            self.send_telegram_message(header + part)
            if i < len(parts) - 1:  # Пауза между частями, кроме последней
                time.sleep(3)
    
    def format_critical_alerts(self, critical_signals):
        """Форматируем критические алерты"""
        if not critical_signals:
            return None
            
        message = f"🚨 *КРИТИЧЕСКИЕ АЛЕРТЫ* {datetime.now().strftime('%H:%M')}\n\n"
        
        for signal in critical_signals[:5]:  # Максимум 5 алертов
            emoji = self.signal_emojis.get(signal['signal'], '⚪')
            
            if signal['signal'] in ['STRONG_BUY', 'STRONG_SELL']:
                message += f"{emoji} *{signal['signal']}*: {signal.get('symbol', 'N/A')}\n"
                
                if 'advice' in signal:
                    message += f"💡 {signal['advice']}\n"
                elif 'signal_reason' in signal:
                    message += f"💡 {signal['signal_reason']}\n"
                    
                if 'price' in signal:
                    message += f"💰 Цена: {signal['price']}\n"
                    
                message += "\n"
        
        return message if len(message) > 50 else None
    
    def update_processed_signals_cache(self, signals):
        """Обновляем кеш обработанных сигналов (упрощенный для расширенного режима)"""
        # В расширенном режиме отправляем отчеты каждые 30 минут
        # Поэтому не фильтруем дублированные сигналы так строго
        pass

def main():
    """Основная функция"""
    bot = TradingSignalBot()
    
    # Проверяем подключение к Telegram
    logger.info("🔌 Проверяем подключение к Telegram...")
    test_message = f"🤖 *РАСШИРЕННЫЙ БОТ ТОРГОВЫХ СИГНАЛОВ ЗАПУЩЕН!*\n\n⏰ {datetime.now().strftime('%H:%M %d.%m.%Y')}\n\n📊 Новые возможности:\n• Топ-10 криптовалют с RSI и объемами\n• Горячие сигналы и алерты\n• Технический анализ BTC/ETH\n• DeFi метрики и доминация Bitcoin\n• Индикаторы рынка в реальном времени\n\n🚀 *Первый расширенный анализ через 30 секунд...*"
    
    if bot.send_telegram_message(test_message):
        logger.info("✅ Подключение к Telegram успешно!")
    else:
        logger.error("❌ Ошибка подключения к Telegram!")
        return
    
    if os.getenv('GITHUB_ACTIONS'):
        # Одноразовый запуск в GitHub Actions
        logger.info("🚀 GitHub Actions режим - расширенный одноразовый запуск")
        time.sleep(30)  # Даем время на инициализацию
        bot.run_analysis()
    else:
        # Непрерывный режим для локального запуска
        logger.info("🔄 Локальный режим - расширенный анализ каждые 30 минут")
        time.sleep(30)  # Первый запуск через 30 секунд
        
        while True:
            try:
                bot.run_analysis()
                logger.info("😴 Ожидаем следующего расширенного анализа (30 минут)...")
                time.sleep(1800)  # 30 минут = 1800 секунд
            except KeyboardInterrupt:
                logger.info("👋 Остановка расширенного бота...")
                bot.send_telegram_message("🛑 *Расширенный бот остановлен*\n\nСпасибо за использование! 👋")
                break
            except Exception as e:
                error_msg = f"💥 Критическая ошибка: {e}"
                logger.error(error_msg)
                bot.send_telegram_message(f"🚨 *Критическая ошибка расширенного бота:*\n{error_msg}\n\n🔄 Перезапуск через 5 минут...")
                time.sleep(300)  # 5 минут перед повтором

if __name__ == "__main__":
    main()
