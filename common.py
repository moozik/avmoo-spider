import logging
import time
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
from urllib import parse

CONFIG_FILE = "config.ini"
CONFIG_FILE_DEFAULT = "config.ini.default"
CONFIG = configparser.ConfigParser()

DB: Connection = None

# 存储 av_genre,av_extend, rename数据，用于快速查找
DATA_STORAGE = {}

# 缓存
SQL_CACHE = {}

# 任务队列
QUEUE = Queue(maxsize=0)

LOG_FORMAT = "%(asctime)s [%(filename)s:%(lineno)d] %(levelname)s: %(message)s"
LOGGER = logging.getLogger(APP_NAME)


def init(argv=None):
    global CONFIG_FILE
    LOGGER.info("common.init")
    if argv is not None and len(argv) > 1:
        # 命令行指定配置文件
        CONFIG_FILE = argv[1]
    # 初始化配置
    config_check()
    config_init()
    db_init()


def make_dicts(cursor, row):
    return dict((cursor.description[idx][0], value)
                for idx, value in enumerate(row))


def db_init():
    LOGGER.info("common.init.db")
    # 初始化db
    global DB
    db_file = CONFIG.get("base", "db_file")
    if os.path.exists(db_file):
        DB = sqlite3.connect(db_file, check_same_thread=False)
        DB.row_factory = make_dicts


def storage_init(table: str) -> None:
    if table in DATA_STORAGE and non_empty(DATA_STORAGE[table]):
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
        for cond_key, cond_val in conditions.items():
            if not cond_val:
                continue
            if isinstance(cond_val, str):
                if cond_val != row[cond_key]:
                    hit = False
                    break
            elif isinstance(cond_val, list):
                if row[cond_key] not in cond_val:
                    hit = False
                    break
            else:
                LOGGER.fatal("wrong type")
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
    LOGGER.info('CONFIG FILE:%r', config_path())
    CONFIG.read(config_path())


# 配置文件
def config_check():
    if not os.path.exists(CONFIG_FILE):
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


# 创建日志记录器
def create_logger(app_name: str):
    logger = logging.getLogger(app_name)
    logger.setLevel(logging.INFO)  # Log等级总开关
    # 第二步，创建一个handler，用于写入日志文件
    if not os.path.exists('logs'):
        os.mkdir('logs')
    log_path = os.getcwd() + '/logs/'
    logfile = log_path + app_name + '.' + time.strftime('%Y%m%d%H', time.localtime(time.time())) + '.log'

    fh = logging.FileHandler(logfile, mode='a', encoding='utf-8')
    fh.setLevel(logging.DEBUG)  # 输出到file的log等级的开关
    # 第三步，定义handler的输出格式
    fh.setFormatter(logging.Formatter(LOG_FORMAT))
    # 第四步，将logger添加到handler里面
    logger.addHandler(fh)

    fh = logging.StreamHandler()
    fh.setLevel(logging.DEBUG)  # 输出到file的log等级的开关
    # 第三步，定义handler的输出格式
    fh.setFormatter(logging.Formatter(LOG_FORMAT))
    # 第四步，将logger添加到handler里面
    logger.addHandler(fh)


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
    if len(sql) < 150:
        LOGGER.info(color(36, sql))
    else:
        LOGGER.info(color(36, "INSERT,table:{},count:{}".format(table, len(data))))
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
    LOGGER.info(color(35, sql))
    DB.cursor().execute(sql)
    DB.commit()


# 查询sql 没缓存
def fetchall(sql) -> list:
    if DB is None:
        # 触发安装程序
        raise IOError('db')

    cur = DB.cursor()
    LOGGER.info(color(36, sql))
    cur.execute(sql)
    return cur.fetchall()


# 查询sql 带缓存
def query_sql(sql) -> list:
    cache_key = gen_cache_key(sql)
    # 是否使用缓存
    if CONFIG.getboolean("website", "use_cache"):
        LOGGER.info('CACHE[%s]', cache_key)
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
           "av_list.genre LIKE '%{0}%' OR ".format(key_item) + \
           "av_list.stars LIKE '%{0}%')".format(key_item)


def open_browser_tab(url):
    if not url:
        return
    LOGGER.info("open_browser_tab:%s", url)

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

    LOGGER.fatal("wrong url:{}".format(url))
    return '', '', -1


# 获取sql中的表名
def get_table_name(sql):
    return list(set(re.findall("(av_[a-z]+)", sql)))


# 获取缓存key
def gen_cache_key(sql):
    return '|'.join(get_table_name(sql)) + ':' + str(binascii.crc32(sql.encode()) & 0xffffffff)


def empty(i: any) -> bool:
    if i is None:
        return True
    if isinstance(i, str):
        return i == ''
    if isinstance(i, list) or isinstance(i, tuple):
        return len(i) == 0
    if isinstance(i, dict):
        return i == {}
    if isinstance(i, int) or isinstance(i, float):
        return i == 0
    return False


def non_empty(i: any) -> bool:
    return not empty(i)


# 命令行颜色
def color(c, s):
    if not CONFIG.getboolean('log', 'ansi_color'):
        return s
    """
    \033[30m黑\033[0m
    \033[31m酱红\033[0m
    \033[32m浅绿\033[0m
    \033[33m黄褐\033[0m
    \033[34m浅蓝\033[0m
    \033[35m紫\033[0m
    \033[36m天蓝\033[0m
    \033[37m灰白\033[0m
    """
    return "\033[{}m{}\033[0m".format(c, s)


def upper_path(path: str) -> str:
    # 如果为windows环境路径，则路径首字母大写
    if re.match("^[a-z]:\\\\", path):
        return path[0].upper() + path[1:]
    else:
        return path


def a_tag_build(link):
    return '<a href="{}">{}</a>'.format(link, link)


# 识别linkid
def is_linkid(linkid: str = '') -> bool:
    if empty(linkid):
        return False
    return re.match('^[a-z0-9]{16}$', linkid) is not None


# 替换链接中命中rename的{rename}
def url_rename(s: str) -> str:
    res = re.findall("{(.+)}", s)
    if res:
        return s.replace('{'+res[0]+'}', rename(res[0]))
    return s


# 重命名
def rename(name):
    # 渲染前准备rename数据
    storage_init(AV_EXTEND)
    if 'rename' not in DATA_STORAGE:
        DATA_STORAGE['rename'] = {}
        for row in DATA_STORAGE[AV_EXTEND]:
            if row['extend_name'] == 'rename':
                DATA_STORAGE['rename'][row['key']] = row['val']
    if name in DATA_STORAGE['rename']:
        return DATA_STORAGE['rename'][name]
    return name


# 列表小头图
def small_img(s):
    return CONFIG.get('website', 'cdn') + '/digital/video' + s[:-6] + 'ps' + s[-4:]


# 获取大头图
def big_img(s):
    return CONFIG.get('website', 'cdn') + '/digital/video' + s


# 是否为可播放的链接
def can_play_url(s):
    p = parse.urlparse(s)
    if p.scheme not in ['http', 'https']:
        return False
    return list_in_str(('.m3u8', '.mp4', '.flv'), p.path)


if __name__ == "__main__":
    pass
