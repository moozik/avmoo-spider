from ast import Constant
from asyncio import constants
import time
import sys
from requests import Timeout
import json

from typing import Iterator
from common import *

'''
抓取aqdav.net的影片添加到扩展信息
1. av_extend 中必须有{aqd}配置,(rename,aqd,https://vip.aqdtv540.com),用来记录最新的地址
'''
class Aqd:
    instance = None
    requests_ins = None
    db_ins = None
    log = logging.getLogger('aqd')
    save_file = 'aqd_result.txt'

    @staticmethod
    def db():
        if Aqd.db_ins is None:
            Aqd.log.info('spider.db.init')
            # 链接数据库
            Aqd.db_ins = sqlite3.connect(CONFIG.get("base", "db_file"))
            Aqd.db_ins.row_factory = make_dicts
        return Aqd.db_ins

    @staticmethod
    def requests():
        if Aqd.requests_ins is None:
            Aqd.log.info('spider.requests.init')
            # 创建会话对象
            Aqd.requests_ins = requests.Session()
            Aqd.requests_ins.headers = {
                'User-Agent': CONFIG.get("requests", "user_agent"),
            }
        return Aqd.requests_ins

    @staticmethod
    def fetchall(sql) -> list:
        cur = Aqd.db().cursor()
        cur.execute(sql)
        return cur.fetchall()

    # 自动翻页返回影片url
    @staticmethod
    def url_general() -> Iterator[str]:
        res = fetchall("select * from av_extend where extend_name='rename' and key='aqd'")
        if empty(res):
            print("需要aqd配置")
            return
        site_url = res[0]["val"].strip("/")
        for page_no in range(1, 500):
            time.sleep(1)
            # 有PART关键字的影片都是AV影片
            # url = site_url + '/videos/search?key=PART&page={}'.format(page_no)
            url = site_url + '/videos/category/jp/{}'.format(page_no)
            Aqd.log.info("get:{}".format(url))

            (status_code, html) = Aqd.get_html_by_url(url)
            if status_code in [403, 404, 500] or html is None:
                Aqd.log.fatal("url:{} status_code:{}".format(url, status_code))
                break

            item_a_list = html.xpath('//div[@class="row index-videos-list index-videos-item-list"]/div/div/div/a')
            if not item_a_list:
                Aqd.log.warning("page empty break")
                break
            for item in item_a_list:
                # 判断是否有番号id
                title = item.attrib.get('alt')
                url = item.attrib.get('href')
                # av_id = Aqd.get_av_id(title)
                # if empty(av_id):
                #     continue
                head_img = item.xpath('img')[0].attrib.get('data-original')
                # Aqd.log.info("aqdurl:{},title:{}".format(url, title))
                yield site_url + url, head_img

    @staticmethod
    def movie_save(insert_list: list) -> None:
        if empty(insert_list):
            return
        insert_list_str = "\n".join([json.dumps(x, ensure_ascii = False) for x in insert_list])
        with open(Aqd.save_file, "a", encoding='utf-8') as f:
            f.write(insert_list_str + "\n")

    # 解析html数据
    @staticmethod
    def movie_page_data(html) -> dict:
        title = html.xpath("/html/body/section/div[2]/div[2]/div[3]/div/div[1]/h3/text()")[0]
        video = ""
        res = re.findall(r"(http.+\.m3u8)", html.xpath("//script")[-5].text)
        if non_empty(res):
            video = res[0]
        url = html.xpath('/html/head/meta[15]')[0].attrib.get('content')
        data = {
            'id': int(re.findall("\d+$", url)[0]),
            'title': title,
            'av_id': Aqd.get_av_id(title),
            'video': video,
            'img': '',
            # 发行时间
            'date': html.xpath('/html/body/section/div[2]/div[2]/div[3]/div/div[3]/span/text()')[0].strip()[-19:]
        }
        return data

    @staticmethod
    def get_html_by_url(url: str) -> tuple:
        retry_limit = 100
        for i in range(retry_limit):
            try:
                res = Aqd.requests().get(url, timeout=CONFIG.getint("requests", "timeout"))
                if res.status_code != 200:
                    Aqd.log.error("status_code = {},url:{}".format(res.status_code, url))
                    return res.status_code, None

                return 200, etree.HTML(res.text)
            except Timeout as e:
                Aqd.log.warning("requests Timeout,error:{}\nretry url:{}".format(
                    e, url
                ))
                # 休眠
                time.sleep(10)
                # 超时重试
                continue

            except ConnectionError as e:
                Aqd.log.warning("requests ConnectionError,error:{}\nretry url:{}".format(
                    e, url
                ))
                # 休眠
                time.sleep(10)
                # 链接异常
                continue

            except Exception as e:
                Aqd.log.warning("requests Exception:{}\nurl:{}".format(e, url))
                time.sleep(10)
                continue
        # 返回错误
        return 500, None

    @staticmethod
    def get_av_id(title: str) -> str:
        '''
        从title中获取avid,取不到返回空'''
        res = re.findall(r"\[([A-Z]+\-\d+)\]", title)
        if not res:
            return ''
        return res[0]

    @staticmethod
    def get_max_id() -> int:
        max_id = 0
        with open(Aqd.save_file, "r", encoding="utf-8") as f:
            for line in f.readlines():
                row = json.loads(line.strip())
                if row["id"] > max_id:
                    max_id = row["id"]
        return max_id

    @staticmethod
    def fetch_data():
        max_id = aqd.get_max_id()
        for url, img in aqd.url_general():
            id = re.findall("\d+$", url)[0]
            if int(id) <= max_id:
                break
            status_code,html = Aqd.get_html_by_url(url)
            if status_code != 200:
                continue
            
            Aqd.log.info('fetch:{}'.format(url))
            data = Aqd.movie_page_data(html)
            data['img'] = img
            Aqd.movie_save([data])
    
    @staticmethod
    def insert_data():
        with open(Aqd.save_file, "r", encoding="utf-8") as f:
            for line in f.readlines():
                row = json.loads(line.strip())
                if empty(row['av_id']):
                    continue
                # 查询库里有没有当前id
                res = fetchall("select * from av_list where av_id ='{}'".format(row['av_id']))
                if empty(res):
                    print("av_id:{},none".format(row["av_id"]))
                m3u8_url = "{}#{}".format(row["video"], row["id"])
                # 查询数据是不是已存在
                res = fetchall("select * from av_extend where extend_name='movie_res' and key='{}' and val='{}'".format(row['av_id'], m3u8_url))
                if non_empty(res):
                    continue
                insert("av_extend", [{
                    "extend_name": "movie_res",
                    "key": row['av_id'],
                    "val": m3u8_url
                }])
if __name__ == '__main__':
    init(sys.argv[1])
    create_logger('aqd')
    aqd = Aqd()
    if len(sys.argv) < 2 or sys.argv[2] == 'fetch':
        aqd.fetch_data()
    elif sys.argv[2] == 'insert':
        aqd.insert_data()
    else:
        print('wrong param')
    
    # print(aqd.get_max_id())
    # status_code,html = Aqd.get_html_by_url("/videos/play/6988")
    # data = Aqd.movie_page_data(html)
    # print(data)
