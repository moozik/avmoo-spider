import requests
import configparser
import os
import sqlite3
from install import buildSqliteDb
from lxml import etree

CONFIG_FILE = "config.ini"
CONFIG_FILE_DEFAULT = "config.ini.default"
CONFIG = None
DB = {}
NETWORK_CONNECT = False

STATIC_FILE = []

COUNTRY_MAP = {
    'en' : 'English',
    'ja' : '日本语',
    'tw' : '正體中文',
    'cn' : '简体中文',
}

def init():
    print("common.init")
    global CONFIG, DB, NETWORK_CONNECT, STATIC_FILE
    # 初始化配置
    config_init()
    
    # 初始化db
    DB['CONN'] = sqlite3.connect(CONFIG.get(
        "base", "db_file"), check_same_thread=False)
    DB['CUR'] = DB['CONN'].cursor()
    # 如果不存在则新建表
    buildSqliteDb(DB['CONN'], DB['CUR'])
    print("common.init.db")

    # 检查是否联网
    NETWORK_CONNECT = check_network_connect()
    if not NETWORK_CONNECT:
        print("no network")
        return

    # 检查配置的地址是否可访问
    avmoo_site = CONFIG["base"]["avmoo_site"]
    try:
        res = requests.get(avmoo_site, timeout=5)
        if res == None or res.status_code != 200:
            avmoo_site = ""
    except Exception as e:
        print("Exception:{}".format(e))
        avmoo_site = ""

    # 更新最新地址
    if avmoo_site == "":
        avmoo_site = get_new_avmoo_site()
        print("common.check.avmoo_site,newSite:{}".format(avmoo_site))
        CONFIG["base"]["avmoo_site"] = avmoo_site
        config_save()

    # 下载静态资源
    for item in STATIC_FILE:
        if os.path.exists(item[0]):
            continue
        with open(item[0], "wb") as f:
            link = item[1]
            if link[:4] != 'http':
                link = avmoo_site + link
            resp = requests.get(link)
            f.write(resp.content)
            print("fetch:" + link)

def config_path() -> str:
    global CONFIG_FILE, CONFIG_FILE_DEFAULT
    if os.path.exists(CONFIG_FILE):
        return CONFIG_FILE
    return CONFIG_FILE_DEFAULT

def config_init() -> None:
    global CONFIG, COUNTRY_MAP
    # 初始化配置
    cf = configparser.ConfigParser()
    cf.read(config_path())
    CONFIG = cf
    CONFIG.set("base", "country_name", COUNTRY_MAP[CONFIG.get("base", "country")])

def config_save() -> None:
    global CONFIG_FILE
    CONFIG.remove_option("base", "country_name")
    with open(CONFIG_FILE, "w") as fp:
        CONFIG.write(fp)

def check_network_connect() -> bool:
    global CONFIG, NETWORK_CONNECT
    try:
        resp = requests.get(CONFIG["base"]["network_test"], timeout=2)
    except Exception as e:
        NETWORK_CONNECT = False
        return False
    NETWORK_CONNECT = resp.status_code == 200
    return NETWORK_CONNECT


def show_column_name(data, description) -> list:
    result = []
    for row in data:
        row_dict = {}
        for i in range(len(description)):
            row_dict[description[i][0]] = row[i]
        result.append(row_dict)
    return result


def fetchall(cur, sql) -> list:
    cur.execute(sql)
    ret = cur.fetchall()
    return show_column_name(ret, cur.description)


def get_new_avmoo_site() -> str:
    res = requests.get('https://tellme.pw/avmoo')
    html = etree.HTML(res.text)
    avmoo_site = html.xpath(
        '/html/body/div[1]/div[2]/div/div[2]/h4[1]/strong/a/@href')[0]
    return avmoo_site
