import logging

import aiosqlite
import re
import hashlib
import secrets
import random
import string
import json
import requests
import time

import ymbotpy.errors
#from botpy import BotAPI
from ymbotpy import BotAPI

from config import APPID
from libs.SensitiveFilter import SimpleSensitiveFilter

databasePath = 'data/database.db'
latestVersion = 'data/latestVersion.json'
BotName = 'HuHoBot'
_log = logging.getLogger()

bindServerTemp = {}

url_getBedrockStatus = "https://motdbe.blackbe.work/api?host="
url_getJavaStatus = "https://motdbe.blackbe.work/api/java?host="
url_getBedrockStatusImg = "https://motdbe.blackbe.work/status_img?host="
url_getJavaStatusImg = "https://motdbe.blackbe.work/status_img/java?host="

class AsyncSQLite:
    def __init__(self, db_path):
        self.db_path = db_path

    async def connect(self):
        self.connection = await aiosqlite.connect(self.db_path)

    async def close(self):
        await self.connection.close()

    async def execute(self, query, params=None):
        if params is None:
            params = []
        async with self.connection.execute(query, params) as cursor:
            return await cursor.fetchall()

    async def fetchone(self, query, params=None):
        if params is None:
            params = []
        async with self.connection.execute(query, params) as cursor:
            return await cursor.fetchone()

    async def fetchall(self, query, params=None):
        if params is None:
            params = []
        async with self.connection.execute(query, params) as cursor:
            return await cursor.fetchall()

    async def commit(self):
        await self.connection.commit()

    async def rollback(self):
        await self.connection.rollback()

class Motd:
    def __init__(self,url) -> None:
        self.url = url

    def is_valid(self) -> bool:
        return is_valid_domain_port(self.url)
    
    def _request(self,url) -> dict:
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()  # 检查 HTTP 请求是否成功
            return response.json()  # 将返回值转换为字典
        except requests.exceptions.RequestException as e:
            return {"status":"error","msg": str(e)}
        
    def _remove_color_codes(self,text) -> str:
        # 移除颜色代码
        cleaned_text = re.sub(r"§.", "", text)
        # 移除每行开头和结尾多余的空格，并压缩多行之间的空格
        cleaned_text = re.sub(r"\s+", " ", cleaned_text.strip())
        return cleaned_text
        
    def motd_be(self) -> dict:
        motd_respone = self._request(url_getBedrockStatus+self.url)
        if(motd_respone['status'] != "online"):
            return {"online":False}
        statusText= ("\nMC 基岩版服务器状态查询\n"
                    "⭕️状态: 在线\n"
                    f"📋描述: {self._remove_color_codes(motd_respone.get('motd','').replace('.','_'))}\n"
                    f"📡延迟: {motd_respone.get('delay',-1)} ms\n"
                    f"💳协议版本: {motd_respone.get('agreement',-1)}\n"
                    f"🧰游戏版本: {motd_respone.get('version','0.0.0')}\n"
                    f"👧在线人数: {motd_respone.get('online',-1)}/{motd_respone.get('max',-1)}\n"
                    f"🚩地图名称: {motd_respone.get('level_name','world').replace('.','·')}\n"
                    f"🎗️默认模式: {motd_respone.get('gamemode','Unknown')}")
        return {'online':True,'text':statusText,'imgUrl':url_getBedrockStatusImg+self.url}
    
    def motd_je(self) -> dict:
        motd_respone = self._request(url_getJavaStatus+self.url)
        if(motd_respone['status'] != "online"):
            return {"online":False}
        statusText= ("\nMC Java服务器状态查询\n"
                    "⭕️状态:在线\n"
                    f"📋描述: {self._remove_color_codes(motd_respone.get('motd','').replace('.','_'))}\n"
                    f"💳协议版本: {motd_respone.get('agreement',-1)}\n"
                    f"🧰游戏版本: {motd_respone.get('version','0.0.0')}\n"
                    f"📡延迟: {motd_respone.get('delay',-1)} ms\n"
                    f"👧玩家在线: {motd_respone.get('online',-1)}/{motd_respone.get('max',-1)}")
        return {'online':True,'text':statusText,'imgUrl':url_getJavaStatusImg+self.url}
    
    def motd(self,platform='auto') -> dict:
        if(platform == 'auto'):
            for motd_method in [self.motd_je,self.motd_be]:
                motd_data = motd_method()
                if motd_data.get('online'):
                    return motd_data
        elif(platform == 'je'):
            motd_data = self.motd_je()
            if motd_data.get('online'):
                return motd_data
        else:
            motd_data = self.motd_be()
            if motd_data.get('online'):
                return motd_data

        return {"online": False}

class Chat:
    def __init__(self):
        self.chatTemplate = {}
        self.groupId = {}
        self.botApi = None

    def saveTemp(self,serverId:str,groupId:str,msgId:str,currentSeq=1):
        if serverId not in self.chatTemplate:
            self.chatTemplate[serverId] = {}

        if groupId not in self.chatTemplate[serverId]:
            self.chatTemplate[serverId][groupId] = []

        self.chatTemplate[serverId][groupId].append({
            "msg_id": msgId,
            "last_time": time.time(),
            "expire_at": time.time() + 5 * 60,  # 5分钟有效期
            "current_seq": currentSeq
        })
        return True

    async def postChat(self, serverId: str, msg: str):
        if serverId not in self.chatTemplate or not self.botApi:
            return False

        sent = False
        for groupId, msgId_pool in self.chatTemplate[serverId].items():
            if not msgId_pool:
                continue

            # 按最后使用时间降序排序，优先用最新消息
            msgId_pool.sort(key=lambda x: x['last_time'], reverse=True)

            for msgObj in msgId_pool:
                # 条件调整为：序列号未满 且 消息未过期（5分钟内）
                if msgObj['current_seq'] <= 5 and time.time() - msgObj['last_time'] <= 5 * 60:
                    msgObj['current_seq'] += 1
                    msgObj['last_time'] = time.time()  # 更新时间戳

                    #过滤文本信息
                    filter = SimpleSensitiveFilter()
                    output = filter.replace(msg)

                    try:
                        await self.botApi.post_group_message(
                            group_openid=groupId,
                            content=f'[聊天消息]\n{output}',
                            msg_id=msgObj['msg_id'],
                            msg_seq=msgObj['current_seq']
                        )
                    except ymbotpy.errors.ServerError  as e:
                        _log.error(f"发送群消息无效：{e}")

                    sent = True
                    break  # 每个群组只发最新一条

            # 清理过期消息（统一处理）
            self.chatTemplate[serverId][groupId] = [
                obj for obj in msgId_pool
                if obj['current_seq'] <= 5  # 新增序列号判断
                   and time.time() - obj['last_time'] <= 5 * 60
            ]

        return sent

    def postBotApi(self, botApi: BotAPI):
        self.botApi = botApi

chatManager = Chat()

#切割命令参数
def splitCommandParams(params: str):
    if not params:
        return []

    result = []
    now, in_quote = "", ""
    for word in params.split():
        if in_quote:
            in_quote += " " + word
            if word.endswith('"'):
                in_quote = in_quote.rstrip('"')
                result.append(in_quote.strip('"'))
                in_quote = ""
        else:
            if word.startswith('"') and word.endswith('"'):
                result.append(word[1:-1])
            elif word.startswith('"'):
                in_quote = word
            else:
                result.append(word)

    if in_quote:
        for word in in_quote.split():
            result.append(word)

    return [item.replace('"', '') for item in result]

#检查是否是合法的QQ
def is_valid_QQ(qqStr: str):
    qq_regex = r"^\d{5,12}$"
    # 使用正则表达式匹配
    if re.match(qq_regex, qqStr):
        return True
    else:
        return False

#Xbox ID 的合法性
def is_valid_xbox_id(xbox_id):
    # 定义Xbox ID的正则表达式规则
    pattern = r'^[a-zA-Z_][a-zA-Z0-9_ ]{2,14}[a-zA-Z0-9_]$'
    # 使用正则表达式匹配
    if re.match(pattern, xbox_id):
        return True
    else:
        return False

#域名或IP地址和端口号的合法性
def is_valid_domain_port(domain_port:str):
    pattern = r'^((?:[a-zA-Z0-9][-\w]*\.)+[a-zA-Z]{2,63}|(?:\d{1,3}\.){3}\d{1,3})(?::(\d{1,5}))?$'
    match = re.match(pattern, domain_port)
    if match:
        port = match.group(2)
        if port:
            return 1 <= int(port) <= 65535
        else:
            return True
    else:
        return False

#查询玩家昵称
async def queryName(memberData:dict):
    db = AsyncSQLite(databasePath)
    await db.connect()
    try:
        rows = await db.fetchall(f"select name from nickName where `group`='{memberData['groupId']}' and `author`='{memberData['author']}'")
    finally:
        await db.close()
    if(len(rows) > 0):
        return rows[0][0]
    return None

#添加玩家NickName
async def setNickName(memberData:dict):
    db = AsyncSQLite(databasePath)
    await db.connect()
    try:
        await db.execute('INSERT OR REPLACE INTO nickName (`group`, `author`, `name`) VALUES (?, ?, ?)', (memberData['groupId'], memberData['author'], memberData['nick']))
        await db.commit()
    finally:
        await db.close()
    return True

# 对绑定的uid生成一个hash256密钥
def generate_hash_key(input_string:str,salt_length=16):
    salt = secrets.token_hex(salt_length)
    combined = input_string + salt
    hash_object = hashlib.sha256(combined.encode('utf-8'))
    hex_dig = hash_object.hexdigest()
    return hex_dig

#获取服务器配置文件
def getServerConfig(serverId:str):
    hashKey = generate_hash_key(serverId)
    config = {
        "serverId":serverId,
        "hashKey":hashKey,
        "serverName":"server",
        "addSimulatedPlayerTip":True,
        "motdUrl": "play.easecation.net:19132",
        "chatFormat":{
            "game":"<{name}> {msg}",
            "group":"群:<{nick}> {msg}"
            }
        }
    return config

#绑定服务器
async def bindServer(groupId,config):
    serverId = config['serverId']
    hashKey = config['hashKey']

    db = AsyncSQLite(databasePath)
    await db.connect()
    try:
        await db.execute('INSERT OR REPLACE INTO bindServer (`group`, `serverId`, `hashKey`) VALUES (?, ?, ?)', (groupId,serverId,hashKey))
        await db.commit()
    finally:
        await db.close()
    

#查询绑定服务器（通过群）
async def queryBindServerByGroup(groupId):
    db = AsyncSQLite(databasePath)
    await db.connect()
    try:
        rows = await db.fetchall(f"select `group`,`serverId` from bindServer where `group`='{groupId}'")
    finally:
        await db.close()
    if(len(rows) > 0):
        return rows[0]
    return None

#查询绑定服务器（通过serverId）
async def queryBindServerById(serverId):
    db = AsyncSQLite(databasePath)
    await db.connect()
    try:
        rows = await db.fetchall(f"select * from bindServer where `serverId`='{serverId}'")
    finally:
        await db.close()
    return rows

#查询管理员
async def queryIsAdmin(groupId,author):
    db = AsyncSQLite(databasePath)
    await db.connect()
    try:
        rows = await db.fetchall(f"select * from adminList where `group`='{groupId}' and author='{author}'")
    finally:
        await db.close()
    return len(rows) > 0

#添加管理员
async def addAdmin(groupId,author):
    db = AsyncSQLite(databasePath)
    await db.connect()
    try:
        await db.execute('INSERT OR REPLACE INTO adminList (`group`, `author`) VALUES (?, ?)', (groupId,author))
        await db.commit()
    finally:
        await db.close()
    return True

#删除管理员
async def delAdmin(groupId,author):
    db = AsyncSQLite(databasePath)
    await db.connect()
    try:
        await db.execute(f"DELETE FROM adminList WHERE `group` = '{groupId}' AND author = '{author}'")
        await db.commit()
    finally:
        await db.close()
    return True

#查询是否屏蔽Motd
async def queryIsBlockMotd(groupId):
    db = AsyncSQLite(databasePath)
    await db.connect()
    try:
        rows = await db.fetchall(f"select * from blockMotd where `group`='{groupId}'")
    finally:
        await db.close()
    return len(rows) > 0

#添加屏蔽Motd
async def addBlockMotd(groupId):
    db = AsyncSQLite(databasePath)
    await db.connect()
    try:
        await db.execute('INSERT OR REPLACE INTO blockMotd (`group`) VALUES (?)', (groupId,))
        await db.commit()
    finally:
        await db.close()
    return True

#删除屏蔽Motd
async def delBlockMotd(groupId):
    db = AsyncSQLite(databasePath)
    await db.connect()
    try:
        await db.execute(f"DELETE FROM blockMotd WHERE `group` = '{groupId}'")
        await db.commit()
    finally:
        await db.close()
    return True

#查询绑定QQ
async def queryBindQQ(groupId:str,openId:str):
    db = AsyncSQLite(databasePath)
    await db.connect()
    try:
        rows = await db.fetchall(f"select `qq` from bindQQ where `groupId`='{groupId}' AND `openId`='{openId}'")
    finally:
        await db.close()
    if len(rows) > 0:
        return rows[0][0]
    return None

#查询是否已绑定QQ
async def queryIsBindQQ(groupId:str,openId:str):
    bindQQ = await queryBindQQ(groupId,openId)
    return bindQQ is not None

#添加绑定QQ
async def addBindQQ(groupId:str,openId:str,qq:str):
    db = AsyncSQLite(databasePath)
    await db.connect()
    try:
        await db.execute(
            'INSERT OR REPLACE INTO bindQQ (groupId, openId, qq) VALUES (?, ?, ?)',
            (groupId, openId, qq)
        )
        await db.commit()
    except Exception as e:
        _log.error(f"添加QQ绑定失败: {e}")
        return False
    finally:
        await db.close()
    return True

#删除绑定QQ
async def delBindQQById(groupId:str,openId:str):
    db = AsyncSQLite(databasePath)
    await db.connect()
    try:
        await db.execute(
            "DELETE FROM bindQQ WHERE groupId = ? AND openId = ?",
            (groupId, openId)
        )
        await db.commit()
    except Exception as e:
        _log.error(f"删除QQ绑定失败: {e}")
        return False
    finally:
        await db.close()
    return True

async def delBindQQByQQ(qq: str):
    """通过QQ号删除绑定"""
    db = AsyncSQLite(databasePath)
    await db.connect()
    try:
        await db.execute(
            "DELETE FROM bindQQ WHERE qq = ?",
            (qq,)
        )
        await db.commit()
    except Exception as e:
        _log.error(f"通过QQ删除绑定失败: {e}")
        return False
    finally:
        await db.close()
    return True

#查询是否是符合数字
def isNumber(data:str):
    if(data.isdigit() and int(data) >= 0):
        return True
    return False

#查询是否Guid
def isGuid(s):
    guid_pattern = re.compile(r'^[0-9a-fA-F]{32}$')
    return bool(guid_pattern.match(s))

#生成四位数验证码
def generate_randomCode():
    return ''.join(random.choices(string.digits, k=4))

#从文件获取最新版本
def getLatestVersion():
    try:
        with open(latestVersion, 'r', encoding='utf-8') as file:
            # 解析 JSON 内容并将其转换为字典
            data = json.load(file)
            return data
    except Exception as e:
        return {}

def try_parse_json(input_str: str):
    """
    尝试解析字符串是否为JSON格式
    返回元组 (是否成功, 结果字典/原字符串)
    """
    try:
        return True, json.loads(input_str)
    except json.JSONDecodeError:
        return False, input_str

def getQLogoUrl(OpenID:str,size:int = 640):
    return f"https://q.qlogo.cn/qqapp/{APPID}/{OpenID}/{size}"
