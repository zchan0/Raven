"""
Strava Token 存储模块
使用 SQLite + Fernet 对称加密
"""
import json
import sqlite3
from pathlib import Path
from cryptography.fernet import Fernet
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

@dataclass
class StravaToken:
    """Strava OAuth Token 数据结构"""
    access_token: str
    refresh_token: str
    expires_at: int  # Unix timestamp
    athlete_id: int
    athlete_name: str
    scope: str
    
    @property
    def is_expired(self) -> bool:
        """检查 token 是否过期（提前5分钟认为过期）"""
        return datetime.now().timestamp() > (self.expires_at - 300)


class TokenStore:
    """加密 Token 存储"""
    
    def __init__(self, db_path: str, encryption_key: Optional[str] = None):
        """
        Args:
            db_path: SQLite 数据库路径
            encryption_key: 加密密钥，None 时自动生成/读取
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 初始化加密
        self._init_encryption(encryption_key)
        
        # 初始化数据库
        self._init_db()
    
    def _init_encryption(self, key: Optional[str]):
        """初始化加密密钥"""
        key_file = self.db_path.parent / '.strava_key'
        
        if key:
            self.cipher = Fernet(key.encode() if isinstance(key, str) else key)
        elif key_file.exists():
            with open(key_file, 'rb') as f:
                self.cipher = Fernet(f.read())
        else:
            # 生成新密钥
            new_key = Fernet.generate_key()
            with open(key_file, 'wb') as f:
                f.write(new_key)
            # 设置文件权限（仅所有者可读）
            import os
            os.chmod(key_file, 0o600)
            self.cipher = Fernet(new_key)
    
    def _init_db(self):
        """初始化数据库表"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS strava_tokens (
                    user_id INTEGER PRIMARY KEY,
                    encrypted_token BLOB NOT NULL,
                    athlete_id INTEGER,
                    athlete_name TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS strava_sync_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    activity_id INTEGER,
                    synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    status TEXT,  -- 'success', 'failed', 'skipped'
                    error_msg TEXT
                )
            """)
            conn.commit()
    
    def _encrypt(self, data: str) -> bytes:
        """加密数据"""
        return self.cipher.encrypt(data.encode())
    
    def _decrypt(self, data: bytes) -> str:
        """解密数据"""
        return self.cipher.decrypt(data).decode()
    
    def save_token(self, user_id: int, token: StravaToken):
        """保存加密后的 token"""
        token_json = json.dumps({
            'access_token': token.access_token,
            'refresh_token': token.refresh_token,
            'expires_at': token.expires_at,
            'scope': token.scope
        })
        encrypted = self._encrypt(token_json)
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO strava_tokens 
                (user_id, encrypted_token, athlete_id, athlete_name, updated_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (user_id, encrypted, token.athlete_id, token.athlete_name))
            conn.commit()
    
    def get_token(self, user_id: int) -> Optional[StravaToken]:
        """获取并解密 token"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT encrypted_token, athlete_id, athlete_name FROM strava_tokens WHERE user_id = ?",
                (user_id,)
            )
            row = cursor.fetchone()
            
            if not row:
                return None
            
            encrypted_token, athlete_id, athlete_name = row
            token_data = json.loads(self._decrypt(encrypted_token))
            
            return StravaToken(
                access_token=token_data['access_token'],
                refresh_token=token_data['refresh_token'],
                expires_at=token_data['expires_at'],
                athlete_id=athlete_id,
                athlete_name=athlete_name,
                scope=token_data.get('scope', 'read')
            )
    
    def delete_token(self, user_id: int):
        """删除 token（用户取消授权时）"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM strava_tokens WHERE user_id = ?", (user_id,))
            conn.commit()
    
    def log_sync(self, user_id: int, activity_id: Optional[int], 
                 status: str, error_msg: Optional[str] = None):
        """记录同步日志"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO strava_sync_log (user_id, activity_id, status, error_msg)
                VALUES (?, ?, ?, ?)
            """, (user_id, activity_id, status, error_msg))
            conn.commit()
    
    def get_last_sync_time(self, user_id: int) -> Optional[datetime]:
        """获取上次成功同步时间"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT MAX(synced_at) FROM strava_sync_log 
                WHERE user_id = ? AND status = 'success'
            """, (user_id,))
            row = cursor.fetchone()
            if row and row[0]:
                return datetime.fromisoformat(row[0])
            return None


# 使用示例
if __name__ == "__main__":
    store = TokenStore("./data/strava_tokens.db")
    
    # 保存 token
    token = StravaToken(
        access_token="abc123",
        refresh_token="xyz789",
        expires_at=int((datetime.now() + timedelta(hours=6)).timestamp()),
        athlete_id=12345,
        athlete_name="Cc",
        scope="read,activity:read"
    )
    store.save_token(user_id=331345727, token=token)
    
    # 读取 token
    retrieved = store.get_token(331345727)
    print(f"Token for {retrieved.athlete_name}: expired={retrieved.is_expired}")
