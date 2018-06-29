#!/usr/bin/env python3
#-*- coding:utf-8 -*-
import sys
import time
import getopt
import requests
import sqlite3
import re
import os
from lxml import etree

'''
未启用的两个函数
data_check()
按照主表检查缺少数据，时间非常长，需手动配置
test_page() 输出单页数据


图片服务器：
https://jp.netcdn.space/digital/video/miae00056/miae00056jp-10.jpg
https://pics.dmm.co.jp/digital/video/miae00056/miae00056jp-10.jpg
https://pics.dmm.com/digital/video/miae00056/miae00056jp-10.jpg
小封面：
https://jp.netcdn.space/digital/video/miae00056/miae00056ps.jpg
https://pics.javbus.info/thumb/{{linkid}}.jpg
大封面:
https://jp.netcdn.space/digital/video/miae00056/miae00056pl.jpg
'''

class avmo:
 
    def __init__(self):
        
        #================主要配置================

        #目标域名
        self.site = 'javlog.com'

        #sqlite数据库地址
        if os.path.exists('avmoo_.db'):
            self.sqlite_file = 'avmoo_.db'
        else:
            self.sqlite_file = 'avmoo.db'
        #其他配置初始化
        self.config()

        #================测试区间================
        '''
        #重试缺失地址
        # self.data_check()
        exit()
        '''

        #================读取参数================
        try:
            opts, args = getopt.getopt(
                sys.argv[1:],
                "hs:e:arp:gt",
                ['help', 'start', 'end', 'auto', 'retry', 'proxies', 'genre', 'stars']
            )
        except:
            self.usage()
            exit()

        for op, value in opts:
            if op == '-s' or op == '-start':
                self.start_id = value
            elif op == '-e' or op == '-end':
                self.stop_id = value
            elif op == '-a' or op == '-auto':
                self.auto = True
            elif op == '-p' or op == '-proxies':
                self.s.proxies['https'] = value
            elif op == '-r' or op == '-retry':
                if self.action != 'movie':
                    print('参数错误')
                    exit()
                else:
                    self.action = 'retry'
            elif op == '-g' or op == '-genre':
                if self.action != 'movie':
                    print('参数错误')
                    exit()
                else:
                    self.action = 'genre'
            elif op == '-t' or op == '-stars':
                if self.action != 'movie':
                    print('参数错误')
                    exit()
                else:
                    self.action = 'stars'
            elif op == '-h' or op == '-help':
                self.usage()
                exit()
        #展示说明
        if len(sys.argv) == 1:
            self.usage()
            exit()

        if self.action == 'retry':
            self.retry_errorurl()
            exit()
        elif self.action == 'genre':
            self.genre_update()
            exit()
        elif self.action == 'stars':
            self.stars_loop()
            exit()
        elif self.auto == True:
            self.get_last()

        #主程序
        self.main(self.get_linkid())

    #默认配置
    def config(self):
        #默认抓电影
        self.action = 'movie'
        #待insert数据
        self.insert_list = []
        #遍历linkid
        self.abc_sequence = '0123456789abcdefghijklmnopqrstuvwxyz'
        #获取sl的字典列表dl
        self.dl = {}
        for item in range(len(self.abc_sequence)):
            self.dl[self.abc_sequence[item]] = item


        #主函数延时
        self.main_sleep = 1
        #更新flag
        self.last_flag = False
        #是否重试
        self.flag_retry = True
        #开始id
        self.start_id = '0000'
        #结束id
        self.stop_id = 'zzzz'
        #自动获取start stop
        self.auto = False

        #插入阈值
        self.insert_threshold = 20
        #用于重试失败计数
        self.retry_counter = 0
        #重试阈值
        self.retry_threshold = 5


        #主表
        self.table_main = 'av_list'
        #重试表
        self.table_retry = 'av_error_linkid'
        self.table_genre = 'av_genre'
        self.table_stars = 'av_stars'
        #表结构
        self.column = ['id', 'linkid', 'director', 'director_url', 'studio',
                       'studio_url', 'label', 'label_url', 'series', 'series_url', 'image_len',
                       'genre', 'len', 'stars', 'av_id', 'title', 'bigimage', 'release_date']
        #表结构str
        self.column_str = ",".join(self.column)
        #链接数据库
        self.conn()

        #站点url
        self.site_url = 'https://{0}/cn'.format(self.site)

        #番号主页url
        self.movie_url = self.site_url+'/movie/'
        #导演 制作 发行 系列
        self.director = self.site_url+'/director/'
        self.studio = self.site_url+'/studio/'
        self.label = self.site_url+'/label/'
        self.series = self.site_url+'/series/'
        self.genre_url = self.site_url+'/genre/'
        self.star_url = self.site_url+'/star/'

        #创建会话对象
        self.s = requests.Session()
        #超时时间
        self.s.timeout = 3
        self.s.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/67.0.3396.99 Safari/537.36'
        }
        #代理
        self.s.proxies = {
            #'https':'https://127.0.0.1:1080'
        }
    #mysql conn
    def conn(self):
        try:
            #链接sqlite
            self.CONN = sqlite3.connect(self.sqlite_file, check_same_thread=False)
            self.CUR = self.CONN.cursor()
        except:
            print('connect database fail.')
            sys.exit()
        try:
            self.CUR.execute('select count(1) from ' + self.table_main)
        except:
            self.CUR.execute('''
            CREATE TABLE "av_list" (
            "id"  INTEGER,
            "linkid"  TEXT(10) NOT NULL,
            "title"  TEXT(500),
            "av_id"  TEXT(50),
            "release_date"  TEXT(20),
            "len"  TEXT(20),
            "director"  TEXT(100),
            "studio"  TEXT(100),
            "label"  TEXT(100),
            "series"  TEXT(200),
            "genre"  TEXT(200),
            "stars"  TEXT(300),
            "director_url"  TEXT(10),
            "studio_url"  TEXT(10),
            "label_url"  TEXT(10),
            "series_url"  TEXT(10),
            "bigimage"  TEXT(200),
            "image_len"  INTEGER,
            PRIMARY KEY ("linkid")
            ); '''.replace("av_list", self.table_main))
        try:
            self.CUR.execute('select count(1) from ' + self.table_retry)
        except:
            self.CUR.execute('''
            CREATE TABLE "av_error_linkid" (
            "linkid"  TEXT(4) NOT NULL,
            "status_code"  INTEGER,
            "datetime"  TEXT(50),
            PRIMARY KEY ("linkid")
            ); '''.replace("av_error_linkid", self.table_retry))

    #写出命令行格式
    def usage(self):
        usage = '''
        -h(-help):使用说明
        -s(-start):开始id(0000,1ddd,36wq)
        -e(-end):结束id(0000,1ddd,36wq)
        -a(-auto):获取当前数据库最新的一个id和网站最新的一个id，补全新增数据
        -r(-retry):重试错误链接
        -g(-genre):更新类别
        -t(-stars):更新演员
        -p(-proxies):使用指定的https代理服务器或SOCKS5代理服务器。例如：-p http://127.0.0.1:1080,-p socks5://127.0.0.1:52772
        '''
        print(usage)

    #主函数，抓取页面内信息
    def main(self, looplist):
        for item in looplist:
            url = self.movie_url + item
            time.sleep(self.main_sleep)
            try:
                res = self.s.get(url)
                if res.status_code != 200:
                    self.insert_retry((item, res.status_code))
                    print(url, res.status_code)
                    continue
            except:
                print(url, 'requests.get error')
                self.insert_retry((item, 777))
                continue
            try:
                html = etree.HTML(res.text)
            except:
                print(url, 'etree.HTML error')
                self.insert_retry((item, 888))
                continue

            #解析页面内容
            data = self.movie_page_data(html)
            #从linkid获取id
            id_column = self.linkid2id(item)
            #输出当前进度
            print(data[12].ljust(30), data[15].ljust(11), item.ljust(5), id_column)

            self.insert_list.append(
                "'{0}','{1}','{2}'".format(id_column, item, "','".join(data))
            )
            #存储数据
            if len(self.insert_list) == self.insert_threshold:
                self.movie_save()

    #获取最后一次的id
    def get_last(self):
        sql = "SELECT linkid FROM {0} ORDER BY linkid DESC LIMIT 0,1".format(self.table_main)
        self.CUR.execute(sql)
        res = self.CUR.fetchall()
        self.start_id = res[0][0]
        try:
            response = self.s.get(self.site_url)
        except:
            print('访问超时')
            exit()
        if response.status_code != 200:
            print('页面返回错误')
            exit()
        html = etree.HTML(response.text)
        self.stop_id = html.xpath('//*[@id="waterfall"]/div[1]/a')[0].attrib.get('href')[-4:]
        print('database start:{0},website end:{1}'.format(self.start_id, self.stop_id))
    
    #插入重试表
    def insert_retry(self, data):
        self.CUR.execute("REPLACE INTO {0}(linkid, status_code, datetime)VALUES('{1[0]}', {1[1]}, '{2}');"
            .format(
                self.table_retry,
                data,
                time.strftime(
                    "%Y-%m-%d %H:%M:%S",
                    time.localtime()
                )
            )
        )
        self.CONN.commit()

    #获取演员
    def stars_loop(self):
        self.CUR.execute(
            'SELECT linkid FROM {} ORDER BY linkid DESC LIMIT 0,1'.format(self.table_stars))
        self.start_id = self.CUR.fetchall()[0][0]
        self.stop_id = '1000'
        def get_val(str):
            return str.split(':')[1].strip()

        page_404_count = 0
        for linkid in self.get_linkid():
            url = self.star_url + linkid
            print(linkid, self.linkid2id(linkid))
            try:
                response = self.s.get(url)
                html = etree.HTML(response.text)
            except:
                if response:
                    if response.status_code == 404:
                        print(linkid, 'status_code:404')
                        break
                    else:
                        print(linkid,
                            'status_code:',response.status_code)
                        time.sleep(5)
                        continue
            data = {
                'id': self.linkid2id(linkid),
                'linkid': linkid,
                'name': '',
                'birthday':'',
                'height':'',
                'cup':'',
                'bust':'',
                'waist':'',
                'hips':'',
                'hometown':'',
                'hobby':'',
                'headimg': ''
            }
            if response.status_code == 403:
                print(response.status_code)
                exit()
            if response.status_code == 404:
                page_404_count += 1
                if page_404_count == 10:
                    print('stat 404 count:100')
                    exit()
                else:
                    page_404_count == 0
                    print(data['id'],'  ',data['linkid'],'  ',page_404_count)
                    self.stars_save(data)
                    continue
            del(response)

            try:
                data['name'] = html.xpath(
                    '/html/head/meta[8]/@content')[0].split(',', 1)[0]
                data['headimg'] = html.xpath(
                    '//*[@id="waterfall"]/div[1]/div/div[1]/img/@src')[0].split('/', 3)[3].replace('mono/actjpgs/nowprinting.gif', '')
            except:
                print(response.text)
                exit()
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
            #print(data['id'],'  ','  '.join(list(data.values())[1:-1]))
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
            if data['cup'] == 'F':
                time.sleep(5)
            elif data['cup'] == 'E':
                time.sleep(3)
            elif data['cup'] == 'D':
                time.sleep(2.5)
            elif data['cup'] == 'C':
                time.sleep(2)
            elif data['cup'] == 'B':
                time.sleep(1)
            else:
                time.sleep(1)
    def stars_save(self, data):
        insert_sql = 'REPLACE INTO "{}" VALUES({},"{}","{}","{}","{}","{}","{}","{}","{}","{}","{}","{}")'.format(
            self.table_stars,
            data['id'],
            data['linkid'],
            data['name'],
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
    #遍历urlid
    def get_linkid(self):
        for abcd in self.abc_map():
            if abcd <= self.start_id:
                continue
            
            if self.start_id < abcd <= self.stop_id:
                yield abcd
            
            if abcd > self.stop_id:
                print('start:{0} end:{1} done!'.format(self.start_id, self.stop_id))
                if self.action == 'movie':
                    #插入剩余的数据
                    self.movie_save()
                    #重试错误数据
                    self.retry_errorurl()
                exit()
    #由urlid获取排序自增id
    def linkid2id(self, item):
        return self.dl[item[3]] + self.dl[item[2]]*36 + self.dl[item[1]]*1296 + self.dl[item[0]]*46656

    #插入数据库
    def movie_save(self):
        if len(self.insert_list) == 0:
            return

        self.replace_sql(self.table_main, self.column_str, "),(".join(self.insert_list))
        print('rows:', len(self.insert_list), 'retry_counter:', self.retry_counter)
        self.insert_list = []
        self.retry_counter += 1

        if self.flag_retry:
            #重试失败地址
            if self.retry_counter >= self.retry_threshold:
                self.retry_counter = 0
                self.retry_errorurl()

    def replace_sql(self, table, column, data):
        self.CUR.execute("REPLACE INTO {0}({1})VALUES({2});".format(table, column, data))
        self.CONN.commit()
    
    #重试
    def retry_errorurl(self):
        self.CUR.execute("SELECT * FROM {0} WHERE status_code<>'404' ORDER BY linkid;".format(self.table_retry))
        res_retry = self.CUR.fetchall()
        reslen = len(res_retry)
        if reslen == 0:
            return
        print('retry error url count:', reslen)

        del_list = []
        update_list = []

        def update_sql(update_list):
            time_now = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
            sql = "REPLACE INTO {0}(linkid, status_code, datetime)VALUES({1});".format(
            self.table_retry, "),(".join(["'{0[0]}',{0[1]},'{1}'".format(x, time_now) for x in update_list]))
            self.CUR.execute(sql)
            self.CONN.commit()
        
        def delete_sql(del_list):
            sql = 'DELETE FROM {0} WHERE {1};'.format(
                self.table_retry, ' OR '.join([" linkid='{0}' ".format(x) for x in del_list]))
            self.CUR.execute(sql)
            self.CONN.commit()
        
        for item in res_retry:
            retry_linkid = item[0]
            reslen -= 1

            #统一更新表，提高效率
            if len(update_list) == 20:
                update_sql(update_list)
                update_list = []
                print('some status_code update done.')

            url = self.movie_url + retry_linkid
            try:
                response = self.s.get(url)
                html = etree.HTML(response.text)
            except:
                # 重写重试记录
                if response.status_code == 404:
                    update_list.append((retry_linkid, 404))
                print(reslen, retry_linkid, 'status_code:404')
                continue

            if response.status_code != 200:
                # 重写重试记录
                update_list.append((retry_linkid, response.status_code))
                print(reslen, retry_linkid, 'status_code:{}'.format(response.status_code))
                continue
            print(reslen, retry_linkid, 'success')
            data = self.movie_page_data(html)
            id = self.linkid2id(retry_linkid)
            self.insert_list.append("'{0}','{1}','{2}'".format(id, retry_linkid, "','".join(data)))
            del_list.append(retry_linkid)

            #存储数据
            if len(self.insert_list) == self.insert_threshold:
                #插入数据
                print(self.insert_threshold, 'insert.')
                self.replace_sql(self.table_main, self.column_str, "),(".join(self.insert_list))
                if del_list != []:
                    delete_sql(del_list)
                    del_list = []
        #插入数据
        if len(self.insert_list) != 0:
            self.replace_sql(self.table_main, self.column_str, "),(".join(self.insert_list))
        #删除数据
        if len(del_list) != 0:
            delete_sql(del_list)
        #更新数据
        if len(update_list) != 0:
            update_sql(update_list)

    def movie_page_data(self, html):
        data = ['' for x in range(16)]
        #番号
        try:
            data[12] = html.xpath('/html/body/div[2]/div[1]/div[2]/p[1]/span[2]/text()')[0]
        except:
            return data
        #获取：导演、制作商、发行商、系列
        right_info = html.xpath('/html/body/div[2]/div[1]/div[2]/p/a')
        for i in right_info:
            if i.text == None:
                continue
            tmp_text = i.text.replace("'", '"')
            tmp_href = i.attrib.get('href')

            if self.director in tmp_href:
                #导演
                data[0] = tmp_text
                data[1] = tmp_href.replace(self.director, '')
            elif self.studio in tmp_href:
                #制作商
                data[2] = tmp_text
                data[3] = tmp_href.replace(self.studio, '')
            elif self.label in tmp_href:
                #发行商
                data[4] = tmp_text
                data[5] = tmp_href.replace(self.label, '')
            elif self.series in tmp_href:
                #系列
                data[6] = tmp_text
                data[7] = tmp_href.replace(self.series, '')

        #图片个数image_len
        data[8] = str(len(html.xpath('//*[@id="sample-waterfall"]/a')))
        #获取类别列表genre
        data[9] = '|'.join(html.xpath('/html/body/div[2]/div[1]/div[2]/p/span/a/text()')).replace("'", '"')
        #时长len
        lentext = html.xpath('/html/body/div[2]/div[1]/div[2]/p[3]/text()')
        if len(lentext) != 0 and '分钟' in lentext[0]:
            data[10] = lentext[0].replace('分钟', '').strip()
        else:
            data[10] = '0'
        #演员stars
        data[11] = '|'.join(html.xpath('//*[@id="avatar-waterfall"]/a/span/text()')).replace("'", '"')

        #接取除了番号的标题
        data[13] = html.xpath('/html/body/div[2]/h3/text()')[0][len(data[12]) + 1:].replace("'", '"')
        #封面 截取域名之后的部分
        data[14] = '/' + html.xpath('/html/body/div[2]/div[1]/div[1]/a/img/@src')[0].split('/',5)[5]
        #发行时间
        data[15] = html.xpath('/html/body/div[2]/div[1]/div[2]/p[2]/text()')[0].strip()
        return data
    def abc_map(self):
        for i1 in self.abc_sequence:
            for i2 in self.abc_sequence:
                for i3 in self.abc_sequence:
                    for i4 in self.abc_sequence:
                        yield (i1 + i2 + i3 + i4)
    
    #检查被遗漏的页面，并插入数据库
    #按照linkid的顺序检查漏掉的番号，并不是从重试表检索
    def data_check(self):
        self.CUR.execute("SELECT linkid FROM {0} WHERE 1 ORDER BY linkid;".format(self.table_main))
        res = self.CUR.fetchall()

        res_list = [x[0] for x in res]
        res_min = res_list[0]
        res_max = res_list[len(res)-1]
        miss_list = []

        for abcd in self.abc_map():
            if abcd <= res_min:
                continue
            if abcd >= res_max:
                break

            if abcd in res_list:
                continue
            else:
                miss_list.append(abcd)
                continue

        print('miss count:', len(miss_list))
        print('需要遍历请手动修改代码')
        exit()
        self.CUR.execute('DELETE FROM "{0}";'.format(self.table_retry))
        self.CONN.commit()
        if len(miss_list) != 0:
            for item in miss_list:
                self.CUR.execute('INSERT INTO "{0}" ("linkid") VALUES ("{1}");'.format(self.table_retry, item))
            self.CONN.commit()
        else:
            print("miss_linkid no fond")
            return

        #重试错误链接并插入数据库
        self.CUR.execute('SELECT linkid FROM "{0}" ORDER BY linkid;'.format(self.table_retry))
        res = self.CUR.fetchall()
        self.main([x[0] for x in res])
        #插入剩余的数据
        self.movie_save()

    #获取所有类别
    def genre_update(self):
        html = etree.HTML(self.s.get(self.genre_url).text)
        insert_list = []
        h4 = html.xpath('/html/body/div[2]/h4/text()')
        div = html.xpath('/html/body/div[2]/div')
        for div_item in range(len(div)):
            g_title = h4[div_item]
            a_list = div[div_item].xpath('a')
            for a_item in a_list:
                if a_item.text == None:
                    continue
                g_name = a_item.text#.replace('・','')
                g_id = a_item.attrib.get('href').replace(self.genre_url,'')
                insert_list.append("'{0}','{1}','{2}'".format(g_id,g_name,g_title))
        
        sql = "REPLACE INTO {} (id,name,title)VALUES({});".format(self.table_genre, "),(".join(insert_list))
        self.CUR.execute(sql)
        self.CONN.commit()
        print('本次更新类别：{}条'.format(len(insert_list)))
    
    #测试单个页面
    def test_page(self, linkid):
        url = self.movie_url + linkid
        res = self.s.get(url).text
        #解析页面内容
        data = self.movie_page_data(etree.HTML(res))
        print(data)


if __name__ == '__main__':
    avmo()
