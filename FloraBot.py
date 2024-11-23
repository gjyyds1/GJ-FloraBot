# coding: utf-8

import ctypes
import importlib.util
import json
import os
import platform
import re
import signal
import threading

import requests
from flask import Flask, request
from mcrcon import MCRcon

flora_logo = "GJ-FloraBot"
flora_server = Flask("FloraBot", template_folder="FloraBot", static_folder="FloraBot")
flora_host = "127.0.0.1"
flora_port = 3003
gj_bot_ver = "GJBot v0.4.0"
framework_address = "127.0.0.1:3000"
bot_qq = 0
administrator = []
auto_install = False
onebot_api_url = "http://127.0.0.1:3000"

flora_version = "v1.01-GJ修改版"
plugins_dict = {}  # 插件对象字典
plugins_info_dict = {}  # 插件信息字典


def extract_mentioned_qq_id(message):
    # 使用正则表达式找到消息中被@的用户ID
    match = re.search(r'\[CQ:at,qq=(\d+),name=.*?\]', message)
    if match:
        return int(match.group(1))
    return None


def kick_user(group_id, user_id, onebot_api_url):
    url = f"{onebot_api_url}/set_group_kick"
    payload = {
        "group_id": group_id,
        "user_id": user_id,
        "reject_add_request": False  # 是否拒绝该用户的加群请求
    }

    response = requests.post(url, json=payload)

    if response.status_code == 200:
        print("踢出成功")
    else:
        print("踢出失败，错误信息:", response.text)


def load_config():  # 加载FloraBot配置文件函数
    global auto_install, connection_type, flora_host, flora_port, framework_address, bot_id, administrator
    if not os.path.isdir("./FloraBot"):
        os.makedirs("./FloraBot")
    if not os.path.isdir("./FloraBot/Plugins"):
        os.makedirs("./FloraBot/Plugins")
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
        bot_id = flora_config.get("BotID")
        flora_api.update({"BotID": bot_id})
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


def get_group_list():
    url = f"http://{framework_address}/get_group_list"
    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()  # 检查请求是否成功
        data = response.json()
        if data.get("status") == "ok":
            return [group["group_id"] for group in data.get("data", [])]
        else:
            return []
    except requests.exceptions.RequestException:
        return []


def send_msg_to_all_groups(msg: str):
    group_ids = get_group_list()
    url = f"http://{framework_address}"
    data = {}
    for gid in group_ids:
        url += f"/send_group_msg"
        data.update({"group_id": gid, "message": msg})
        requests.post(url, json=data, timeout=5)  # 提交发送消息


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


def ban_user(group_id, user_id, duration, onebot_api_url):
    url = f"{onebot_api_url}/set_group_ban"
    payload = {
        "group_id": group_id,
        "user_id": user_id,
        "duration": duration
    }

    response = requests.post(url, json=payload)

    if response.status_code == 200:
        print("禁言成功")
    else:
        print("禁言失败，错误信息:", response.text)


def load_plugins():  # 加载插件函数
    print("正在加载插件, 请稍后...")
    plugins_info_dict.clear()
    plugins_dict.clear()
    for plugin in os.listdir("./FloraBot/Plugins"):  # 遍历所有插件
        plugin_path = f"FloraBot/Plugins/{plugin}"
        if os.path.isfile(f"./{plugin_path}/Plugin.json"):
            with open(f"./{plugin_path}/Plugin.json", "r", encoding="UTF-8") as read_plugin_config:
                plugin_config = json.loads(read_plugin_config.read())
            if os.path.isfile(f"./{plugin_path}/{plugin_config.get('MainPyName')}.py") and plugin_config.get(
                    "EnablePlugin"):  # 如果配置正确则导入插件
                plugin_config = plugin_config.copy()
                print(f"正在加载插件 {plugin_config.get('PluginName')} ...")
                plugin_config.update({"ThePluginPath": plugin_path})
                plugins_info_dict.update({plugin_config.get("PluginName"): plugin_config})  # 添加插件信息
                spec = importlib.util.spec_from_file_location(plugin_config.get("MainPyName"),
                                                              f"./{plugin_path}/{plugin_config.get('MainPyName')}.py")
                module = importlib.util.module_from_spec(spec)
                try:
                    spec.loader.exec_module(module)
                except ModuleNotFoundError as error_info:
                    print(f"插件 {plugin_config.get('PluginName')} 导入失败, 错误信息: {error_info}")
                    exit(2)
                try:
                    module.flora_api = flora_api.copy()  # 传入API参数
                except AttributeError:
                    pass
                module.flora_api.update({"ThePluginPath": plugin_path})
                try:
                    module.flora_api = flora_api.copy()  # 传入API参数
                except AttributeError:
                    pass
                module.flora_api.update({"ThePluginPath": plugin_path})
                try:
                    threading.Thread(target=module.init).start()  # 开线程初始化插件
                except AttributeError:
                    pass
                plugins_dict.update({plugin_config.get("PluginName"): module})  # 添加插件对象
    update_flora_api()


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
             "LoadPlugins": load_plugins, "SendMsg": send_msg}


def sm(msg: str):
    data = request.get_json()  # 获取提交数据
    uid = data.get("user_id")
    gid = data.get("group_id")
    mid = data.get("message_id")
    send_msg(msg, uid, gid, mid)


@flora_server.post("/")
def process():  # 消息处理函数,不要主动调用这个函数
    data = request.get_json()  # 获取提交数据
    uid = data.get("user_id")
    if uid in administrator:  # 判断消息是否来自管理员(主人)
        gid = data.get("group_id")
        mid = data.get("message_id")
        msg = data.get("raw_message")
        if msg is not None:
            msg = msg.replace("&#91;", "[").replace("&#93;", "]").replace("&amp;", "&").replace("&#44;",
                                                                                                ",")  # 消息需要将URL编码替换到正确内容
            if msg == "reload":
                send_msg("正在重载插件, 请稍后...", uid, gid, mid)
                load_plugins()
                send_msg(
                    f"{gj_bot_ver}\n\n插件重载完成, 共有 {len(plugins_info_dict)} 个插件, 已启用 {len(plugins_dict)} 个插件",
                    uid, gid, mid)
            elif msg == "list":
                plugins = f"{gj_bot_ver}\n\n插件列表:\n"
                for plugin_info in plugins_info_dict.values():
                    plugin_status = "启用"
                    if not plugin_info.get("EnablePlugin"):
                        plugin_status = "禁用"
                    plugins += f"•{plugin_info.get('PluginName')}  [状态: {plugin_status}]\n"
                plugins += f"\n共有 {len(plugins_info_dict)} 个插件, 已启用 {len(plugins_dict)} 个插件\n可使用 \"load/disable + [插件名]\" 来启用或者禁用插件\n若未找到插件, 但插件文件已添加, 请试试使用 \"reload\""
                send_msg(plugins, uid, gid, mid)
            elif msg == "exit":
                send_msg(f"已关闭{gj_bot_ver}", uid, gid, mid)
                command_exit()
            elif msg.startswith("load "):
                msg = msg.replace("load ", "", 1)
                if plugins_info_dict.get(msg) is not None and not plugins_info_dict.get(msg).get("EnablePlugin"):
                    plugin_info = plugins_info_dict.get(msg)
                    plugin_info.update({"EnablePlugin": True})
                    plugins_info_dict.update({msg: plugin_info})
                    spec = importlib.util.spec_from_file_location(plugin_info.get("MainPyName"),
                                                                  f"./{plugin_info.get('ThePluginPath')}/{plugin_info.get('MainPyName')}.py")
                    module = importlib.util.module_from_spec(spec)
                    try:
                        spec.loader.exec_module(module)
                    except ModuleNotFoundError as error_info:
                        print(f"插件 {plugin_info.get('PluginName')} 导入失败, 错误信息: {error_info}")
                        exit(2)
                    try:
                        module.flora_api = flora_api.copy()
                    except AttributeError:
                        pass
                    module.flora_api.update({"ThePluginPath": plugin_info.get("ThePluginPath")})
                    try:
                        threading.Thread(target=module.init).start()
                    except AttributeError:
                        pass
                    plugins_dict.update({plugin_info.get("PluginName"): module})
                    update_flora_api()
                    with open(f"./{plugin_info.get('ThePluginPath')}/Plugin.json", "w",
                              encoding="UTF-8") as write_plugin_config:
                        plugin_info_copy = plugin_info.copy()
                        plugin_info_copy.pop("ThePluginPath")
                        write_plugin_config.write(json.dumps(plugin_info_copy, ensure_ascii=False, indent=4))
                    send_msg(
                        f"{gj_bot_ver}\n\n插件 {msg} 已启用, 共有 {len(plugins_info_dict)} 个插件, 已启用 {len(plugins_dict)} 个插件",
                        uid, gid, mid)
                else:
                    send_msg(
                        f"{gj_bot_ver}\n\n未找到或已启用插件 {msg} , 若未找到插件, 但插件文件已添加, 请试试使用 \"reload\"",
                        uid, gid, mid)
            elif msg.startswith("disable "):
                msg = msg.replace("disable ", "", 1)
                if plugins_info_dict.get(msg) is not None and plugins_info_dict.get(msg).get("EnablePlugin"):
                    plugin_info = plugins_info_dict.get(msg)
                    plugin_info.update({"EnablePlugin": False})
                    plugins_info_dict.update({msg: plugin_info})
                    if plugins_dict.get(msg) is not None:
                        plugins_dict.pop(msg)
                    update_flora_api()
                    with open(f"./{plugin_info.get('ThePluginPath')}/Plugin.json", "w",
                              encoding="UTF-8") as write_plugin_config:
                        plugin_info_copy = plugin_info.copy()
                        plugin_info_copy.pop("ThePluginPath")
                        write_plugin_config.write(json.dumps(plugin_info_copy, ensure_ascii=False, indent=4))
                    send_msg(
                        f"{gj_bot_ver}\n\n插件 {msg} 已禁用, 共有 {len(plugins_info_dict)} 个插件, 已启用 {len(plugins_dict)} 个插件",
                        uid, gid, mid)
                else:
                    send_msg(
                        f"{gj_bot_ver}\n\n未找到或已禁用插件 {msg} , 若未找到插件, 但插件文件已添加, 请试试使用 \"reload\"",
                        uid, gid, mid)
            elif msg.startswith("echo "):
                send_msg(msg.replace("echo ", "", 1), uid, gid, mid)
            elif msg.startswith("echo1 "):
                send_msg(msg.replace("echo1 ", "", 1), uid, gid)
            elif msg == "admin_help":
                send_msg(f"admin菜单"
                         f"\n"
                         f"\nreload - 重载插件"
                         f"\nlist - 查看插件列表"
                         f"\ndel [插件名] - 删除插件文件"
                         f"\nexit - 关闭GJBot"
                         f"\nload [插件名] - 加载插件"
                         f"\ndisable [插件名] - 禁用插件"
                         f"\necho [消息] - 发送消息（回复形式）"
                         f"\necho1 [消息] - 发送消息（不回复形式）"
                         f"\nban [@用户] [禁言时长] - 禁言用户"
                         f"\nunban [@用户] - 解除禁言"
                         f"\nkick [@用户] - 踢出用户", uid, gid, mid)
            if msg.startswith("rcon "):
                rcon_command = msg.replace("rcon ", "", 1)
                print(rcon_command)
                mcr = MCRcon("127.0.0.1", "Abc12345", 10701)
                mcr.connect()
                response_rcon = mcr.command(f"{rcon_command}")
                send_msg(f"[CQ:at,qq={uid}]\n\nRCON命令执行结果：\n{response_rcon}", uid, gid, mid)
                mcr.disconnect()
            if msg.startswith("cmd "):
                msg_command = msg.replace("cmd ", "", 1)
                os.system(msg_command)
                send_msg("OK", uid, gid, mid)
            if msg.startswith("ban "):
                qqid = extract_mentioned_qq_id(msg)
                try:
                    # 分割消息以提取用户ID和禁言时间
                    parts = msg.split()
                    ban_time = int(parts[-1])  # 提取禁言时间
                    # 调用ban_user函数禁言用户
                    ban_user(gid, qqid, ban_time, onebot_api_url)
                    send_msg(f"已禁言{qqid} {ban_time}秒", uid, gid, mid)
                except:
                    send_msg("格式错误，请按照格式ban <QQ号> <禁言时长>", uid, gid, mid)
            if msg.startswith("unban "):
                unban_qqid = extract_mentioned_qq_id(msg)
                # 调用ban_user函数解除禁言
                ban_user(gid, unban_qqid, 0, onebot_api_url)
                send_msg(f"已解除{unban_qqid}的禁言", uid, gid, mid)
            if msg.startswith("kick "):
                qqid = extract_mentioned_qq_id(msg)
                # 调用群组踢人函数踢人
                kick_user(gid, qqid, onebot_api_url)
                send_msg(f"已从{gid}踢出{qqid}", uid, gid, mid)
            elif msg.startswith("公告 "):
                guard_msg = msg.replace("公告 ", "", 1)
                send_msg_to_all_groups(guard_msg)
                send_msg("OK", uid, gid, mid)
            elif msg.startswith("del "):
                command = f"rmdir /S /Q .\\FloraBot\\FloraBot-main\\FloraBot\\Plugins\\{msg.replace('del ', '', 1)}"
                exit_code = os.system(command)
                if exit_code == 0:
                    send_msg("OK", uid, gid, mid)
                else:
                    send_msg("Error", uid, gid, mid)
            elif msg == "运行状态":
                send_msg(f"{gj_bot_ver} 正在运行", uid, gid, mid)
    else:
        gid = data.get("group_id")
        mid = data.get("message_id")
        msg = data.get("raw_message")
        if msg is not None:
            if msg == "运行状态":
                send_msg(f"{gj_bot_ver} 正在运行", uid, gid, mid)

    for plugin in plugins_dict.values():  # 遍历开线程调用所有的插件事件函数
        try:
            threading.Thread(target=plugin.event, args=(data,)).start()
        except AttributeError:
            pass
    return "OK"


def command_exit():
    print("已关闭GJBot")
    print("管理员已执行exit")
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
    load_plugins()
    flora_server.run(host=flora_host, port=flora_port)
