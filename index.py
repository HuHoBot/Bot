import os
import sys
import asyncio
import argparse
import logging
from typing import Optional, Dict
from ymbotpy import logging as botpy_logging

# 本地模块导入
import libs.main as BotMain
import libs.audit as BotAudit

_log = botpy_logging.get_logger()
CONFIG_TEMPLATE = '''"""
机器人配置文件 (自动生成)
"""
APPID = "{appid}"
SECRET = "{secret}"
AUDIT = {audit}
'''

def load_config(config_path: str) -> Optional[Dict]:
    """加载配置文件"""
    try:
        from config import APPID, SECRET, AUDIT
        return {
            'APPID': APPID,
            'SECRET': SECRET,
            'AUDIT': AUDIT
        }
    except ImportError as e:
        _log.error(f"配置加载失败: {str(e)}")
        return None
    except Exception as e:
        _log.error(f"配置文件格式错误: {str(e)}")
        return None

def save_config(config_path: str, appid: str, secret: str, audit: bool):
    """保存配置文件"""
    try:
        with open(config_path, 'w', encoding='utf-8') as f:
            f.write(CONFIG_TEMPLATE.format(
                appid=appid,
                secret=secret,
                audit='True' if audit else 'False'
            ))
        _log.info("配置文件已更新")
    except IOError as e:
        _log.error(f"配置文件保存失败: {str(e)}")
        sys.exit(1)

def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description='QQ机器人启动程序')
    parser.add_argument('--webhook', action='store_true',
                      help='启用Webhook模式')
    parser.add_argument('--sandbox', action='store_true',
                      help='强制启用沙箱模式')
    return parser.parse_args()

async def run_main(appid: str, secret: str, sandbox: bool, webhook: bool):
    """主运行逻辑"""
    try:
        if webhook:
            _log.info("以Webhook模式启动...")
        else:
            _log.info("以Websocket模式启动...")
        await BotMain.main(appid, secret, sandbox,webhook)
    except KeyboardInterrupt:
        _log.info("程序已手动终止")
    except Exception as e:
        _log.error(f"运行时发生严重错误: {str(e)}")
        sys.exit(1)

def interactive_setup(config_path: str):
    """交互式配置向导"""
    print("\n== 首次配置向导 ==")
    appid = input("请输入AppID(机器人ID): ").strip()
    secret = input("请输入AppSecret(机器人密钥): ").strip()

    while True:
        audit = input("机器人是否已通过审核？(y/n): ").lower()
        if audit in ('y', 'n'):
            save_config(config_path, appid, secret, audit == 'y')
            return
        print("请输入 y 或 n")

if __name__ == '__main__':
    args = parse_args()
    config_path = os.path.join(os.getcwd(), 'config.py')

    # 配置检查与初始化
    if not os.path.isfile(config_path):
        interactive_setup(config_path)
        sys.exit("请重新启动程序以应用配置")

    config = load_config(config_path)
    if not config:
        sys.exit("配置文件加载失败，请检查config.py格式")

    # 模式判断逻辑
    if config['AUDIT'] or args.sandbox:
        sandbox = args.sandbox if args.sandbox else False
        asyncio.run(run_main(
            config['APPID'],
            config['SECRET'],
            sandbox,
            args.webhook
        ))
    else:
        # 审核模式处理流程
        BotAudit.main(config['APPID'], config['SECRET'])
