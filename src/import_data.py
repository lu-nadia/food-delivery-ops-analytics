import os
import pandas as pd
from sqlalchemy import create_engine

# 1. Параметры подключения к твоей базе данных PostgreSQL
# Формат: postgresql://пользователь:пароль@хост:порт/имя_базы
DATABASE_URL = "postgresql://postgres:ugadause7@localhost:5432/fifa_analysis"

# 2. Путь к твоему сырому CSV-файлу
# Находим точное имя файла в папке data/raw/
raw_data_dir = "data/raw"
csv_files = [f for f in os.listdir(raw_data_dir) if f.endswith('.csv')]

if not csv_files:
    print("Ошибка: В папке data/raw/ не найдено CSV-файлов!")
    exit()

# Берем первый попавшийся CSV-файл из папки raw
csv_path = os.path.join(raw_data_dir, csv_files[0])
print(f"Читаем файл: {csv_path}...")

# Загружаем весь датасет в память через pandas
df = pd.read_csv(csv_path)

# Создаем движок подключения к Postgres
engine = create_engine(DATABASE_URL)

print("Начинаем трансформацию и загрузку данных...")

try:
    with engine.begin() as connection:
        # --- ТАБЛИЦА 1: Клубы (clubs) ---
        # Выделяем уникальные имена клубов, убираем пустые, если есть
        if 'club_name' in df.columns:
            clubs_df = df[['club_name']].dropna().drop_duplicates().reset_index(drop=True)
            # Загружаем в базу. Если такие клубы уже есть — ничего не делаем
            clubs_df.to_sql('clubs', con=connection, if_exists='append', index=False)
            print("✓ Таблица 'clubs' успешно заполнена.")
            
            # Получаем обратно id созданных клубов, чтобы связать их с игроками
            db_clubs = pd.read_sql("SELECT * FROM clubs", con=connection)
            club_mapping = dict(zip(db_clubs['club_name'], db_clubs['club_id']))
            df['club_id'] = df['club_name'].map(club_mapping)
        else:
            df['club_id'] = None

        # --- ТАБЛИЦА 2: Игроки (players) ---
        # Собираем уникальные данные самих игроков (характеристики, которые не меняются каждый матч)
        player_cols = [
            'player_id', 'player_name', 'age', 'nationality', 'team', 
            'jersey_number', 'position', 'height_cm', 'weight_kg', 
            'preferred_foot', 'club_id', 'market_value_eur'
        ]
        # Оставляем только существующие в датасете колонки
        existing_player_cols = [col for col in player_cols if col in df.columns]
        players_df = df[existing_player_cols].drop_duplicates(subset=['player_id']).reset_index(drop=True)
        
        players_df.to_sql('players', con=connection, if_exists='append', index=False)
        print("✓ Таблица 'players' успешно заполнена.")

        # --- ТАБЛИЦА 3: Матчи (matches) ---
        # Выделяем общую информацию о матчах (дата, стадион, стадия)
        match_cols = ['match_id', 'match_date', 'stadium', 'city', 'tournament_stage']
        existing_match_cols = [col for col in match_cols if col in df.columns]
        matches_df = df[existing_match_cols].drop_duplicates(subset=['match_id']).reset_index(drop=True)
        
        matches_df.to_sql('matches', con=connection, if_exists='append', index=False)
        print("✓ Таблица 'matches' успешно заполнена.")

        # --- ТАБЛИЦА 4: Статистика (player_match_stats) ---
        # Теперь берем всё остальное — это метрики перформанса игрока в конкретном матче
        # Удаляем из датасета колонки, которые ушли в другие таблицы (кроме ключей связи)
        stats_df = df.copy()
        cols_to_drop = ['player_name', 'age', 'nationality', 'team', 'jersey_number', 
                        'position', 'height_cm', 'weight_kg', 'preferred_foot', 
                        'club_name', 'market_value_eur', 'match_date', 'stadium', 
                        'city', 'tournament_stage', 'club_id'] # <-- ДОБАВИЛИ 'club_id' СЮДА
        stats_df = stats_df.drop(columns=[col for col in cols_to_drop if col in stats_df.columns])
        
        stats_df.to_sql('player_match_stats', con=connection, if_exists='append', index=False)
        print("✓ Таблица 'player_match_stats' успешно заполнена.")
        
    print("\n🎉 ЕТL-процесс успешно завершен! Все данные в базе данных.")

except Exception as e:
    print(f"\n❌ Произошла ошибка при загрузке данных: {e}")