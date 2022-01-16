#!/usr/bin/env python3
# -*- coding:utf-8 -*-
import sys
import time
import getopt
import requests
import sqlite3
import math
import re
import os
from lxml import etree
from install import buildSqliteDb
import common
'''
图片服务器:
https://jp.netcdn.space/digital/video/miae00056/miae00056jp-10.jpg
https://pics.dmm.co.jp/digital/video/miae00056/miae00056jp-10.jpg
https://pics.dmm.com/digital/video/miae00056/miae00056jp-10.jpg
小封面:
https://jp.netcdn.space/digital/video/miae00056/miae00056ps.jpg
https://pics.javbus.info/thumb/{{linkid}}.jpg
大封面:
https://jp.netcdn.space/digital/video/miae00056/miae00056pl.jpg
https://pics.javcdn.pw/cover/3tya_b.jpg
https://pics.javcdn.pw/cover/{{linkid}}_b.jpg
'''


class Avmo:

    def __init__(self):
        print('avmo.init')
        # ================主要配置================

        # sqlite数据库地址
        self.sqlite_file = common.get_db_file()
        # 主函数延时 越慢越稳，请求过快会403
        self.main_sleep = 1.5

        # 其他配置初始化
        self.config()

    # 默认配置
    def config(self):
        print('avmo.config')
        # 插入阈值
        self.insert_threshold = 10

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
        self.conn()

        # 创建会话对象
        self.s = requests.Session()
        # 超时时间
        self.s.timeout = 3
        self.s.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36',
        }
        # 代理
        self.s.proxies = {
            # 'https':'http://127.0.0.1:1080'
        }
        # 番号主页url
        self.movie_url = self.get_avmoo_site() + '/movie/'
        # 导演 制作 发行 系列
        self.director_url = self.get_url('director', '')
        self.studio_url = self.get_url('studio', '')
        self.label_url = self.get_url('label', '')
        self.series_url = self.get_url('series', '')

    # sqlite conn
    def conn(self):
        # 链接sqlite
        self.CONN = sqlite3.connect(self.sqlite_file, check_same_thread=False)
        self.CUR = self.CONN.cursor()
        # 如果不存在则新建表
        buildSqliteDb(self.CONN, self.CUR)
    
    def get_avmoo_site(self):
        if hasattr(self, 'site_url') and self.site_url != None:
            return self.site_url
        
        res = self.s.get('https://tellme.pw/avmoo')
        html = etree.HTML(res.text)
        avmoUrl = html.xpath('/html/body/div[1]/div[2]/div/div[2]/h4[1]/strong/a/@href')[0]
        print("newUrl:{}".format(avmoUrl))
        self.site_url = avmoUrl
        return avmoUrl

    def get_url(self, pagetype, linkid, page_no=None):
        if page_no == None or page_no == 1:
            return '{}/{}/{}/{}'.format(self.get_avmoo_site(), common.get_country(), pagetype, linkid)
        else:
            return '{}/{}/{}/{}/page/{}'.format(self.get_avmoo_site(), common.get_country(), pagetype, linkid, page_no)

    def linkid_general_by_stars(self, stars_id):
        for page_no in range(1, 1000):
            url = self.get_url('star', stars_id, page_no)
            # time.sleep(500)
            res = self.s.get(url)
            if res.status_code != 200:
                print("get:{},status_code:{}".format(url, res.status_code))
                break
            html = etree.HTML(res.text)
            print("get:{},page_length:{}".format(url, len(res.text)))
            movieIdList = html.xpath('//*[@id="waterfall"]/div/a/@href')
            if movieIdList == [] or movieIdList == None:
                print("page empty break")
                break
            for item in movieIdList:
                yield item[-16:]

    # 根据列表抓取
    def spider_by_stars_list(self, stars_id_list):
        for stars in stars_id_list:
            # 全集搜索，碰到相同就跳出
            self.spider_by_stars(stars, True)

    # 抓取指定影片
    def spider_by_movie(self, movie_linkid):
        url = self.get_url('movie', movie_linkid)
        res = self.s.get(url)
        try:
            html = etree.HTML(res.text)
        except:
            print(url, 'etree.HTML error')
            return

        # 解析页面内容
        data = self.movie_page_data(html)
        data['linkid'] = movie_linkid
        self.movie_save([tuple(data.values())])
        print("影片{}抓取完成".format(movie_linkid))
    
    # 主函数，抓取页面内信息
    def spider_by_stars(self, stars_linkid, is_increment):
        starsData = self.stars_one(stars_linkid)
        print("[{}] spider_by_stars start".format(starsData['name']))
        # 查询db全集去重
        self.CUR.execute(
            "SELECT linkid from av_list where stars_url LIKE '%{}%'".format(stars_linkid))
        db_res = self.CUR.fetchall()
        movie_id_exist_list = [x[0] for x in db_res]
        print("已存在影片数量,{}".format(len(movie_id_exist_list)))
        # 待插入
        insert_list = []
        skip_count = 0
        insert_count = 0
        for item in self.linkid_general_by_stars(stars_linkid):
            # 过滤已存在影片
            url = self.get_url('movie', item)
            if item in movie_id_exist_list:
                skip_count += 1
                # 如果为增量更新，碰到相同就跳出
                if is_increment:
                    break
                continue
            time.sleep(self.main_sleep)
            try:
                res = self.s.get(url)
                if res.status_code != 200:
                    print(url, res.status_code)
                    continue
            except:
                print(url, 'requests.get error')
                continue
            try:
                html = etree.HTML(res.text)
            except:
                print(url, 'etree.HTML error')
                continue

            # 解析页面内容
            data = self.movie_page_data(html)
            data['linkid'] = item
            # 输出当前进度
            print(data['av_id'].ljust(15), data['release_date'].ljust(11), data['stars'])

            insert_list.append(tuple(data.values()))
            # 存储数据
            if len(insert_list) == self.insert_threshold:
                self.movie_save(insert_list)
                insert_count += len(insert_list)
                insert_list = []
        # 插入剩余的数据
        self.movie_save(insert_list)
        insert_count += len(insert_list)
        print("stars:{},insert_count:{},skip_count:{}".format(
            starsData['name'], insert_count, skip_count))
        print("[{}] spider_by_stars end".format(starsData['name']))

    # 获取一个明星的信息
    def stars_one(self, linkid):
        starsRes = common.fetchall(self.CUR, "SELECT * from av_stars where linkid='{}'".format(linkid))
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
        try:
            response = self.s.get(url)
            html = etree.HTML(response.text)
        except:
            data['birthday'] = 'error'
            self.stars_save(data)
            return False

        if response.status_code == 403:
            print(data['id'], '  ', data['linkid'], '  status_code:403')
            exit()
        if response.status_code == 404:
            return False

        try:
            data['name'] = html.xpath(
                '/html/head/meta[8]/@content')[0].split(',', 1)[0]
            data['headimg'] = html.xpath(
                '//*[@id="waterfall"]/div[1]/div/div[1]/img/@src')[0].split('/', 3)[3].replace('mono/actjpgs/nowprinting.gif', '')
        except:
            print(response.text)
            return False

        for item_p in html.xpath('//*[@id="waterfall"]/div[1]/div/div[2]/p'):
            if item_p.text == None:
                continue
            if '生日:' in item_p.text or 'Birthday:' in item_p.text:
                data['birthday'] = get_val(item_p.text)
                continue
            if '身高:' in item_p.text or 'Height:' in item_p.text:
                data['height'] = get_val(item_p.text)
                continue
            if '罩杯:' in item_p.text or 'Cup:' in item_p.text:
                data['cup'] = get_val(item_p.text)
                continue
            if '胸围:' in item_p.text or 'Bust:' in item_p.text:
                data['bust'] = get_val(item_p.text)
                continue
            if '腰围:' in item_p.text or 'Waist:' in item_p.text:
                data['waist'] = get_val(item_p.text)
                continue
            if '臀围:' in item_p.text or 'Hips:' in item_p.text:
                data['hips'] = get_val(item_p.text)
                continue
            if '出生地:' in item_p.text or 'Hometown:' in item_p.text:
                data['hometown'] = get_val(item_p.text)
                continue
            if '爱好:' in item_p.text or 'Hobby:' in item_p.text:
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

    def stars_save(self, data):
        insert_sql = 'REPLACE INTO {} VALUES(?,?,?,?,?,?,?,?,?,?,?,?);'.format(
            self.table_stars
        )
        self.CUR.execute(insert_sql, tuple(data.values()))
        self.CONN.commit()

    # 插入数据库
    def movie_save(self, insert_list):
        if len(insert_list) == 0:
            print("insert_list empty!")
            return
        insertSql = 'REPLACE INTO {0}({1})VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?);'.format(self.table_main, self.column_str)
        self.CUR.executemany(insertSql, insert_list)
        self.CONN.commit()
        print('INSERT:', len(insert_list))

    def movie_page_data(self, html):
        data = {
            'linkid':'',
            'av_id':'',
            'director':'',
            'director_url':'',
            'studio':'',
            'studio_url':'',
            'label':'',
            'label_url':'',
            'series':'',
            'series_url':'',
            'genre':'',
            'stars':'',
            'stars_url':'',
            'image_len':'',
            'len':'',
            'title':'',
            'bigimage':'',
            'release_date':''
        }
        # 番号
        try:
            data['av_id'] = html.xpath(
                '/html/body/div[2]/div[1]/div[2]/p[1]/span[2]/text()')[0]
        except:
            return data
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
        data['genre'] = '|'.join(html.xpath(
            '/html/body/div[2]/div[1]/div[2]/p/span/a/text()')).replace("'", '"')
        # genre_url_list = html.xpath(
        #     '/html/body/div[2]/div[1]/div[2]/p/span/a/@href')
        # if genre_url_list != None and len(genre_url_list) != 0:
        #     data[10] = '|' + '|'.join(
        #         [re.findall('([a-z0-9]+)$', x)[0] for x in genre_url_list])

        # 演员stars
        data['stars'] = '|'.join(html.xpath(
            '//div[@id="avatar-waterfall"]/a/span/text()')).replace("'", '"')
        if data['stars'] != '':
            data['stars'] = '|' + data['stars']

        # stars_url
        stars_url_list = html.xpath('//div[@id="avatar-waterfall"]/a/@href')
        if stars_url_list != None and len(stars_url_list) != 0:
            data['stars_url'] = '|' + '|'.join([re.findall('([a-z0-9]+)$', x)[0]
                                      for x in stars_url_list])

        # 图片个数image_len
        data['image_len'] = str(len(html.xpath('//div[@id="sample-waterfall"]/a')))
        # 时长len
        lentext = html.xpath('/html/body/div[2]/div[1]/div[2]/p[3]/text()')
        if len(lentext) != 0 and '分钟' in lentext[0]:
            data['len'] = lentext[0].replace('分钟', '').strip()
        else:
            data['len'] = '0'

        # 标题
        data['title'] = html.xpath('/html/body/div[2]/h3/text()')[0]
        # 封面 截取域名之后的部分
        data['bigimage'] = '/' + \
            html.xpath(
                '/html/body/div[2]/div[1]/div[1]/a/img/@src')[0].split('/', 5)[5]
        # 发行时间
        data['release_date'] = html.xpath(
            '/html/body/div[2]/div[1]/div[2]/p[2]/text()')[0].strip()

        return data

    # 获取所有类别
    def genre_update(self):
        genre_url = self.get_url('genre', '')
        html = etree.HTML(self.s.get(
            genre_url).text)
        insert_list = []
        h4 = html.xpath('/html/body/div[2]/h4/text()')
        div = html.xpath('/html/body/div[2]/div')
        for div_item in range(len(div)):
            g_title = h4[div_item]
            a_list = div[div_item].xpath('a')
            for a_item in a_list:
                if a_item.text == None:
                    continue
                g_name = a_item.text  # .replace('・','')
                g_id = a_item.attrib.get('href')[-16:]
                insert_list.append(
                    "'{0}','{1}','{2}'".format(g_id, g_name, g_title))
        sql = "REPLACE INTO {} (linkid,name,title)VALUES({});".format(
            self.table_genre, "),(".join(insert_list))
        self.CUR.execute(sql)
        self.CONN.commit()
        print('genre update record:{}'.format(len(insert_list)))


if __name__ == '__main__':
    pass