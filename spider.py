#!/usr/bin/env python3
# -*- coding:utf-8 -*-
import time

from requests import Timeout

from typing import Iterator
from common import *


class Spider:
    instance = None
    requests_ins = None
    db_ins = None
    log = logging.getLogger('spider')

    def __init__(self):
        self.last_insert_list = []
        self.running_work = None
        self.done_work = []

    def __new__(cls, *args, **kwargs):
        if not cls.instance:
            cls.instance = super(Spider, cls).__new__(cls)
        return cls.instance

    def run(self):
        create_logger('spider')
        # 启动爬虫线程
        if CONFIG.getboolean("base", "readonly"):
            return
        thread = threading.Thread(target=self.spider_thread, args=())
        thread.daemon = True
        thread.start()

    @staticmethod
    def db():
        if Spider.db_ins is None:
            Spider.log.info('spider.db.init')
            # 链接数据库
            Spider.db_ins = sqlite3.connect(CONFIG.get("base", "db_file"))
            Spider.db_ins.row_factory = make_dicts
        return Spider.db_ins

    @staticmethod
    def requests():
        if Spider.requests_ins is None:
            Spider.log.info('spider.requests.init')
            # 创建会话对象
            Spider.requests_ins = requests.Session()
            Spider.requests_ins.headers = {
                'User-Agent': CONFIG.get("requests", "user_agent"),
            }
            # 代理
            Spider.requests_ins.proxies = {
                # 'https':'http://127.0.0.1:1080'
            }
        return Spider.requests_ins

    # 爬虫线程
    def spider_thread(self):
        Spider.log.info("spider_thread.start")
        while True:
            time.sleep(CONFIG.getfloat("spider", "sleep"))

            # 获取一个任务
            work_param = QUEUE.get()
            work_param["url"] = get_url(work_param["page_type"], work_param["keyword"], work_param["page_start"])
            work_param["status"] = "ING"

            # 记录运行中任务
            self.running_work = work_param.copy()

            work_param["exist_linkid"] = {}
            # 是否跳过 默认跳过
            if "skip_exist" not in work_param or work_param.get("skip_exist"):
                work_param["exist_linkid"] = Spider.get_exist_linkid(work_param["page_type"], work_param["keyword"])

            Spider.log.info("[crawl start]url:{0[url]} page_limit:{0[page_limit]}, exist_count:{1}".format(
                    work_param, len(work_param["exist_linkid"])))
            ret = self.crawl_accurate(work_param)

            # 打开浏览器提醒抓取完成
            if ret:
                # 清空缓存
                if CONFIG.getboolean("website", "use_cache"):
                    SQL_CACHE.clear()
                if CONFIG.getboolean("website", "auto_open_link_when_crawl_done"):
                    open_browser_tab(get_local_url(work_param["page_type"], work_param["keyword"], work_param["page_start"]))


            if "exist_linkid" in self.running_work:
                del self.running_work["exist_linkid"]
            self.done_work.append(self.running_work)
            self.running_work = None

    def get_last_insert_list(self):
        return self.last_insert_list

    def get_running_work(self, action: str = ''):
        if action:
            self.running_work["status"] = action
            return
        return self.running_work

    def get_done_work(self):
        return self.done_work

    @staticmethod
    def fetchall(sql) -> list:
        cur = Spider.db().cursor()
        cur.execute(sql)
        return cur.fetchall()

    # 根据链接参数抓取
    def crawl_accurate(self, work_param: dict) -> bool:
        page_type = work_param["page_type"]
        if not page_type:
            Spider.log.error("wrong param")
            return False
        # 单个电影
        if page_type == "movie":
            (status_code, data) = Spider.crawl_by_movie_linkid(work_param["keyword"])
            if empty(data) or status_code != 200:
                Spider.log.warning("crawl_by_movie_linkid wrong,data:%r,status_code:%d", data, status_code)
                return False
            self.movie_save([data])
            return True
        # 其他
        if page_type in ('genre', 'series', 'studio', 'label', 'director', 'search', 'star', 'popular'):
            self.crawl_by_page_type(work_param)
            return True
        Spider.log.fatal("wrong param,work_param:%s", work_param)
        return False

    # 获取所有类别
    @staticmethod
    def crawl_genre() -> list:
        genre_url = get_url('genre', '')
        Spider.log.info("get:%s", genre_url)
        (status_code, html) = Spider.get_html_by_url(genre_url)
        insert_list = []
        h4 = html.xpath('/html/body/div[2]/h4/text()')
        div = html.xpath('/html/body/div[2]/div')
        for div_item in range(len(div)):
            g_title = h4[div_item]
            a_list = div[div_item].xpath('a')
            for a_item in a_list:
                if empty(a_item.text):
                    continue
                insert_list.append({
                    "linkid": a_item.attrib.get('href')[-16:],
                    "name": a_item.text,
                    "title": g_title
                })
        Spider.log.info('genre fetch record:%r', len(insert_list))
        return insert_list

    # 根据页面类型抓取所有影片
    def crawl_by_page_type(self, work_param: dict) -> None:
        if work_param["page_type"] == 'star':
            Spider.stars_one(work_param["keyword"])
        # 待插入
        insert_list = []
        insert_count = 0
        skip_count = 0
        banned_count = 0
        continued_skip_count = 0
        for movie_linkid in Spider.linkid_general(work_param):
            # 跳出
            if self.running_work["status"] != "ING":
                # 任务结束
                break

            # 跳过已存在的
            if movie_linkid in work_param["exist_linkid"]:
                skip_count += 1
                continued_skip_count += 1
                Spider.log.info("SKIP EXIST,URL:%s", get_local_url("movie", movie_linkid))
                # 连续跳过到指定数量，则跳出抓取
                if continued_skip_count >= CONFIG.getint("spider", "continued_skip_limit"):
                    break
                continue

            continued_skip_count = 0
            time.sleep(CONFIG.getfloat("spider", "sleep"))

            (status_code, data) = Spider.crawl_by_movie_linkid(movie_linkid)
            if status_code == 403:
                banned_count += 1
                if banned_count == 10:
                    Spider.log.info("banned count:%d,break loop", banned_count)
                    break
                continue
            if empty(data):
                continue

            # 判断影片是否符合要求
            duration = CONFIG.getint("spider", "minimum_movie_duration")
            if duration > 0 and data["len"] < duration:
                Spider.log.info("movie duration non conformance,url:%s", get_url("movie", movie_linkid))
                continue

            insert_list.append(data)
            # 存储数据
            if len(insert_list) == CONFIG.getint("spider", "insert_threshold"):
                self.movie_save(insert_list)
                insert_count += len(insert_list)
                insert_list = []
        # 插入剩余的数据
        self.movie_save(insert_list)
        insert_count += len(insert_list)
        Spider.log.info("[exist_count:{}][fetch_count:{}][skip_count:{}]".format(
            len(work_param["exist_linkid"]), insert_count, skip_count))

    # 根据linkid抓取一个movie页面
    @staticmethod
    def crawl_by_movie_linkid(movie_linkid: str) -> tuple:
        url = get_url('movie', movie_linkid)
        (status_code, html) = Spider.get_html_by_url(url)
        if status_code != 200:
            return status_code, None
        if html is None:
            return status_code, None
        # 解析页面内容
        try:
            data = Spider.movie_page_data(html)
        except Exception as e:
            Spider.log.error('movie_page_data error:%r', e)
            return status_code, None

        if empty(data) or empty(data['av_id']) or empty(data["title"]):
            Spider.log.error("movie crawl fatal,linkid:%s", movie_linkid)
            return 500, None
        data['linkid'] = movie_linkid
        # 输出当前进度
        Spider.log.info(data['av_id'].ljust(15) + data['release_date'] + ' ' + data['stars'])
        return status_code, data

    # 获取一个明星的信息
    @staticmethod
    def stars_one(linkid: str):
        stars_res = Spider.fetchall("SELECT * FROM av_stars WHERE linkid='{}'".format(linkid))
        if len(stars_res) == 1:
            return stars_res[0]

        def get_val(str_param):
            return str_param.split(':')[1].strip()

        url = get_url('star', linkid)
        data = {
            'linkid': linkid,
            'name': '',
            'name_history': '',
            'birthday': '',
            'height': '',
            'cup': '',
            'bust': '',
            'waist': '',
            'hips': '',
            'hometown': '',
            'hobby': '',
            'headimg': ''
        }
        Spider.log.info("get:%s", url)
        (status_code, html) = Spider.get_html_by_url(url)
        if html is None:
            return False

        try:
            data['name'] = html.xpath(
                '/html/head/meta[8]/@content')[0].split(',', 1)[0]
            data['headimg'] = html.xpath(
                '//*[@id="waterfall"]/div[1]/div/div[1]/img/@src')[0].split('/', 3)[3].replace(
                'mono/actjpgs/nowprinting.gif', '')
        except:
            return False

        for item_p in html.xpath('//*[@id="waterfall"]/div[1]/div/div[2]/p'):
            if empty(item_p.text):
                continue
            if list_in_str(('生日:', 'Birthday:', '生年月日:'), item_p.text):
                data['birthday'] = get_val(item_p.text)
                continue
            if list_in_str(('身高:', 'Height:', '身長:'), item_p.text):
                data['height'] = get_val(item_p.text)
                continue
            if list_in_str(('罩杯:', 'Cup:', 'ブラのサイズ:'), item_p.text):
                data['cup'] = get_val(item_p.text)
                continue
            if list_in_str(('胸围:', 'Bust:', 'バスト:'), item_p.text):
                data['bust'] = get_val(item_p.text)
                continue
            if list_in_str(('腰围:', 'Waist:', 'ウエスト:'), item_p.text):
                data['waist'] = get_val(item_p.text)
                continue
            if list_in_str(('臀围:', 'Hips:', 'ヒップ:'), item_p.text):
                data['hips'] = get_val(item_p.text)
                continue
            if list_in_str(('出生地:', 'Hometown:', '出身地:'), item_p.text):
                data['hometown'] = get_val(item_p.text)
                continue
            if list_in_str(('爱好:', 'Hobby:', '趣味:'), item_p.text):
                data['hobby'] = get_val(item_p.text)
                continue
        # 讲括号中的名字记录为曾用名
        tmp = data['name'].replace('（', '(').replace('）', '').split('(')
        if len(tmp) == 2:
            data['name_history'] = tmp[1]
        Spider.log.info("star:%r", data)
        Spider.stars_save(data)
        return data

    # 自动翻页返回movie_id
    @staticmethod
    def linkid_general(work_param: dict) -> Iterator[str]:
        # 网站限制最多100页
        for page_no in range(work_param["page_start"], work_param["page_limit"] + 1):
            time.sleep(CONFIG.getfloat("spider", "sleep"))

            url = get_url(work_param["page_type"], work_param["keyword"], page_no)
            Spider.log.info("get:{}".format(url))

            (status_code, html) = Spider.get_html_by_url(url)
            if status_code in [403, 404, 500] or html is None:
                break

            movie_id_list = html.xpath('//*[@id="waterfall"]/div/a/@href')
            if not movie_id_list:
                Spider.log.warning("page empty break")
                break
            for item in movie_id_list:
                yield item[-16:]

            # 检查是否有下一页
            next_page = html.xpath(
                '//span[@class="glyphicon glyphicon-chevron-right"]')
            if not next_page:
                break

    @staticmethod
    def stars_save(data: dict) -> None:
        insert_sql = replace_sql_build(AV_STARS, data)
        Spider.db().execute(insert_sql, tuple(data.values()))
        Spider.db().commit()

    # 插入数据库
    def movie_save(self, insert_list: list) -> None:
        if empty(insert_list):
            return
        self.last_insert_list = insert_list

        insert_sql = replace_sql_build(AV_LIST, insert_list[0])
        cur = Spider.db().cursor()
        cur.executemany(insert_sql, [tuple(x.values()) for x in insert_list])
        Spider.db().commit()
        Spider.log.info('INSERT:%d', len(insert_list))

    # 解析html数据
    @staticmethod
    def movie_page_data(html) -> dict:
        data = {
            'linkid': '',
            # 番号
            'av_id': html.xpath('/html/body/div[2]/div[1]/div[2]/p[1]/span[2]/text()')[0].strip().upper(),
            'director': '',
            'director_url': '',
            'studio': '',
            'studio_url': '',
            'label': '',
            'label_url': '',
            'series': '',
            'series_url': '',
            'genre': '',
            'stars': '',
            'stars_url': '',
            # 图片个数image_len
            'image_len': int(len(html.xpath('//div[@id="sample-waterfall"]/a'))),
            'len': 0,
            # 标题
            'title': html.xpath('/html/body/div[2]/h3/text()')[0].strip(),
            # 封面 截取域名之后的部分
            'bigimage': '/' + html.xpath('/html/body/div[2]/div[1]/div[1]/a/img/@src')[0].split('/', 5)[5].strip(),
            # 发行时间
            'release_date': html.xpath('/html/body/div[2]/div[1]/div[2]/p[2]/text()')[0].strip()
        }
        # 时长len
        len_text = html.xpath('/html/body/div[2]/div[1]/div[2]/p[3]/text()')
        if non_empty(len_text):
            res = re.findall("(\\d+)", len_text[0])
            if non_empty(res):
                data['len'] = int(res[0].strip())

        # 获取：导演、制作商、发行商、系列
        right_info = html.xpath('/html/body/div[2]/div[1]/div[2]/p/a')
        for i in right_info:
            if empty(i.text):
                continue
            tmp_href = i.attrib.get('href')

            if "/director/" in tmp_href:
                # 导演
                data['director'] = i.text.strip()
                data['director_url'] = tmp_href[-16:]
            elif "/studio/" in tmp_href:
                # 制作商
                data['studio'] = i.text.strip()
                data['studio_url'] = tmp_href[-16:]
            elif "/label/" in tmp_href:
                # 发行商
                data['label'] = i.text.strip()
                data['label_url'] = tmp_href[-16:]
            elif "/series/" in tmp_href:
                # 系列
                data['series'] = i.text.strip()
                data['series_url'] = tmp_href[-16:]

        genre_list = []
        # 获取类别列表genre 类别列表genre_url
        for genre_tag in html.xpath('/html/body/div[2]/div[1]/div[2]/p/span/a'):
            # 获取类目链接
            link = genre_tag.attrib.get('href')
            # 获取类目名
            name = genre_tag.text.strip()
            genre_list.append(name)

            # 查看类目是否存在,不存在则添加
            storage_ret = storage(AV_GENRE, {"linkid": link[-16:]}, "name")
            if empty(storage_ret):
                # 添加新类目
                genre_data = {
                    'linkid': link[-16:],
                    'name': name,
                    'title': '未知分类'
                }
                Spider.log.info('find new genre:%r', genre_data)
                sql = replace_sql_build(AV_GENRE, genre_data)
                Spider.db().execute(sql, tuple(genre_data.values()))
                Spider.db().commit()
                DATA_STORAGE[AV_GENRE].clear()

        data['genre'] = '|'.join(genre_list)
        if non_empty(data['genre']):
            data['genre'] = '|' + data['genre'] + '|'

        # 演员stars
        star_list = html.xpath('//div[@id="avatar-waterfall"]/a/span/text()')
        data['stars'] = '|'.join([x.strip() for x in star_list])
        if non_empty(data['stars']):
            data['stars'] = '|' + data['stars'] + '|'

        # stars_url
        stars_url_list = html.xpath('//div[@id="avatar-waterfall"]/a/@href')
        if non_empty(stars_url_list):
            data['stars_url'] = '|' + '|'.join([re.findall('([a-z0-9]+)$', x)[0]
                                                for x in stars_url_list])

        return data

    # 查询已存在影片
    @staticmethod
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
            genre = Spider.fetchall("SELECT name FROM av_genre WHERE linkid='{}'".format(keyword))
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
        if non_empty(sql):
            ret = Spider.fetchall(sql)
            exist_linkid_dict = {x["linkid"]: True for x in ret}
        return exist_linkid_dict

    @staticmethod
    def get_html_by_url(url: str) -> tuple:
        retry_limit = 100
        for i in range(retry_limit):
            try:
                res = Spider.requests().get(url, timeout=CONFIG.getint("requests", "timeout"))
                if res.status_code != 200:
                    Spider.log.error("status_code = {},url:{}".format(res.status_code, url))
                    return res.status_code, None

                return 200, etree.HTML(res.text)
            except Timeout as e:
                Spider.log.warning("requests Timeout,error:{}\nretry url:{}".format(
                    e, url
                ))
                # 休眠
                time.sleep(10)
                # 超时重试
                continue

            except ConnectionError as e:
                Spider.log.warning("requests ConnectionError,error:{}\nretry url:{}".format(
                    e, url
                ))
                # 休眠
                time.sleep(10)
                # 链接异常
                continue

            except Exception as e:
                Spider.log.warning("requests Exception:{}\nurl:{}".format(e, url))
                time.sleep(10)
                continue
        # 返回错误
        return 500, None


if __name__ == '__main__':
    pass
