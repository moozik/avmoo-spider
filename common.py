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

# 初始化
def init():
    global CONFIG, DB
    # 初始化配置
    if CONFIG != None:
        return
    config_file = CONFIG_FILE_DEFAULT
    if os.path.exists(CONFIG_FILE):
        config_file = CONFIG_FILE
    cf = configparser.ConfigParser()
    cf.read(config_file)
    CONFIG = cf

    # 检查配置的地址是否可访问
    avmoo_site = CONFIG["base"]["avmoo_site"]
    try:
        res = requests.get(avmoo_site, timeout=5)
        if res == None or res.status_code != 200:
            avmoo_site = ""
    except Exception as e:
        print("Exception:{}".format(e))
        avmoo_site = ""
    
    if avmoo_site == "":
        avmoo_site = get_new_avmoo_site()
        CONFIG["base"]["avmoo_site"] = avmoo_site
        with open(CONFIG_FILE, "w") as fp:
            CONFIG.write(fp)

    # 初始化db
    DB['CONN'] = sqlite3.connect(CONFIG.get("base","db_file"), check_same_thread=False)
    DB['CUR'] = DB['CONN'].cursor()
    # 如果不存在则新建表
    buildSqliteDb(DB['CONN'], DB['CUR'])

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

# 获取最新地址
def get_new_avmoo_site():
    res = requests.get('https://tellme.pw/avmoo')
    html = etree.HTML(res.text)
    avmoo_site = html.xpath('/html/body/div[1]/div[2]/div/div[2]/h4[1]/strong/a/@href')[0]
    print("newUrl:{}".format(avmoo_site))
    return avmoo_site
