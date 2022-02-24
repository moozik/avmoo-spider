#!/usr/bin/env python3
# -*- coding:utf-8 -*-
import time
import requests
import re
import common
import sqlite3
from lxml import etree
from typing import Iterator, List

class Avmo:

    def __init__(self):
        print('avmo.init')
        # 表结构
        self.column = [
            'linkid',
            'av_id',
            'director', 'director_url',
            'studio', 'studio_url',
            'label', 'label_url',
            'series', 'series_url',
            'genre',
            'stars', 'stars_url',
            'image_len', 'len', 'title', 'bigimage', 'release_date', ]
        # 表结构str
        self.column_str = ",".join(self.column)
        # 上次插入
        self.last_insert_list = []
        # 创建会话对象
        self.s = requests.Session()
        # 超时时间
        self.s.timeout = common.CONFIG.getint("requests", "timeout")
        self.s.headers = {
            'User-Agent': common.CONFIG.get("requests", "user_agent"),
        }
        # 代理
        self.s.proxies = {
            # 'https':'http://127.0.0.1:1080'
        }
        # 链接数据库
        self.CONN = sqlite3.connect(common.CONFIG.get(
            "base", "db_file"), check_same_thread=False)
        self.CUR = self.CONN.cursor()

    # 根据链接参数抓取
    def crawl_accurate(self, page_type: str, keyword: str, page_start: int, page_limit: int,
                       exist_linkid_dict: dict) -> bool:
        # 单个电影
        if page_type == "movie":
            (status_code, data) = self.crawl_by_movie_linkid(keyword)
            if data is None or status_code != 200:
                return False
            self.movie_save([data])
            return True
        # 其他
        if page_type in ('genre', 'series', 'studio', 'label', 'director', 'search', 'star'):
            self.crawl_by_page_type(page_type, keyword, page_start, page_limit, exist_linkid_dict)
            return True
        print("wrong param,page_type:{}, keyword:{}, page_start:{}".format(
            page_type, keyword, page_start))
        return False

    # 获取所有类别
    def crawl_genre(self) -> None:
        genre_url = common.get_url('genre', '')
        print("get:{}".format(genre_url))
        (status_code, html) = self.get_html_by_url(genre_url)
        insert_list = []
        h4 = html.xpath('/html/body/div[2]/h4/text()')
        div = html.xpath('/html/body/div[2]/div')
        for div_item in range(len(div)):
            g_title = h4[div_item]
            a_list = div[div_item].xpath('a')
            for a_item in a_list:
                if a_item.text is None:
                    continue
                g_name = a_item.text
                g_id = a_item.attrib.get('href')[-16:]
                insert_list.append((g_id, g_name, g_title))
        sql = "REPLACE INTO av_genre (linkid,name,title)VALUES(?,?,?);"
        self.CUR.executemany(sql, insert_list)
        self.CONN.commit()
        print('genre update record:{}'.format(len(insert_list)))

    # 根据页面类型抓取所有影片
    def crawl_by_page_type(self, page_type: str, keyword: str, page_start: int, page_limit: int,
                           exist_linkid_dict: dict) -> None:
        print("[exist_count:{}]".format(
            len(exist_linkid_dict)))
        if page_type == 'star':
            self.stars_one(keyword)
        # 待插入
        insert_list = []
        insert_count = 0
        skip_count = 0
        banned_count = 0
        continued_skip_count = 0
        for movie_linkid in self.linkid_general(page_type, keyword, page_start, page_limit):
            # 跳过已存在的
            if movie_linkid in exist_linkid_dict:
                skip_count += 1
                continued_skip_count += 1
                print("SKIP EXIST,URL:{}".format(common.get_local_url("movie", movie_linkid)))
                # 连续跳过到指定数量，则跳出抓取
                if continued_skip_count >= common.CONFIG.getint("spider", "continued_skip_limit"):
                    break
                continue

            continued_skip_count = 0
            time.sleep(common.CONFIG.getfloat("spider", "sleep"))

            (status_code, data) = self.crawl_by_movie_linkid(movie_linkid)
            if status_code == 403:
                banned_count += 1
                if banned_count == 10:
                    print("banned count:{},break loop".format(banned_count))
                    break
                continue
            if data is None:
                continue
            insert_list.append(data)
            # 存储数据
            if len(insert_list) == common.CONFIG.getint("spider", "insert_threshold"):
                self.movie_save(insert_list)
                insert_count += len(insert_list)
                insert_list = []
        # 插入剩余的数据
        self.movie_save(insert_list)
        insert_count += len(insert_list)
        print("[exist_count:{}][fetch_count:{}][skip_count:{}]".format(
            len(exist_linkid_dict), insert_count, skip_count))

    # 根据linkid抓取一个movie页面
    def crawl_by_movie_linkid(self, movie_linkid: str) -> List[int, dict]:
        url = common.get_url('movie', movie_linkid)
        (status_code, html) = self.get_html_by_url(url)
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

        if data is None or data["av_id"] == "" or data["title"] == "":
            print("movie crawl fatal,linkid:{}".format(movie_linkid))
            return 500, None
        data['linkid'] = movie_linkid
        # 输出当前进度
        print(data['av_id'].ljust(15),
              data['release_date'].ljust(11), data['stars'])
        return status_code, data

    # 获取一个明星的信息
    def stars_one(self, linkid: str):
        stars_res = common.fetchall(self.CUR, "SELECT * FROM av_stars WHERE linkid='{}'".format(linkid))
        if len(stars_res) == 1:
            return stars_res[0]

        def get_val(str_param):
            return str_param.split(':')[1].strip()

        url = common.get_url('star', linkid)
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
        (status_code, html) = self.get_html_by_url(url)
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
            if common.list_in_str(('生日:', 'Birthday:', '生年月日:'), item_p.text):
                data['birthday'] = get_val(item_p.text)
                continue
            if common.list_in_str(('身高:', 'Height:', '身長:'), item_p.text):
                data['height'] = get_val(item_p.text)
                continue
            if common.list_in_str(('罩杯:', 'Cup:', 'ブラのサイズ:'), item_p.text):
                data['cup'] = get_val(item_p.text)
                continue
            if common.list_in_str(('胸围:', 'Bust:', 'バスト:'), item_p.text):
                data['bust'] = get_val(item_p.text)
                continue
            if common.list_in_str(('腰围:', 'Waist:', 'ウエスト:'), item_p.text):
                data['waist'] = get_val(item_p.text)
                continue
            if common.list_in_str(('臀围:', 'Hips:', 'ヒップ:'), item_p.text):
                data['hips'] = get_val(item_p.text)
                continue
            if common.list_in_str(('出生地:', 'Hometown:', '出身地:'), item_p.text):
                data['hometown'] = get_val(item_p.text)
                continue
            if common.list_in_str(('爱好:', 'Hobby:', '趣味:'), item_p.text):
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
    def linkid_general(self, page_type: str, keyword: str, page_start: int = 1, page_limit: int = 100) -> Iterator[str]:
        # 网站限制最多100页
        for page_no in range(page_start, page_limit + 1):
            time.sleep(common.CONFIG.getfloat("spider", "sleep"))

            url = common.get_url(page_type, keyword, page_no)
            print("get:{}".format(url))

            (status_code, html) = self.get_html_by_url(url)
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

    def stars_save(self, data: dict) -> None:
        insert_sql = 'REPLACE INTO av_stars VALUES(?,?,?,?,?,?,?,?,?,?,?,?);'
        self.CUR.execute(insert_sql, tuple(data.values()))
        self.CONN.commit()

    # 插入数据库
    def movie_save(self, insert_list: list) -> None:
        if len(insert_list) == 0:
            return
        self.last_insert_list = insert_list
        insert_sql = 'REPLACE INTO av_list({})VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?);'.format(
            self.column_str)
        self.CUR.executemany(insert_sql, [tuple(x.values()) for x in insert_list])
        self.CONN.commit()
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
            'image_len': str(len(html.xpath('//div[@id="sample-waterfall"]/a'))),
            'len': '0',
            # 标题
            'title': html.xpath('/html/body/div[2]/h3/text()')[0].strip(),
            # 封面 截取域名之后的部分
            'bigimage': '/' + html.xpath('/html/body/div[2]/div[1]/div[1]/a/img/@src')[0].split('/', 5)[5].strip(),
            # 发行时间
            'release_date': html.xpath('/html/body/div[2]/div[1]/div[2]/p[2]/text()')[0].strip()
        }
        # 时长len
        lentext = html.xpath('/html/body/div[2]/div[1]/div[2]/p[3]/text()')
        if len(lentext) != 0:
            res = re.findall("(\\d+)", lentext[0])
            if len(res) != 0:
                data['len'] = res[0].strip()

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

        # 获取类别列表genre 类别列表genre_url
        data['genre'] = '|'.join(html.xpath(
            '/html/body/div[2]/div[1]/div[2]/p/span/a/text()'))
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

    def get_last_insert_list(self):
        return self.last_insert_list

    def get_html_by_url(self, url: str) -> tuple:
        try:
            res = self.s.get(url)
            if res.status_code != 200:
                print("status_code = {},url:{}".format(res.status_code, url))
                return res.status_code, None

            return 200, etree.HTML(res.text)
        except:
            return 500, None


if __name__ == '__main__':
    pass
