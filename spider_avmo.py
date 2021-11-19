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
import config
'''
图片服务器：
https://jp.netcdn.space/digital/video/miae00056/miae00056jp-10.jpg
https://pics.dmm.co.jp/digital/video/miae00056/miae00056jp-10.jpg
https://pics.dmm.com/digital/video/miae00056/miae00056jp-10.jpg
小封面：
https://jp.netcdn.space/digital/video/miae00056/miae00056ps.jpg
https://pics.javbus.info/thumb/{{linkid}}.jpg
大封面:
https://jp.netcdn.space/digital/video/miae00056/miae00056pl.jpg
https://pics.javcdn.pw/cover/3tya_b.jpg
https://pics.javcdn.pw/cover/{{linkid}}_b.jpg
'''


class avmo:

    def __init__(self):
        print('avmo.init')
        # ================主要配置================
        # 原网址
        self.site_url = config.getAvmooUrl()

        # sqlite数据库地址
        self.sqlite_file = config.getDbFile()
        # 主函数延时 越慢越稳，请求过快会403
        self.main_sleep = 1.5

        # 其他配置初始化
        self.config()

    def start_by_single(self):
        # ================读取参数================
        try:
            opts, args = getopt.getopt(
                sys.argv[1:],
                "hp:gs:",
                ['help', 'proxies', 'genre', 'stars']
            )
        except:
            self.usage()
            exit()

        # 展示说明
        if len(sys.argv) == 1:
            self.usage()
            exit()

        opt_dict = {}
        opt_r = {
            '-h': '-help',
            '-p': '-proxies',
            '-g': '-genre',
            '-s': '-stars',
        }
        for op, value in opts:
            if op in opt_r:
                opt_dict[opt_r[op]] = value
            else:
                opt_dict[op] = value
        if '-help' in opt_dict:
            self.usage()
            exit()

        if '-proxies' in opt_dict:
            self.s.proxies['https'] = opt_dict['-proxies']

        if '-genre' in opt_dict:
            self.genre_update()
            exit()

        if '-stars' in opt_dict:
            self.spider_by_stars(opt_dict['-stars'])
            exit()

    # 默认配置
    def config(self):
        print('avmo.config')
        # 待insert数据
        self.insert_list = []

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

        # 番号主页url
        self.movie_url = self.site_url+'/movie/'
        # 导演 制作 发行 系列
        self.director_url = self.get_url('cn', 'director', '')
        self.studio_url = self.get_url('cn', 'studio', '')
        self.label_url = self.get_url('cn', 'label', '')
        self.series_url = self.get_url('cn', 'series', '')

        # 创建会话对象
        self.s = requests.Session()
        # 超时时间
        self.s.timeout = 3
        self.s.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/95.0.4638.69 Safari/537.36'
        }
        # 代理
        self.s.proxies = {
            # 'https':'http://127.0.0.1:1080'
        }

    # sqlite conn
    def conn(self):
        # 链接sqlite
        self.CONN = sqlite3.connect(self.sqlite_file, check_same_thread=False)
        self.CUR = self.CONN.cursor()
        # 如果不存在则新建表
        buildSqliteDb(self.CONN, self.CUR)

    # 写出命令行格式
    def usage(self):
        usage = '''
        -h(-help):使用说明
        -g(-genre):更新类别
        -s(-stars):更新演员
        '''
        print(usage.replace('        ', ''))

    def get_url(self, country, pagetype, linkid, pageNo=None):
        if pageNo == None or pageNo == 1:
            return '{}/{}/{}/{}'.format(self.site_url, country, pagetype, linkid)
        else:
            return '{}/{}/{}/{}/page/{}'.format(self.site_url, country, pagetype, linkid, pageNo)

    def linkid_general_by_stars(self, stars_id):
        for pageNo in range(1, 1000):
            url = self.get_url('cn', 'star', stars_id, pageNo)
            res = self.s.get(url)
            print("url.get:{}\n".format(url))
            html = etree.HTML(res.text)
            movieIdList = html.xpath('//*[@id="waterfall"]/div/a/@href')
            if movieIdList == [] or movieIdList == None:
                break
            for item in movieIdList:
                yield item[-16:]

    # 根据列表抓取
    def spider_by_stars_list(self, stars_id_list):
        for stars in stars_id_list:
            self.spider_by_stars(stars)

    # 主函数，抓取页面内信息
    def spider_by_stars(self, stars_id):
        print("spider_by_stars start:{}".format(stars_id))
        self.stars_one(stars_id)
        # 查询db全集去重
        self.CUR.execute(
            "select linkid from av_list where stars_url LIKE '%{}%'".format(stars_id))
        dbRes = self.CUR.fetchall()
        movieIdExistList = [x[0] for x in dbRes]

        for item in self.linkid_general_by_stars(stars_id):
            # 过滤已存在影片
            if item in movieIdExistList:
                #有相同则跳出
                break
            url = self.get_url('cn', 'movie', item)
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
            # 从linkid获取id
            # id_column = self.linkid2id(item)
            # 输出当前进度
            print(data[0].ljust(15), data[16].ljust(11), item.ljust(5))

            self.insert_list.append(
                "'{0}','{1}'".format(item, "','".join(data))
            )
            # 存储数据
            if len(self.insert_list) == self.insert_threshold:
                self.movie_save()
        # 插入剩余的数据
        self.movie_save()
        print("spider_by_stars end:{}".format(stars_id))

    # 获取一个明星的信息
    def stars_one(self, linkid):
        self.CUR.execute(
            "select linkid from av_stars where linkid='{}'".format(linkid))
        starsRes = self.CUR.fetchall()
        if len(starsRes) == 1:
            return

        def get_val(str):
            return str.split(':')[1].strip()

        url = self.get_url('cn', 'star', linkid)
        print(linkid)
        data = {
            # 'id': sort_id,
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
            if '生日' in item_p.text:
                data['birthday'] = get_val(item_p.text)
                continue
            if '身高' in item_p.text:
                data['height'] = get_val(item_p.text)
                continue
            if '罩杯' in item_p.text:
                data['cup'] = get_val(item_p.text)
                continue
            if '胸围' in item_p.text:
                data['bust'] = get_val(item_p.text)
                continue
            if '腰围' in item_p.text:
                data['waist'] = get_val(item_p.text)
                continue
            if '臀围' in item_p.text:
                data['hips'] = get_val(item_p.text)
                continue
            if '出生地' in item_p.text:
                data['hometown'] = get_val(item_p.text)
                continue
            if '爱好' in item_p.text:
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

    def stars_save(self, data):
        insert_sql = 'REPLACE INTO "{}" VALUES("{}","{}","{}","{}","{}","{}","{}","{}","{}","{}","{}","{}")'.format(
            self.table_stars,
            data['linkid'],
            data['name'],
            data['name_history'],
            data['birthday'],
            data['height'],
            data['cup'],
            data['bust'],
            data['waist'],
            data['hips'],
            data['hometown'],
            data['hobby'],
            data['headimg']
        )
        self.CUR.execute(insert_sql)
        self.CONN.commit()

    # 插入数据库
    def movie_save(self):
        if len(self.insert_list) == 0:
            return

        self.replace_sql(self.table_main, self.column_str,
                         "),(".join(self.insert_list))
        print('INSERT:', len(self.insert_list))
        self.insert_list = []

    def replace_sql(self, table, column, data):
        self.CUR.execute(
            "REPLACE INTO {0}({1})VALUES({2});".format(table, column, data))
        self.CONN.commit()

    def movie_page_data(self, html):
        data = ['' for x in range(17)]
        # 番号
        try:
            data[0] = html.xpath(
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
                data[1] = tmp_text
                data[2] = tmp_href[-16:]
            elif "/studio/" in tmp_href:
                # 制作商
                data[3] = tmp_text
                data[4] = tmp_href[-16:]
            elif "/label/" in tmp_href:
                # 发行商
                data[5] = tmp_text
                data[6] = tmp_href[-16:]
            elif "/series/" in tmp_href:
                # 系列
                data[7] = tmp_text
                data[8] = tmp_href[-16:]

        # 获取类别列表genre 类别列表genre_url
        data[9] = '|'.join(html.xpath(
            '/html/body/div[2]/div[1]/div[2]/p/span/a/text()')).replace("'", '"')
        genre_url_list = html.xpath(
            '/html/body/div[2]/div[1]/div[2]/p/span/a/@href')
        # if genre_url_list != None and len(genre_url_list) != 0:
        #     data[10] = '|' + '|'.join(
        #         [re.findall('([a-z0-9]+)$', x)[0] for x in genre_url_list])

        # 演员stars
        data[10] = '|'.join(html.xpath(
            '//div[@id="avatar-waterfall"]/a/span/text()')).replace("'", '"')
        if data[10] != '':
            data[10] = '|' + data[10]

        # stars_url
        stars_url_list = html.xpath('//div[@id="avatar-waterfall"]/a/@href')
        if stars_url_list != None and len(stars_url_list) != 0:
            data[11] = '|' + '|'.join([re.findall('([a-z0-9]+)$', x)[0]
                                      for x in stars_url_list])

        # 图片个数image_len
        data[12] = str(len(html.xpath('//div[@id="sample-waterfall"]/a')))
        # 时长len
        lentext = html.xpath('/html/body/div[2]/div[1]/div[2]/p[3]/text()')
        if len(lentext) != 0 and '分钟' in lentext[0]:
            data[13] = lentext[0].replace('分钟', '').strip()
        else:
            data[13] = '0'

        # 接取除了番号的标题
        data[14] = html.xpath('/html/body/div[2]/h3/text()')[0]
        # 封面 截取域名之后的部分
        data[15] = '/' + \
            html.xpath(
                '/html/body/div[2]/div[1]/div[1]/a/img/@src')[0].split('/', 5)[5]
        # 发行时间
        data[16] = html.xpath(
            '/html/body/div[2]/div[1]/div[2]/p[2]/text()')[0].strip()

        return data

    # 获取所有类别
    def genre_update(self):
        genre_url = self.get_url('cn', 'genre', '')
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
        print('genre update record：{}'.format(len(insert_list)))


if __name__ == '__main__':
    avmo = avmo()
    avmo.start_by_single()
