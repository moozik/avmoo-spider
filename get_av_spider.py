#!/usr/bin/env python3
#-*- coding:utf-8 -*-
import sys
import time
import getopt
import requests
import sqlite3
import re
from lxml import etree

'''
data_check()
按照主表检查缺少数据，时间非常长，需手动配置
test_page() 输出单页数据
replace_genre() 输出所有类别
未启用的两个函数
图片服务器：
https://jp.netcdn.space/digital/video/miae00056/miae00056jp-10.jpg
https://pics.dmm.co.jp/digital/video/miae00056/miae00056jp-10.jpg
https://pics.dmm.com/digital/video/miae00056/miae00056jp-10.jpg
小封面：
https://pics.javbus.info/thumb/{{linkid}}.jpg
'''

class avmo:
 
    def __init__(self):
        
        #================主要配置================

        #目标域名
        self.site = 'javlog.com'

        #sqlite数据库地址
        self.sqlite_file = 'avmoo.db'
        
        #其他配置初始化
        self.config()



        #================测试区间================
        '''
        self.flag_insert = True
        self.conn()
        #清算失败地址，里面还有些能访问的
        self.retry_errorurl()
        #重试失败地址
        # self.retry_errorurl()
        #测试单个页面
        # self.test_page('')
        #检测遗漏项
        # self.flag_check = True
        # self.data_check()
        exit()
        '''

        
        #================读取参数================
        try:
            opts, args = getopt.getopt(
                sys.argv[1:],
                "his:e:arp:",
                ['help', 'insert', 'start', 'end', 'auto', 'retry', 'proxies']
            )
        except:
            self.usage()
            sys.exit()

        for op, value in opts:
            if op == '-i' or op == '-insert':
                self.flag_insert = True

            elif op == '-s' or op == '-start':
                self.start_id = value

            elif op == '-e' or op == '-end':
                self.stop_id = value

            elif op == '-a' or op == '-auto':
                self.auto = True
                #self.flag_insert = True

            elif op == '-r' or op == '-retry':
                self.flag_insert = True
                self.conn()
                self.retry_errorurl()
                sys.exit()

            elif op == '-h' or op == '-help':
                self.usage()
                sys.exit()
            elif op == '-p' or op == '-proxies':
                self.proxies = {
                    'https':value
                }
        #展示说明
        if len(sys.argv) == 1:
            self.usage()
            sys.exit()
        if self.flag_insert == False:
            self.flag_retry = False

        #链接数据库
        self.conn()
        if self.auto:
            self.get_last()

        #主程序
        self.main()

    #销毁
    def __del__(self):
        try:
            #关闭数据库
            self.CONN.close()
        except:
            pass

    #默认配置
    def config(self):
        #待insert数据
        self.insert_list = []
        #遍历linkid
        self.sl = '0123456789abcdefghijklmnopqrstuvwxyz'
        #获取sl的字典列表dl
        self.relist()
        #表结构
        self.column = ['id', 'linkid', 'director', 'director_url', 'studio',
        'studio_url', 'label', 'label_url', 'series', 'series_url', 'image_len',
        'genre', 'len', 'stars', 'av_id', 'title', 'bigimage', 'release_date']
        #表结构str
        self.column_str = ",".join(self.column)
        #插入阈值
        self.insert_threshold = 20
        #用于重试失败阈值
        self.retry_counter = 0
        #重试阈值
        self.retry_threshold = 5

        #主函数延时
        self.main_sleep = 1
        #更新flag
        self.last_flag = False

        #是否插入数据库
        self.flag_insert = False
        #是否重试
        self.flag_retry = True

        #是否启用data_check()
        self.flag_check = False

        #开始id
        self.start_id = '0000'
        #结束id
        self.stop_id = 'zzzz'
        #自动获取start stop
        self.auto = False

        #主表
        self.main_table = 'av_list'
        #重试表
        self.retry_table = 'av_error_linkid'

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

        #创建会话对象
        self.s = requests.Session()
        #超时时间
        self.s.timeout = 3
        #代理
        # self.s.proxies = {
        #     'https':'https://127.0.0.1:1080'
        # }
    #mysql conn
    def conn(self):
        #如果正式插入那么链接数据库
        if self.flag_insert:
            try:
                #链接sqlite
                self.CONN = sqlite3.connect(self.sqlite_file)
                self.CUR = self.CONN.cursor()
            except:
                print('connect database fail.')
                self.usage()
                sys.exit()
            try:
                self.CUR.execute('select count(1) from ' + self.main_table)
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
                ); '''.replace("av_list", self.main_table))
            try:
                self.CUR.execute('select count(1) from ' + self.retry_table)
            except:
                self.CUR.execute('''
                CREATE TABLE "av_error_linkid" (
                "linkid"  TEXT(4) NOT NULL,
                "status_code"  INTEGER,
                "datetime"  TEXT(50),
                PRIMARY KEY ("linkid")
                ); '''.replace("av_error_linkid", self.retry_table))

    #写出命令行格式
    def usage(self):
        print('抓取来自{}的信息，并插入数据库，id区间为0000-zzzz'.format(self.site))
        print(sys.argv[0] + " -i -s 0000 -e 0100\n")
        print('抓取来自{}的信息，不进行存储操作'.format(self.site))
        print(sys.argv[0] + " -s 0000 -e 0100\n")
        print('接着上次抓取并存入数据库')
        print(sys.argv[0] + " -a -i\n\n")
        print('-h(-help):使用说明')
        print('-i(-insert):插入数据库')
        print('-s(-start):开始id(0000,1ddd,36wq)')
        print('-e(-end):结束id(0000,1ddd,36wq)')
        print('-a(-auto):获取当前最新的一个id和网站最新的一个id，补全新增数据')
        print('-p(-proxies):使用指定的https代理服务器或SOCKS5代理服务器。例如：-p https://127.0.0.1:1080,-p socks5://127.0.0.1:52772')

    #主函数，抓取页面内信息
    def main(self):
        if self.flag_check:
            nowlist = self.linkid_list
        else:
            nowlist = self.get_linkid()

        for item in nowlist:
            url = self.movie_url+item
            time.sleep(self.main_sleep)
            try:
                res = self.s.get(url)
                if res.status_code != 200:
                    self.insert_retry((item, res.status_code))
                    print(url, res.status_code)
                    continue
            except:
                print(url, 'requests.get error')
                #超过一定时间就退出
                if time.time() > 1520632800:
                    exit()
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
            id = self.linkid2id(item)
            #输出当前进度
            print(data[12].ljust(30), data[15].ljust(11), item.ljust(5), id)

            if self.flag_insert:
                self.insert_list.append(
                    "'{0}','{1}','{2}'".format(id, item, "','".join(data))
                )
                #存储数据
                if self.insert_list.__len__() == self.insert_threshold:
                    self.insert_mysql()

    #获取最后一次的id
    def get_last(self):
        sql = "SELECT linkid FROM {0} ORDER BY linkid DESC LIMIT 0,1".format(self.main_table)
        self.CUR.execute(sql)
        res = self.CUR.fetchall()
        self.start_id = res[0][0]
        try:
            response = self.s.get(self.site_url)
        except:
            print('访问超时')
            exit()
        html = etree.HTML(response.text)
        self.stop_id = html.xpath('//*[@id="waterfall"]/div[1]/a')[0].attrib.get('href')[-4:]
        print('database start:{0},website end:{1}'.format(self.start_id, self.stop_id))
    
    #插入重试表
    def insert_retry(self, data):
        if self.flag_insert:
            self.CUR.execute("REPLACE INTO {0}(linkid, status_code, datetime)VALUES('{1[0]}', {1[1]}, '{2}');"
                .format(
                    self.retry_table,
                    data,
                    time.strftime(
                        "%Y-%m-%d %H:%M:%S",
                        time.localtime()
                    )
                )
            )
            self.CONN.commit()

    #遍历urlid
    def get_linkid(self):
        for i1 in self.sl:
            for i2 in self.sl:
                for i3 in self.sl:
                    for i4 in self.sl:
                        tmp = i1 + i2 + i3 + i4
                        if tmp > self.stop_id:
                            print('start:{0} end:{1} done!'.format(self.start_id, self.stop_id))
                            #插入剩余的数据
                            self.insert_mysql()
                            #重试错误数据
                            self.retry_errorurl()
                            exit()
                        if self.start_id < tmp:
                            yield tmp
                        else:
                            continue
    #由urlid获取排序自增id
    def linkid2id(self, item):
        return self.dl[item[3]] + self.dl[item[2]]*36 + self.dl[item[1]]*1296 + self.dl[item[0]]*46656

    #插入数据库
    def insert_mysql(self):
        if self.insert_list.__len__() == 0:
            return

        if self.flag_insert == True:
            self.replace_sql(self.main_table, self.column_str, "),(".join(self.insert_list))

        print('rows:', self.insert_list.__len__(), 'retry_counter:', self.retry_counter)
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
        self.CUR.execute("SELECT * FROM {0} WHERE status_code<>'404' ORDER BY linkid;".format(self.retry_table))
        res = self.CUR.fetchall()
        reslen = res.__len__()
        if reslen == 0:
            return
        print('retry error url count:', reslen)

        dellist = []
        update_list = []

        for item in res:
            reslen -= 1

            #统一更新表，提高效率
            if len(update_list) == 20:
                time_now = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
                self.CUR.execute("REPLACE INTO {0}(linkid, status_code, datetime)VALUES({1});".format(self.retry_table, "),(".join(["'{0[0]}',{0[1]},'{1}'".format(x, time_now) for x in update_list]) ))
                self.CONN.commit()
                update_list = []
                print('some status_code update done.')

            url = self.movie_url + item[0]
            try:
                response = self.s.get(url)
                html = etree.HTML(response.text)
            except:
                # 重写重试记录
                if response.status_code == 404:
                    update_list.append((item[0], 404))
                print(reslen, item[0], 'fail_1', response.status_code)
                continue

            if response.status_code != 200:
                # 重写重试记录
                update_list.append((item[0], response.status_code))
                print(reslen, item[0], 'fail_2', response.status_code)
                continue
            print(reslen, item[0], 'success')
            data = self.movie_page_data(html)
            id = self.linkid2id(item[0])
            self.insert_list.append("'{0}','{1}','{2}'".format(id, item[0], "','".join(data)))
            dellist.append(item[0])

            #存储数据
            if len(self.insert_list) == self.insert_threshold:
                #插入数据
                print(self.insert_threshold, 'insert.')
                self.replace_sql(self.main_table, self.column_str, "),(".join(self.insert_list))
                if dellist != []:
                    self.CUR.execute('DELETE FROM {0} WHERE {1};'.format(self.retry_table, ' OR '.join([" linkid='{0}' ".format(x) for x in dellist])))
                    self.CONN.commit()
                    dellist = []
        #插入数据
        if len(self.insert_list) != 0:
            self.replace_sql(self.main_table, self.column_str, "),(".join(self.insert_list))
        #删除数据
        if len(dellist) != 0:
            self.CUR.execute('DELETE FROM {0} WHERE {1};'.format(self.retry_table, ' OR '.join([" linkid='{0}' ".format(x) for x in dellist])))
            self.CONN.commit()
        #更新数据
        if len(update_list) != 0:
            time_now = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
            self.CUR.execute("REPLACE INTO {0}(linkid, status_code, datetime)VALUES({1});".format(self.retry_table, "),(".join(["'{0[0]}',{0[1]},'{1}'".format(x, time_now) for x in update_list]) ))
            self.CONN.commit()

    #获取idlist的字典
    def relist(self):
        self.dl = {}
        for item in range(self.sl.__len__()):
            self.dl[self.sl[item]] = item

    def movie_page_data(self, html):
        data = ['' for x in range(16)]
        #番号
        try:
            data[12] = html.xpath('/html/body/div[2]/div[1]/div[2]/p[1]/span[2]/text()')[0]
        except:
            return data
        #获取：导演、制作商、发行商、系列
        info = html.xpath('/html/body/div[2]/div[1]/div[2]/p/a')
        for i in info:
            if i.text == None:
                continue
            if self.director in i.attrib.get('href'):
                #导演
                data[0] = i.text.replace("'", '"')
                data[1] = i.attrib.get('href').replace(self.director, '')
            elif self.studio in i.attrib.get('href'):
                #制作商
                data[2] = i.text.replace("'", '"')
                data[3] = i.attrib.get('href').replace(self.studio, '')
            elif self.label in i.attrib.get('href'):
                #发行商
                data[4] = i.text.replace("'", '"')
                data[5] = i.attrib.get('href').replace(self.label, '')
            elif self.series in i.attrib.get('href'):
                #系列
                data[6] = i.text.replace("'", '"')
                data[7] = i.attrib.get('href').replace(self.series, '')

        #图片个数image_len
        data[8] = str(html.xpath('//*[@id="sample-waterfall"]/a').__len__())
        #获取类别列表genre
        data[9] = '|'.join(html.xpath('/html/body/div[2]/div[1]/div[2]/p/span/a/text()')).replace("'", '"')
        #时长len
        tmp = html.xpath('/html/body/div[2]/div[1]/div[2]/p[3]/text()')
        if tmp.__len__() != 0 and '分钟' in tmp[0]:
            data[10] = tmp[0].replace('分钟', '').strip()
        else:
            data[10] = '0'
        #演员stars
        data[11] = '|'.join(html.xpath('//*[@id="avatar-waterfall"]/a/span/text()')).replace("'", '"')

        #接取除了番号的标题
        data[13] = html.xpath('/html/body/div[2]/h3/text()')[0][data[12].__len__()+1:].replace("'", '"')
        #封面 截取域名之后的部分
        data[14] = '/' + html.xpath('/html/body/div[2]/div[1]/div[1]/a/img/@src')[0].split('/',5)[5]
        #发行时间
        data[15] = html.xpath('/html/body/div[2]/div[1]/div[2]/p[2]/text()')[0].strip()
        return data
    #检查被遗漏的页面，并插入数据库
    #按照linkid的顺序检查漏掉的番号，并不是从重试表检索
    def data_check(self):
        self.CUR.execute("SELECT linkid FROM {0} WHERE 1 ORDER BY linkid;".format(self.main_table))
        res = self.CUR.fetchall()
        
        res_index = 0
        res_list = [x[0] for x in res]
        res_min = res_list[0]
        res_max = res_list[res.__len__()-1]
        miss_list = []

        for i1 in self.sl:
            for i2 in self.sl:
                for i3 in self.sl:
                    for i4 in self.sl:
                        tmp = i1+i2+i3+i4
                        if tmp < res_min:
                            continue
                        if tmp > res_max:
                            break

                        if tmp == res_list[res_index]:
                            res_index += 1
                            continue
                        else:
                            miss_list.append(tmp)
                            continue

        print('miss count:', miss_list.__len__())
        self.CUR.execute('DELETE FROM "{0}";'.format(self.retry_table))
        self.CONN.commit()
        if miss_list.__len__() != 0:
            for item in miss_list:
                self.CUR.execute('INSERT INTO "{0}" ("linkid") VALUES ("{1}");'.format(self.retry_table, item))
            self.CONN.commit()
        else:
            print("miss_linkid no fond")
            return

        #重试错误链接并插入数据库
        self.CUR.execute('SELECT linkid FROM "{0}" ORDER BY linkid;'.format(self.retry_table))
        res = self.CUR.fetchall()
        self.linkid_list = [x[0] for x in res]
        self.flag_check = True
        self.main()
        #插入剩余的数据
        self.insert_mysql()
    #测试单个页面
    def test_page(self, linkid):
        url = self.movie_url+linkid
        res = self.s.get(url).text
        #解析页面内容
        data = self.movie_page_data(etree.HTML(res))
        print(data)

    #获取所有类别
    def replace_genre(self):
        html = etree.HTML(self.s.get(self.genre_url).text)
        insert_list = []
        h4 = html.xpath('/html/body/div[2]/h4/text()')
        div = html.xpath('/html/body/div[2]/div')
        for item in range(div.__len__()):
            g_title = h4[item]
            a = div[item].xpath('a')
            for item2 in a:
                g_name = item2.text.replace('・','')
                g_id = item2.attrib.get('href')[25:]
                insert_list.append("'{0}','{1}','{2}'".format(g_id,g_name,g_title))
        sql = "REPLACE INTO avmo_genre (g_id,g_name,g_title)VALUES({0});".format("),(".join(insert_list))
        self.CUR.execute(sql)
        self.CONN.commit()

if __name__ == '__main__':
    avmo()
