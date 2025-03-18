import os
import asyncio
import libs.main as BotMain
import libs.audit as BotAudit
from botpy import logging

_log = logging.get_logger()    #Botpy Logger
config_path = os.path.join(os.getcwd(), 'config.py')

if __name__ == '__main__':
    try:
        # 检查config.py是否存在
        if os.path.isfile(config_path):
            try:
                from config import *
                if AUDIT:
                    #SANDBOX = input("沙箱模式？")
                    SANDBOX="y"
                    if(SANDBOX == 'y'):
                        SANDBOX = True
                    else:
                        SANDBOX = False
                    asyncio.run(BotMain.main(APPID,SECRET,SANDBOX))
                else:
                    cAUDIT = input("机器人是否已经通过开放平台审核(y/n):")
                    with open('config.py','w',encoding='utf8') as f:
                        f.write(f'APPID="{APPID}"\n')
                        f.write(f'SECRET="{SECRET}"\n')
                        if(cAUDIT == 'y'):
                            _log.info("审核通过，正在启动主程序，若未通过审核，则无法使用该机器人（可从config.py中更改）")
                            f.write(f'AUDIT=True')
                            input("按任意键继续...")
                            exit(0)
                        else:
                            f.write(f'AUDIT=False')
                    if(cAUDIT != 'y'): 
                        _log.info("正在启动审核模式...")
                        BotAudit.main(APPID,SECRET)
            except ImportError as e:
                _log.error(f"导入账号信息失败: {e}")
        else:
            _log.warning("账号信息不存在，正在新建账号")
            APPID = input("请输入AppID(机器人ID):")
            SECRET = input("请输入AppSecret(机器人密钥)")
            AUDIT = input("机器人是否已经通过开放平台审核(y/n):")
            with open('config.py','w',encoding='utf8') as f:
                f.write(f'APPID="{APPID}"\n')
                f.write(f'SECRET="{SECRET}"\n')
                if(AUDIT == 'y'):
                    f.write(f'AUDIT=True')
                else:
                    f.write(f'AUDIT=False')
            _log.info("导入账号信息完毕，请重启...")
            input("按任意键继续...")
    except KeyboardInterrupt:
        pass
    except RuntimeError:
        pass