# -*- coding: utf-8 -*-

import signal

from flask import Flask, request
import requests
import importlib.util
import os
import json
import threading
import sys
import subprocess
import platform
import ctypes

flora_logo = "GJBOT-FloraBot"
flora_server = Flask("FloraBot", template_folder="FloraBot", static_folder="FloraBot")
flora_host = "127.0.0.1"
flora_port = 3003
framework_address = "127.0.0.1:3000"
bot_qq = 0
administrator = []
auto_install = False

flora_version = "v1.01"
plugins_dict = {}  # 插件对象字典
plugins_info_dict = {}  # 插件信息字典


def load_config():  # 加载FloraBot配置文件函数
    global auto_install, flora_host, flora_port, framework_address, bot_qq, administrator
    if os.path.isfile("./Config.json"):  # 若文件存在
        with open("./Config.json", "r", encoding="UTF-8") as read_flora_config:
            flora_config = json.loads(read_flora_config.read())
        auto_install = flora_config.get("AutoInstallLibraries")
        flora_host = flora_config.get("FloraHost")
        flora_api.update({"FloraHost": flora_host})
        flora_port = flora_config.get("FloraPort")
        flora_api.update({"FloraPort": flora_port})
        framework_address = flora_config.get("FrameworkAddress")
        flora_api.update({"FrameworkAddress": framework_address})
        bot_qq = flora_config.get("BotQQ")
        flora_api.update({"BotQQ": bot_qq})
        administrator = flora_config.get("Administrator")
        flora_api.update({"Administrator": administrator})
    else:  # 若文件不存在
        print("FloraBot 启动失败, 未找到配置文件 Config.json")
        with open("./Config.json", "w", encoding="UTF-8") as write_flora_config:
            write_flora_config.write(json.dumps(
                {"AutoInstallLibraries": True, "FloraHost": "127.0.0.1", "FloraPort": 3003,
                 "FrameworkAddress": "127.0.0.1:3000", "BotQQ": 0, "Administrator": [0]}, ensure_ascii=False, indent=4))
        print("已生成一个新的配置文件 Config.json , 请修改后再次启动 FloraBot")
        exit()


def send_msg(msg: str, uid: str | int, gid: str | int | None,
             mid: str | int | None = None):  # 发送信息函数,msg: 正文,uid: QQ号,gid: 群号,mid: 消息编号
    url = f"http://{framework_address}"
    data = {}
    if mid is not None:  # 当消息编号不为None时,则发送的消息为回复
        data.update({"message": f"[CQ:reply,id={mid}]{msg}"})
    else:  # 反之为普通消息
        data.update({"message": msg})
    if gid is not None:  # 当群号不为None时,则发送给群聊
        url += f"/send_group_msg"
        data.update({"group_id": gid})
    else:  # 反之为私聊
        url += f"/send_private_msg"
        data.update({"user_id": uid})
    try:
        requests.post(url, json=data, timeout=5)  # 提交发送消息
    except requests.exceptions.RequestException:
        pass


def install_libraries(libraries_name: str):
    if importlib.util.find_spec(libraries_name) is None:
        print(f"正在安装 {libraries_name} 库...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", libraries_name])
            print(f"{libraries_name} 库安装完成")
        except subprocess.CalledProcessError:
            print(f"{libraries_name} 库安装失败")


def update_flora_api():  # 更新API内容函数
    # noinspection PyTypeChecker
    flora_api.update({"PluginsDict": plugins_dict.copy(), "PluginsInfoDict": plugins_info_dict.copy()})
    for plugin in plugins_dict.values():
        try:
            plugin.flora_api.update(flora_api.copy())
        except AttributeError:
            pass
    for plugin in plugins_dict.values():  # 遍历开线程调用所有的API更新事件函数
        try:
            threading.Thread(target=plugin.api_update_event).start()
        except AttributeError:
            pass


flora_api = {"FloraPath": os.path.dirname(os.path.abspath(__file__)), "FloraHost": flora_host, "FloraPort": flora_port,
             "FrameworkAddress": framework_address, "BotQQ": bot_qq, "Administrator": administrator,
             "FloraVersion": flora_version, "FloraServer": flora_server, "UpdateFloraApi": update_flora_api,
             "SendMsg": send_msg}


@flora_server.post("/")
def process():  # 消息处理函数,不要主动调用这个函数
    data = request.get_json()  # 获取提交数据
    uid = data.get("user_id")
    if uid in administrator:  # 判断消息是否来自于管理员(主人)
        gid = data.get("group_id")
        mid = data.get("message_id")
        msg = data.get("raw_message")
        if msg is not None:
            msg = msg.replace("&#91;", "[").replace("&#93;", "]").replace("&amp;", "&").replace("&#44;",
                                                                                                ",")  # 消息需要将URL编码替换到正确内容
            if msg == "start":
                send_msg("OK", uid, gid, mid)
                command_start()
            if msg == "运行状态":
                send_msg("GJBot v0.2.0 服务已停止", uid, gid, mid)
    else:
        gid = data.get("group_id")
        mid = data.get("message_id")
        msg = data.get("raw_message")
        if msg == "运行状态":
            send_msg("GJBot v0.2.0 服务已停止", uid, gid, mid)

    for plugin in plugins_dict.values():  # 遍历开线程调用所有的插件事件函数
        try:
            threading.Thread(target=plugin.event, args=(data,)).start()
        except AttributeError:
            pass
    return "OK"


def command_start():
    print("正在启动 FloraBot , 请稍后...")
    print("FloraBot 已启动")
    os.kill(os.getpid(), signal.SIGTERM)  # 关闭进程


def check_privileges():
    system = platform.system()
    print(f"当前系统为 {system}")
    if system == "Windows":
        try:
            is_admin = ctypes.windll.shell32.IsUserAnAdmin()
        except:
            is_admin = False
        if is_admin:
            print("\033[91m警告: 当前用户具有管理员权限, 若是添加了恶意插件, 后果不堪设想!!!\033[0m")
    elif system in ["Linux", "Darwin"]:
        if os.geteuid() == 0:
            print("\033[91m警告: 当前用户具有 root 权限, 若是添加了恶意插件, 后果不堪设想!!!\033[0m")


if __name__ == "__main__":
    print(flora_logo)
    check_privileges()
    print("正在初始化 FloraBot , 请稍后...")
    if not os.path.isdir("./FloraBot"):
        os.makedirs("./FloraBot")
    if not os.path.isdir("./FloraBot/Plugins"):
        os.makedirs("./FloraBot/Plugins")
    load_config()
    print(f"欢迎使用 FloraBot {flora_version}")
    print(
        "\033[93m声明: 插件为第三方内容, 请您自行分辨是否为恶意插件, 若被恶意插件入侵/破坏了您的设备或恶意盗取了您的信息, 造成的损失请自负, FloraBot 作者概不负责也无义务负责!!!\033[0m")
    flora_server.run(host=flora_host, port=flora_port)
