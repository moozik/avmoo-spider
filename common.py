from sqlite3 import Connection

import requests
import configparser
import os
import re
import sqlite3
from lxml import etree
import webbrowser
import threading
import binascii
from urllib.parse import quote
from queue import Queue
from define import *

CONFIG_FILE = "config.ini"
CONFIG_FILE_DEFAULT = "config.ini.default"
CONFIG = configparser.ConfigParser()

DB: Connection = None

# 存储 av_genre,av_extend数据，用户快速查找
DATA_STORAGE = {}

# 缓存
SQL_CACHE = {}

# 任务队列
QUEUE = Queue(maxsize=0)


def init(argv):
    global CONFIG_FILE
    print("common.init")
    if len(argv) > 1:
        # 命令行指定配置文件
        CONFIG_FILE = argv[1]
    # 初始化配置
    config_check()
    config_init()
    db_init()


def db_init():
    print("common.init.db")
    # 初始化db
    global DB
    db_file = CONFIG.get("base", "db_file")
    if os.path.exists(db_file):
        DB = sqlite3.connect(db_file, check_same_thread=False)


def storage_init(table: str) -> None:
    if table in DATA_STORAGE and DATA_STORAGE[table]:
        return
    DATA_STORAGE[table] = fetchall("SELECT * FROM " + table)


# 仅av_genre和av_extend使用
def storage(table: str, conditions: dict = None, col: str = None) -> list:
    storage_init(table)
    ret = []
    if not conditions:
        return DATA_STORAGE[table]
    # 每条记录
    for row in DATA_STORAGE[table]:
        hit = True
        # 每个条件
        for col_item, val in conditions.items():
            if isinstance(val, str):
                if val != row[col_item]:
                    hit = False
                    break
            elif isinstance(val, list):
                if row[col_item] not in val:
                    hit = False
                    break
            else:
                print("wrong type")
        if not hit:
            continue
        if col:
            ret.append(row[col])
        else:
            ret.append(row)
    return ret


def config_path() -> str:
    if os.path.exists(CONFIG_FILE):
        return CONFIG_FILE
    return CONFIG_FILE_DEFAULT


def config_init() -> None:
    # 初始化配置
    print('CONFIG FILE:', config_path())
    CONFIG.read(config_path())


def config_check():
    if not os.path.exists(CONFIG_FILE):
        print("配置文件缺失")
        return
    config = configparser.ConfigParser()
    config.read(CONFIG_FILE)
    config_default = configparser.ConfigParser()
    config_default.read(CONFIG_FILE_DEFAULT)
    for (section, option) in [x.split('.') for x in CONFIG_NAME_LIST]:
        if not config.has_section(section):
            config.add_section(section)
        if not config.has_option(section, option):
            config.set(section, option, config_default.get(section, option))
    config_save(config)


def config_save(config):
    with open(CONFIG_FILE, "w") as fp:
        config.write(fp)


def replace_sql_build(table: str, data: dict) -> str:
    sql = "REPLACE INTO {} ({}) VALUES ({})".format(
        table, ','.join(list(data)), ("?," * len(data))[:-1]
    )
    return sql


# sql插入操作
# av_genre av_extend
def insert(table: str, data: list):
    if CONFIG.getboolean("base", "readonly"):
        return
    if not data:
        return
    sql = replace_sql_build(table, data[0])
    print("INSERT,table:{},count:{}".format(table, len(data)))
    DB.cursor().executemany(sql, [tuple(x.values()) for x in data])
    DB.commit()
    if table in DATA_STORAGE:
        DATA_STORAGE[table].clear()


# sql删除操作
def delete(table: str, data: dict):
    if CONFIG.getboolean("base", "readonly"):
        return
    if not data:
        return
    sql = "DELETE FROM {} WHERE {}".format(
        table, " AND ".join(["{}='{}'".format(field, value) for field, value in data.items()]))
    execute(sql)
    if table in DATA_STORAGE:
        DATA_STORAGE[table].clear()


# 执行sql
def execute(sql):
    if CONFIG.getboolean("base", "readonly"):
        return
    print("SQL EXECUTE:{}".format(sql))
    DB.cursor().execute(sql)
    DB.commit()


# 查询sql 没缓存
def fetchall(sql) -> list:
    if DB is None:
        raise IOError('db')

    cur = DB.cursor()
    print('SQL FETCH:{}'.format(sql))
    cur.execute(sql)
    rows = cur.fetchall()
    if not rows:
        return []

    result = []
    for row in rows:
        row_dict = {}
        for i in range(len(cur.description)):
            row_dict[cur.description[i][0]] = row[i]
        result.append(row_dict)
    return result


# 查询sql 带缓存
def query_sql(sql) -> list:
    cache_key = gen_cache_key(sql)
    # 是否使用缓存
    if CONFIG.getboolean("website", "use_cache"):
        print('CACHE[{}]'.format(cache_key))
        # 是否有缓存
        if cache_key in SQL_CACHE.keys():
            return SQL_CACHE[cache_key][:]
        else:
            ret = fetchall(sql)
            if CONFIG.getboolean("website", "use_cache") and ret != []:
                SQL_CACHE[cache_key] = ret
            return ret[:]
    else:
        return fetchall(sql)


def get_new_avmoo_site() -> str:
    res = requests.get('https://tellme.pw/avmoo')
    html = etree.HTML(res.text)
    avmoo_site = html.xpath(
        '/html/body/div[1]/div[2]/div/div[2]/h4[1]/strong/a/@href')[0]
    return avmoo_site


def list_in_str(target_list: tuple, target_string: str) -> bool:
    for item in target_list:
        if item in target_string:
            return True
    return False


def get_url(page_type: str = '', keyword: str = '', page_no: int = 1) -> str:
    ret = '{}/{}'.format(CONFIG.get("base", "avmoo_site"),
                         CONFIG.get("base", "country"), )
    if page_type == "search":
        if keyword != '':
            ret += '/{}/{}'.format(page_type, keyword)
    else:
        if page_type != '':
            ret += '/{}'.format(page_type)
        if keyword != '':
            ret += '/{}'.format(keyword)
    if page_no > 1:
        ret += '/page/{}'.format(page_no)
    return ret


def get_local_url(page_type: str = '', keyword: str = '', page_no: int = 1) -> str:
    ret = 'http://{}:{}'.format(LOCAL_IP, CONFIG.getint("base", "port"))
    if page_type == "popular":
        return ''
    if page_type != '':
        ret += '/{}'.format(page_type)
    if keyword != '':
        ret += '/{}'.format(keyword)
    if page_no > 1:
        ret += '/page/{}'.format(page_no)
    return ret


def search_where(key_item: str) -> str:
    key_item = sql_escape(key_item)
    return "(av_list.title LIKE '%{0}%' OR ".format(key_item) + \
           "av_list.director = '{0}' OR ".format(key_item) + \
           "av_list.studio = '{0}' OR ".format(key_item) + \
           "av_list.label = '{0}' OR ".format(key_item) + \
           "av_list.series LIKE '%{0}%' OR ".format(key_item) + \
           "av_list.genre LIKE '%|{0}|%' OR ".format(key_item) + \
           "av_list.stars LIKE '%{0}%')".format(key_item)


def open_browser_tab(url):
    if not url:
        return
    print("open_browser_tab:", url)

    def _open_tab(url_param):
        webbrowser.open_new_tab(url_param)

    thread = threading.Thread(target=_open_tab, args=(url,))
    thread.daemon = True
    thread.start()


def sql_escape(keyword: str) -> str:
    for item in ESCAPE_LIST:
        keyword = keyword.replace(item[0], item[1])
    return keyword


# 解析源站url, 返回 page_type, keyword, page_start
def parse_url(url: str) -> tuple:
    if url is None or url == '':
        return '', '', -1
    
    pattern_1 = "https?://[^/]+/[^/]+/popular(/page/(\\d+))?"
    pattern_2 = "https?://[^/]+/[^/]+/(movie|star|genre|series|studio|label|director|search)/([^/]+)(/page/(\\d+))?"

    if re.match(pattern_1, url):
        res = re.findall(pattern_1, url)
        page_start = int(res[0][1]) if res[0][1] else 1
        return "popular", '', page_start
    
    if re.match(pattern_2, url):
        res = re.findall(pattern_2, url)
        page_start = int(res[0][3]) if res[0][3] else 1
        return res[0][0], res[0][1], page_start

    print("wrong url:{}".format(url))
    return '', '', -1


def get_exist_linkid(page_type: str, keyword: str) -> dict:
    sql = ''
    exist_linkid_dict = {}
    # 必须有值
    if not keyword:
        return {}
    # 查询已存在的
    if page_type in ['director', 'studio', 'label', 'series']:
        sql = "SELECT linkid FROM av_list WHERE {}_url='{}'".format(page_type, keyword)
    if page_type == 'genre':
        genre = fetchall("SELECT * FROM av_genre WHERE linkid='{}'".format(keyword))
        if genre:
            sql = "SELECT linkid FROM av_list WHERE genre LIKE '%|{}|%'".format(genre[0]['name'])
    if page_type == 'star':
        sql = "SELECT linkid FROM av_list WHERE stars_url LIKE '%{}%'".format(keyword)
    if page_type == 'group':
        sql = "SELECT linkid FROM av_list WHERE av_id LIKE '{}-%'".format(keyword)
    if page_type == 'search':
        where = []
        for key_item in keyword.split(' '):
            where.append(search_where(key_item))
        sql = "SELECT linkid FROM av_list WHERE " + " AND ".join(where)
    if sql != '':
        ret = fetchall(sql)
        exist_linkid_dict = {x["linkid"]: True for x in ret}
    return exist_linkid_dict


# 获取sql中的表名
def get_table_name(sql):
    return list(set(re.findall("(av_[a-z]+)", sql)))


# 获取缓存key
def gen_cache_key(sql):
    return '|'.join(get_table_name(sql)) + ':' + str(binascii.crc32(sql.encode()) & 0xffffffff)


if __name__ == "__main__":
    pass
