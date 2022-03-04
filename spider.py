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

    def __init__(self):
        self.last_insert_list = []
        self.running_work = None
        self.done_work = []

    def __new__(cls, *args, **kwargs):
        if not cls.instance:
            cls.instance = super(Spider, cls).__new__(cls)
        return cls.instance

    def run(self):
        # 启动爬虫线程
        if CONFIG.getboolean("base", "readonly"):
            return
        thread = threading.Thread(target=self.spider_thread, args=())
        thread.daemon = True
        thread.start()

    @staticmethod
    def db():
        if Spider.db_ins is None:
            print('spider.db.init')
            # 链接数据库
            Spider.db_ins = sqlite3.connect(CONFIG.get("base", "db_file"))
        return Spider.db_ins

    @staticmethod
    def requests():
        if Spider.requests_ins is None:
            print('spider.requests.init')
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
        print("spider_thread.start")
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
                work_param["exist_linkid"] = get_exist_linkid(work_param["page_type"], work_param["keyword"])

            print("="*10, " crawl start ", "=" * 10)
            print("url:{0[url]} page_limit:{0[page_limit]}, exist_count:{1}".format(
                    work_param, len(work_param["exist_linkid"])))
            ret = self.crawl_accurate(work_param)

            # 打开浏览器提醒抓取完成
            if ret:
                # 清空缓存
                if CONFIG.getboolean("website", "use_cache"):
                    SQL_CACHE.clear()
                if CONFIG.getboolean("website", "auto_open_link_when_crawl_done"):
                    open_browser_tab(get_local_url(work_param["page_type"], work_param["keyword"], work_param["page_start"]))

            print("="*10, " crawl end ", "=" * 10)
            print()

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

    # 根据链接参数抓取
    def crawl_accurate(self, work_param: dict) -> bool:
        page_type = work_param["page_type"]
        if not page_type:
            print("wrong param")
            return False
        # 单个电影
        if page_type == "movie":
            (status_code, data) = self.crawl_by_movie_linkid(work_param["keyword"])
            if data is None or status_code != 200:
                print("crawl_by_movie_linkid wrong,data:{},status_code:{}", data, status_code)
                return False
            self.movie_save([data])
            return True
        # 其他
        if page_type in ('genre', 'series', 'studio', 'label', 'director', 'search', 'star', 'popular'):
            self.crawl_by_page_type(work_param)
            return True
        print("wrong param,work_param:{}".format(work_param))
        return False

    # 获取所有类别
    @staticmethod
    def crawl_genre() -> list:
        genre_url = get_url('genre', '')
        print("get:{}".format(genre_url))
        (status_code, html) = Spider.get_html_by_url(genre_url)
        insert_list = []
        h4 = html.xpath('/html/body/div[2]/h4/text()')
        div = html.xpath('/html/body/div[2]/div')
        for div_item in range(len(div)):
            g_title = h4[div_item]
            a_list = div[div_item].xpath('a')
            for a_item in a_list:
                if a_item.text is None:
                    continue
                insert_list.append({
                    "linkid": a_item.attrib.get('href')[-16:],
                    "name": a_item.text,
                    "title": g_title
                })
        print('genre fetch record:{}'.format(len(insert_list)))
        return insert_list

    # 根据页面类型抓取所有影片
    def crawl_by_page_type(self, work_param: dict) -> None:
        if work_param["page_type"] == 'star':
            self.stars_one(work_param["keyword"])
        # 待插入
        insert_list = []
        insert_count = 0
        skip_count = 0
        banned_count = 0
        continued_skip_count = 0
        for movie_linkid in self.linkid_general(work_param):
            # 跳出
            if self.running_work["status"] != "ING":
                # 任务结束
                break
            
            # 跳过已存在的
            if movie_linkid in work_param["exist_linkid"]:
                skip_count += 1
                continued_skip_count += 1
                print("SKIP EXIST,URL:{}".format(get_local_url("movie", movie_linkid)))
                # 连续跳过到指定数量，则跳出抓取
                if continued_skip_count >= CONFIG.getint("spider", "continued_skip_limit"):
                    break
                continue

            continued_skip_count = 0
            time.sleep(CONFIG.getfloat("spider", "sleep"))

            (status_code, data) = self.crawl_by_movie_linkid(movie_linkid)
            if status_code == 403:
                banned_count += 1
                if banned_count == 10:
                    print("banned count:{},break loop".format(banned_count))
                    break
                continue
            if data is None:
                continue
            
            # 判断影片是否符合要求
            duration = CONFIG.getint("spider", "minimum_movie_duration")
            if duration > 0 and data["len"] < duration:
                print("movie duration non conformance,url:" + get_url("movie", movie_linkid))
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
        print("[exist_count:{}][fetch_count:{}][skip_count:{}]".format(
            len(work_param["exist_linkid"]), insert_count, skip_count))

    # 根据linkid抓取一个movie页面
    def crawl_by_movie_linkid(self, movie_linkid: str) -> tuple:
        url = get_url('movie', movie_linkid)
        (status_code, html) = Spider.get_html_by_url(url)
        if status_code != 200:
            return status_code, None
        if html is None:
            return status_code, None
        # 解析页面内容
        try:
            data = self.movie_page_data(html)
        except Exception as e:
            print('movie_page_data error:', e)
            return status_code, None

        if data is None or data['av_id'] == '' or data["title"] == '':
            print("movie crawl fatal,linkid:{}".format(movie_linkid))
            return 500, None
        data['linkid'] = movie_linkid
        # 输出当前进度
        print(data['av_id'].ljust(15),
              data['release_date'].ljust(11), data['stars'])
        return status_code, data

    # 获取一个明星的信息
    def stars_one(self, linkid: str):
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
        print("get:{}".format(url))
        (status_code, html) = Spider.get_html_by_url(url)
        if html is None:
            data['birthday'] = 'error'
            self.stars_save(data)
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
            if item_p.text is None:
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
        print(
            data['birthday'].ljust(13),
            data['height'].ljust(7),
            data['cup'].ljust(3),
            data['bust'].ljust(7),
            data['waist'].ljust(7),
            data['hips'].ljust(7),
            data['name'].ljust(15),
            data['hometown']
        )
        self.stars_save(data)
        return data

    # 自动翻页返回movie_id
    @staticmethod
    def linkid_general(work_param: dict) -> Iterator[str]:
        # 网站限制最多100页
        for page_no in range(work_param["page_start"], work_param["page_limit"] + 1):
            time.sleep(CONFIG.getfloat("spider", "sleep"))

            url = get_url(work_param["page_type"], work_param["keyword"], page_no)
            print("get:{}".format(url))

            (status_code, html) = Spider.get_html_by_url(url)
            if status_code in [403, 404, 500] or html is None:
                break

            movie_id_list = html.xpath('//*[@id="waterfall"]/div/a/@href')
            if not movie_id_list:
                print("page empty break")
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
        if len(insert_list) == 0:
            return
        self.last_insert_list = insert_list

        insert_sql = replace_sql_build(AV_LIST, insert_list[0])
        cur = Spider.db().cursor()
        cur.executemany(insert_sql, [tuple(x.values()) for x in insert_list])
        Spider.db().commit()
        print('INSERT:', len(insert_list))

    # 解析html数据
    @staticmethod
    def movie_page_data(html) -> dict:
        data = {
            'linkid': '',
            # 番号
            'av_id': html.xpath('/html/body/div[2]/div[1]/div[2]/p[1]/span[2]/text()')[0].strip(),
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
        if len(len_text) != 0:
            res = re.findall("(\\d+)", len_text[0])
            if len(res) != 0:
                data['len'] = int(res[0].strip())

        # 获取：导演、制作商、发行商、系列
        right_info = html.xpath('/html/body/div[2]/div[1]/div[2]/p/a')
        for i in right_info:
            if i.text is None:
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
            storage_ret = storage(AV_GENRE, {"linkid": [link[-16:]]}, "name")
            if not storage_ret:
                # 添加新类目
                genre_data = {
                    'linkid': link[-16:],
                    'name': name,
                    'title': '未知分类'
                }
                print('find new genre:', genre_data)
                sql = replace_sql_build(AV_GENRE, genre_data)
                Spider.db().execute(sql, tuple(genre_data.values()))
                Spider.db().commit()
                DATA_STORAGE[AV_GENRE].clear()

        data['genre'] = '|'.join(genre_list)
        if data['genre'] != '':
            data['genre'] = '|' + data['genre'] + '|'

        # 演员stars
        star_list = html.xpath('//div[@id="avatar-waterfall"]/a/span/text()')
        data['stars'] = '|'.join([x.strip() for x in star_list])
        if data['stars'] != '':
            data['stars'] = '|' + data['stars'] + '|'

        # stars_url
        stars_url_list = html.xpath('//div[@id="avatar-waterfall"]/a/@href')
        if stars_url_list is not None and len(stars_url_list) != 0:
            data['stars_url'] = '|' + '|'.join([re.findall('([a-z0-9]+)$', x)[0]
                                                for x in stars_url_list])

        return data

    @staticmethod
    def get_html_by_url(url: str) -> tuple:
        retry_limit = 3
        for i in range(retry_limit):
            try:
                res = Spider.requests().get(url, timeout=CONFIG.getint("requests", "timeout"))
                if res.status_code != 200:
                    print("status_code = {},url:{}".format(res.status_code, url))
                    return res.status_code, None

                return 200, etree.HTML(res.text)
            except Timeout as e:
                print("requests Timeout,error:{}\nretry url:{}".format(
                    e, url
                ))
                # 休眠
                time.sleep(10)
                # 超时重试
                continue

            except ConnectionError as e:
                print("requests ConnectionError,error:{}\nretry url:{}".format(
                    e, url
                ))
                # 休眠
                time.sleep(10)
                # 链接异常
                continue

            except Exception as e:
                print("requests Exception:{}\nurl:{}".format(e, url))
                time.sleep(10)
                continue
        # 返回错误
        return 500, None


if __name__ == '__main__':
    pass
