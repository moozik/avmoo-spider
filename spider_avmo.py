#!/usr/bin/env python3
# -*- coding:utf-8 -*-
import time
import requests
import re
from lxml import etree
import common
from typing import Iterator


class Avmo:

    def __init__(self):
        print('avmo.init')
        # 主表
        self.table_main = 'av_list'
        self.table_genre = 'av_genre'
        self.table_stars = 'av_stars'
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
        # 链接数据库
        self.CONN = common.DB["CONN"]
        self.CUR = common.DB["CUR"]

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
        self.last_insert_list = []

    def get_last_insert_list(self):
        return self.last_insert_list

    def get_url(self, page_type: str, linkid: str, page_no: int = 1) -> str:
        ret = '{}/{}/{}/{}'.format(common.CONFIG.get("base", "avmoo_site"),
                                   common.CONFIG.get("base", "country"), page_type, linkid)
        if page_no > 1:
            ret = ret + '/page/{}'.format(page_no)
        return ret
    
    def get_html_by_url(self, url):
        try:
            res = self.s.get(url)
            if res.status_code != 200:
                print("status_code != 200,url:{}", url)
                if res.status_code == 403:
                    exit()
                return None
            
            return etree.HTML(res.text)
        except:
            return None
    
    def crawl_by_url(self, link: str) -> None:
        if link == None or link == "":
            return
        res = re.findall(
            "https?://[^/]+/[^/]+/(movie|star|genre|series|studio|label|director|search)/([^/]+)(/page/(\d+))?", link)
        if res == None or len(res) == 0:
            print("格式不正确,link:{}".format(link))
            return
        page_type = res[0][0]
        keyword = res[0][1]
        page_start = 1
        if res[0][3] != "":
            page_start = int(res[0][3])

        ret = self.crawl_accurate(page_type, keyword, page_start)
        if not ret:
            print("错误的链接,link:{},res:{}".format(link, res))
    
    # 根据链接参数抓取
    def crawl_accurate(self, page_type: str, keyword: str, page_start: int = 1, is_increment: bool = False) -> None:
        # 单个电影
        if page_type == "movie":
            data = self.crawl_by_movie_linkid(keyword)
            if data == None:
                return False
            self.movie_save([data])
            return True
        # 演员
        if page_type == "star":
            early_linkid_list = []
            if is_increment:
                early_linkid_list = self.get_early_linkid_list([keyword])
            self.crawl_by_stars(keyword, early_linkid_list, page_start)
            return True
        # 其他
        if page_type in ('genre', 'series', 'studio', 'label', 'director', 'search'):
            self.crawl_by_page_type(page_type, keyword, page_start)
            return True
        print("错误的参数,page_type:{}, keyword:{}, page_start:{}".format(
            page_type, keyword, page_start))
        return False

    # 自动翻页返回movie_id
    def linkid_general(self, page_type: str, keyword: str, page_start: int = 1) -> Iterator[str]:
        for page_no in range(page_start, 100000):
            url = self.get_url(page_type, keyword, page_no)
            print("get:{}".format(url))
            html = self.get_html_by_url(url)
            if html == None:
                continue
            movie_id_list = html.xpath('//*[@id="waterfall"]/div/a/@href')
            if movie_id_list == []:
                print("page empty break")
                break
            for item in movie_id_list:
                yield item[-16:]

            # 检查是否有下一页
            next_page = html.xpath(
                '//span[@class="glyphicon glyphicon-chevron-right"]')
            if next_page == []:
                break

    # 根据演员列表抓取 增量更新
    def crawl_by_stars_list(self, stars_id_list: list[str], is_increment: bool) -> None:
        # 存储所有演员的最新影片id
        early_linkid_list = []
        if is_increment:
            early_linkid_list = self.get_early_linkid_list(stars_id_list)
        for stars in stars_id_list:
            self.crawl_by_stars(stars, early_linkid_list)

    def get_early_linkid_list(self, stars_id_list: list[str]) -> list[str]:
        early_linkid_list = []
        for stars in stars_id_list:
            # 查询db全集去重
            self.CUR.execute(
                "SELECT linkid FROM av_list WHERE stars_url LIKE '%{}%' ORDER BY release_date DESC LIMIT 1".format(stars))
            db_res = self.CUR.fetchall()
            if len(db_res) > 0:
                early_linkid_list.append(db_res[0][0])
        return early_linkid_list

    # 抓取演员所有影片
    def crawl_by_stars(self, stars_linkid: str, early_linkid_list: list[str], page_start: int = 1) -> None:
        starsData = self.stars_one(stars_linkid)
        print("-" * 20)
        print("[{}][early_linkid_list:{}][page_start:{}]start".format(
            starsData['name'], len(early_linkid_list), page_start))
        linkid_exist_dict = {}
        if len(early_linkid_list) == 0:
            # 查询db全集去重
            self.CUR.execute(
                "SELECT linkid from av_list where stars_url LIKE '%{}%'".format(stars_linkid))
            db_res = self.CUR.fetchall()
            linkid_exist_dict = {x[0]:True for x in db_res}
            print("exist count:{}".format(len(linkid_exist_dict)))
        # 待插入
        insert_list = []
        skip_count = 0
        insert_count = 0
        for movie_linkid in self.linkid_general('star', stars_linkid, page_start):
            # 过滤已存在影片
            if movie_linkid in linkid_exist_dict:
                skip_count += 1
                continue
            # 如果为增量更新，碰到相同就跳出
            if movie_linkid in early_linkid_list:
                skip_count += 1
                break
            data = self.crawl_by_movie_linkid(movie_linkid)
            time.sleep(common.CONFIG.getfloat("spider", "sleep"))
            if data == None:
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
        print("[{}][insert_count:{}][skip_count:{}]end".format(
            starsData['name'], insert_count, skip_count))
        print()

    # 根据页面类型抓取所有影片
    def crawl_by_page_type(self, page_type: str, keyword: str, page_start: int = 1) -> None:
        
        sql = ""
        # 查询已存在的
        if page_type in ['director','studio','label','series']:
            sql = "SELECT linkid FROM av_list WHERE {}_url='{}'".format(page_type, keyword)
        if page_type == 'genre':
            genre = common.fetchall("SELECT * FROM av_genre WHERE linkid='{}'".format(keyword))
            print(genre)
            sql = "SELECT linkid FROM av_list WHERE genre LIKE '%|{}|%'".format(genre[0]['name'])
        ret = common.fetchall(sql)
        exist_linkid_dict = {x["linkid"]:True for x in ret}

        print("[page_type:{}][keyword:{}][exist_count:{}][page_start:{}]start".format(
            page_type, keyword, len(exist_linkid_dict), page_start))

        # 待插入
        insert_list = []
        insert_count = 0
        for movie_linkid in self.linkid_general(page_type, keyword, page_start):
            # 跳过已存在的
            if movie_linkid in exist_linkid_dict:
                print("skip exist movie,linkid:{}".format(movie_linkid))
                continue
            data = self.crawl_by_movie_linkid(movie_linkid)
            time.sleep(common.CONFIG.getfloat("spider", "sleep"))
            if data == None:
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
        print("[count:{}]end".format(insert_count))
        print()

    # 根据linkid抓取一个movie页面
    def crawl_by_movie_linkid(self, movie_linkid: str) -> dict:
        url = self.get_url('movie', movie_linkid)
        html = self.get_html_by_url(url)
        if html == None:
            return None
        # 解析页面内容
        try:
            data = self.movie_page_data(html)
        except Exception as e:
            print('movie_page_data error:', e)
            return None

        if data == None or data["av_id"] == "" or data["title"] == "":
            print("movie crawl fatal,linkid:{}".format(movie_linkid))
            return None
        data['linkid'] = movie_linkid
        # 输出当前进度
        print(data['av_id'].ljust(15),
              data['release_date'].ljust(11), data['stars'])
        return data

    # 获取一个明星的信息
    def stars_one(self, linkid: str):
        starsRes = common.fetchall("SELECT * FROM av_stars WHERE linkid='{}'".format(linkid))
        if len(starsRes) == 1:
            return starsRes[0]

        def get_val(str):
            return str.split(':')[1].strip()

        url = self.get_url('star', linkid)
        print(linkid)
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
        html = self.get_html_by_url(url)
        if html == None:
            data['birthday'] = 'error'
            self.stars_save(data)
            return False

        try:
            data['name'] = html.xpath(
                '/html/head/meta[8]/@content')[0].split(',', 1)[0]
            data['headimg'] = html.xpath(
                '//*[@id="waterfall"]/div[1]/div/div[1]/img/@src')[0].split('/', 3)[3].replace('mono/actjpgs/nowprinting.gif', '')
        except:
            return False

        for item_p in html.xpath('//*[@id="waterfall"]/div[1]/div/div[2]/p'):
            if item_p.text == None:
                continue
            if self.list_in_str(('生日:', 'Birthday:', '生年月日:'), item_p.text):
                data['birthday'] = get_val(item_p.text)
                continue
            if self.list_in_str(('身高:', 'Height:', '身長:'), item_p.text):
                data['height'] = get_val(item_p.text)
                continue
            if self.list_in_str(('罩杯:', 'Cup:', 'ブラのサイズ:'), item_p.text):
                data['cup'] = get_val(item_p.text)
                continue
            if self.list_in_str(('胸围:', 'Bust:', 'バスト:'), item_p.text):
                data['bust'] = get_val(item_p.text)
                continue
            if self.list_in_str(('腰围:', 'Waist:', 'ウエスト:'), item_p.text):
                data['waist'] = get_val(item_p.text)
                continue
            if self.list_in_str(('臀围:', 'Hips:', 'ヒップ:'), item_p.text):
                data['hips'] = get_val(item_p.text)
                continue
            if self.list_in_str(('出生地:', 'Hometown:', '出身地:'), item_p.text):
                data['hometown'] = get_val(item_p.text)
                continue
            if self.list_in_str(('爱好:', 'Hobby:', '趣味:'), item_p.text):
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

    def stars_save(self, data: dict[str, str]) -> None:
        insert_sql = 'REPLACE INTO {} VALUES(?,?,?,?,?,?,?,?,?,?,?,?);'.format(
            self.table_stars
        )
        self.CUR.execute(insert_sql, tuple(data.values()))
        self.CONN.commit()

    # 插入数据库
    def movie_save(self, insert_list: list[dict]) -> None:
        if len(insert_list) == 0:
            print("insert_list empty!")
            return
        self.last_insert_list = insert_list
        insertSql = 'REPLACE INTO {0}({1})VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?);'.format(
            self.table_main, self.column_str)
        self.CUR.executemany(insertSql, [tuple(x.values()) for x in insert_list])
        self.CONN.commit()
        print('INSERT:', len(insert_list))

    # 解析html数据
    def movie_page_data(self, html) -> dict[str, str]:
        data = {
            'linkid': '',
            'av_id': '',
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
            'image_len': '',
            'len': '0',
            'title': '',
            'bigimage': '',
            'release_date': ''
        }
        # 标题
        data['title'] = html.xpath('/html/body/div[2]/h3/text()')[0]

        # 封面 截取域名之后的部分
        data['bigimage'] = '/' + \
            html.xpath(
                '/html/body/div[2]/div[1]/div[1]/a/img/@src')[0].split('/', 5)[5]

        # 发行时间
        data['release_date'] = html.xpath(
            '/html/body/div[2]/div[1]/div[2]/p[2]/text()')[0].strip()

        # 番号
        data['av_id'] = html.xpath(
            '/html/body/div[2]/div[1]/div[2]/p[1]/span[2]/text()')[0]

        # 时长len
        lentext = html.xpath('/html/body/div[2]/div[1]/div[2]/p[3]/text()')
        if len(lentext) != 0:
            res = re.findall("(\d+)", lentext[0])
            if len(res) != 0:
                data['len'] = res[0].strip()

        # 获取：导演、制作商、发行商、系列
        right_info = html.xpath('/html/body/div[2]/div[1]/div[2]/p/a')
        for i in right_info:
            if i.text == None:
                continue
            tmp_text = i.text.replace("'", '"')
            tmp_href = i.attrib.get('href')

            if "/director/" in tmp_href:
                # 导演
                data['director'] = tmp_text
                data['director_url'] = tmp_href[-16:]
            elif "/studio/" in tmp_href:
                # 制作商
                data['studio'] = tmp_text
                data['studio_url'] = tmp_href[-16:]
            elif "/label/" in tmp_href:
                # 发行商
                data['label'] = tmp_text
                data['label_url'] = tmp_href[-16:]
            elif "/series/" in tmp_href:
                # 系列
                data['series'] = tmp_text
                data['series_url'] = tmp_href[-16:]

        # 获取类别列表genre 类别列表genre_url
        data['genre'] = '|' + '|'.join(html.xpath(
            '/html/body/div[2]/div[1]/div[2]/p/span/a/text()')).replace("'", '"') + '|'

        # 演员stars
        data['stars'] = '|'.join(html.xpath(
            '//div[@id="avatar-waterfall"]/a/span/text()')).replace("'", '"')
        if data['stars'] != '':
            data['stars'] = '|' + data['stars'] + '|'

        # stars_url
        stars_url_list = html.xpath('//div[@id="avatar-waterfall"]/a/@href')
        if stars_url_list != None and len(stars_url_list) != 0:
            data['stars_url'] = '|' + '|'.join([re.findall('([a-z0-9]+)$', x)[0]
                                                for x in stars_url_list])

        # 图片个数image_len
        data['image_len'] = str(
            len(html.xpath('//div[@id="sample-waterfall"]/a')))

        return data

    def list_in_str(self, target_list: list[str], target_string: str) -> bool:
        for item in target_list:
            if item in target_string:
                return True
        return False

    # 获取所有类别
    def genre_update(self) -> None:
        genre_url = self.get_url('genre', '')
        print("get:{}".format(genre_url))
        html = self.get_html_by_url(genre_url)
        insert_list = []
        h4 = html.xpath('/html/body/div[2]/h4/text()')
        div = html.xpath('/html/body/div[2]/div')
        for div_item in range(len(div)):
            g_title = h4[div_item]
            a_list = div[div_item].xpath('a')
            for a_item in a_list:
                if a_item.text == None:
                    continue
                g_name = a_item.text
                g_id = a_item.attrib.get('href')[-16:]
                insert_list.append((g_id, g_name, g_title))
        sql = "REPLACE INTO {} (linkid,name,title)VALUES(?,?,?);".format(
            self.table_genre)
        self.CUR.executemany(sql, insert_list)
        self.CONN.commit()
        print('genre update record:{}'.format(len(insert_list)))


if __name__ == '__main__':
    pass
