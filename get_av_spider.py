import sys
import time
import getopt
import requests
import sqlite3
import pymysql
from lxml import etree
 
class avmo:
 
    def __init__(self):
        #初始化
        self.config()
        try:
            opts, args = getopt.getopt(sys.argv[1:], "his:e:mc", ['help','insert','start','end','mysql','check'])
        except:
            self.usage()
            sys.exit()
        self.flag_insert = False
        self.flag_retry = True
        self.flag_check = False
        self.use_list = False
        self.sqlite_file = 'avmo.db'
        self.start_id = '0000'
        self.stop_id = 'zzzz'
        for op, value in opts:
            if op == '-i' or op == '-insert':
                self.flag_insert = True
            elif op == '-s' or op == '-start':
                self.start_id = value
            elif op == '-e' or op == '-end':
                self.stop_id = value
            elif op == '-m' or op == '-mysql':
                self.sqlite_file = ''
            elif op == '-c' or op == '-check':
                self.flag_check = True
                self.flag_insert = True
                self.use_list = True
            elif op == '-h' or op == '-help':
                self.usage()
                sys.exit()
        if self.flag_insert == False:
            self.flag_retry = False
        
        #链接数据库
        self.conn()

        if self.flag_check:
            #检测遗漏项
            self.data_check()
        else:
            #主程序
            self.main()
         
        #重试失败地址
        # self.retry_errorurl()
        #测试单个页面
        # self.test_page('5qw0')
 
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
        self.column=[
        'id',
        'linkid',
        'director',
        'director_url',
        'studio',
        'studio_url',
        'label',
        'label_url',
        'series',
        'series_url',
        'image_len',
        'genre',
        'len',
        'stars',
        'av_id',
        'title',
        'bigimage',
        'release_date']
        #表结构str
        self.column_str = ",".join(self.column)
        #插入阈值
        self.insert_threshold = 30
        #用于重试失败阈值
        self.retry_counter = 0
        #重试阈值
        self.retry_threshold = 5
        #超时时间
        self.timeout = 10
        
        #sqlite数据库
        self.sqlite_file = ''
        #主表
        self.main_table = 'av_list'
        #重试表
        self.retry_table = 'av_error_linkid'
        #遗漏记录表
        self.miss_table = 'av_miss_linkid'
        #站点url
        site_url = 'https://avmo.pw/cn'
        #番号主页url
        self.movie_url = site_url+'/movie/'
        #导演 制作 发行 系列
        self.director = site_url+'/director'
        self.studio = site_url+'/studio'
        self.label = site_url+'/label'
        self.series = site_url+'/series'
    
    #mysql conn
    def conn(self):
        #如果正式插入那么链接数据库
        if self.flag_insert:
            try:
                if self.sqlite_file=='':
                    #链接mysql
                    self.CONN = pymysql.connect(
                        host = '127.0.0.1',
                        port = 3306,
                        user = 'root',
                        passwd = 'root',
                        db = 'avmopw',
                        charset = 'utf8'
                    )
                    self.CUR = self.CONN.cursor()
                else:
                    #链接sqlite
                    self.CONN = sqlite3.connect(self.sqlite_file)
                    self.CUR = self.CONN.cursor()
            except:
                print('connect database fail.')
                self.usage()
                sys.exit()
            if self.sqlite_file!='':
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
                        );
                    '''.replace("av_list",self.main_table))
                try:
                    self.CUR.execute('select count(1) from ' + self.retry_table)
                except:
                    self.CUR.execute('''
                    CREATE TABLE "av_error_linkid" (
                    "id"  INTEGER PRIMARY KEY AUTOINCREMENT,
                    "linkid"  TEXT(4) NOT NULL,
                    "status_code"  INTEGER
                    );
                    '''.replace("av_error_linkid",self.retry_table))
                if self.flag_check:
                    try:
                        self.CUR.execute('select count(1) from ' + self.miss_table)
                    except:
                        self.CUR.execute('''
                        CREATE TABLE "av_miss_linkid" (
                        "id"  INTEGER PRIMARY KEY AUTOINCREMENT,
                        "linkid"  TEXT(4) NOT NULL
                        );
                        '''.replace("av_miss_linkid",self.miss_table))
    #写出命令行格式
    def usage(self):
        print(sys.argv[0] + ' -i -m -s 0000 -e zzzz')
        print(sys.argv[0] + ' -s 1000 -e 2000')
        print('-h(-help):Show usage')
        print('-i(-insert):Insert database')
        print('-s(-start):Start linkid')
        print('-e(-end):End linkid')
        print('-m(-mysql):use mysql')
    
    #检查被遗漏的页面，并插入数据库
    def data_check(self):
        self.CUR.execute("SELECT linkid FROM av_list WHERE 1 ORDER BY linkid;")
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

        print('miss count:',miss_list.__len__())
        self.CUR.execute('DELETE FROM "main"."{0}";'.format(self.miss_table))
        self.CONN.commit()
        if miss_list.__len__()!=0:
            for item in miss_list:
                self.CUR.execute('INSERT INTO "main"."{0}" ("linkid") VALUES ("{1}");'.format(self.miss_table,item))
            self.CONN.commit()
        else:
            print("miss_linkid no fond")
            return
        
        #重试错误链接并插入数据库
        self.CUR.execute('SELECT linkid FROM "main"."{0}" ORDER BY linkid;'.format(self.miss_table))
        res = self.CUR.fetchall()
        self.linkid_list = [x[0] for x in res]
        self.main()
    #测试单个页面
    def test_page(self,linkid):
        url = self.movie_url+linkid
        res = requests.get(url,timeout=self.timeout).text
        #解析页面内容
        data = self.movie_page_data(etree.HTML(res))
        print(data)
 
    #插入重试表
    def insert_retry(self,data):
        if self.flag_insert:
            if self.flag_check:
                self.CUR.execute('UPDATE "main"."{0}" SET "linkid"="{1[0]}", "status_code"="{1[1]}" WHERE ("id" IS "{1[0]}");'.format(self.miss_table,data))
            else:
                self.CUR.execute("INSERT INTO {0} (linkid,status_code)VALUES('{1[0]}','{1[1]}');".format(self.retry_table,data))
            self.CONN.commit()
    
    #主函数，抓取页面内信息
    def main(self):
        if self.use_list:
            nowlist = self.linkid_list
        else:
            nowlist = self.get_linkid()
        
        for item in nowlist:
            url = self.movie_url+item
            time.sleep(3)
            try:
                res = requests.get(url, timeout = self.timeout)
                if res.status_code!=200:
                    self.insert_retry((item,res.status_code))
                    print(url,res.status_code)
                    continue
            except:
                print(url,'requests.get error')
                self.insert_retry((item,777))
                continue
            
            try:
                html=etree.HTML(res.text)
            except:
                print(url,'etree.HTML error')
                self.insert_retry((item,888))
                continue
            
            #解析页面内容
            data=self.movie_page_data(html)
            #从linkid获取id
            id=self.linkid2id(item)
            #输出当前进度
            print(data[12].ljust(16),data[15].ljust(11),item.ljust(5),id)
            
            if self.flag_insert:
                self.insert_list.append(
                    "'{0}','{1}','{2}'".format(id, item, "','".join(data))
                )
                #存储数据
                if self.insert_list.__len__() == self.insert_threshold:
                    self.insert_mysql()
 
    #遍历urlid
    def get_linkid(self):

        for i1 in self.sl:
            for i2 in self.sl:
                for i3 in self.sl:
                    for i4 in self.sl:
                        tmp = i1+i2+i3+i4
                        if tmp > self.stop_id:
                            print('start:{0} end:{1} done!'.format(self.start_id,self.stop_id))
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
    def linkid2id(self,item):
        return self.dl[item[3]] + self.dl[item[2]]*36 + self.dl[item[1]]*1296 + self.dl[item[0]]*46656
 
    #插入数据库
    def insert_mysql(self):
        if self.insert_list.__len__()==0:
            return
 
        if self.flag_insert!=False:
            sql="REPLACE INTO {2}({0})VALUES({1});".format(self.column_str,"),(".join(self.insert_list),self.main_table)
            self.CUR.execute(sql)
            self.CONN.commit()
 
        print('insert rows:',self.insert_list.__len__(),'retry_counter:',self.retry_counter)
        self.insert_list=[]
        self.retry_counter+=1
 
        if self.flag_retry:
            #重试失败地址
            if self.retry_counter>=self.retry_threshold:
                self.retry_counter=0
                self.retry_errorurl()
 
    #重试
    def retry_errorurl(self):
        sql = "SELECT linkid FROM {0} WHERE status_code<>'404';".format(self.retry_table)
        self.CUR.execute(sql)
        res = self.CUR.fetchall()
        reslen = res.__len__()
        if reslen == 0:
            return
        print('retry error url:',reslen)
 
        dellist = []
        for item in res:
            reslen -= 1
            url = self.movie_url + item[0]
            try:
                r=requests.get(url,timeout = self.timeout)
                html = etree.HTML(r.text)
            except:
                print(reslen,url,'fail')
                continue
             
            if r.status_code != 200:
                print(reslen, item[0], r.status_code)
                continue
 
            print(reslen,item[0])
            data = self.movie_page_data(html)
            id = self.linkid2id(item[0])
            self.insert_list.append(
                "'{0}','{1}','{2}'".format(id,item[0],"','".join(data))
            )
            dellist.append(item[0])
 
        self.insert_mysql()
        if dellist != []:
            self.CUR.execute('DELETE FROM {0} WHERE {1};'.format(self.retry_table ,' OR '.join([" linkid='{0}' ".format(x) for x in dellist])))
            self.CONN.commit()
 
    #获取idlist的字典
    def relist(self):
        self.dl={}
        for i in range(self.sl.__len__()):
            self.dl[self.sl[i]]=i
 
    def movie_page_data(self,html):
        data = ['' for x in range(16)]
        #获取：导演、制作商、发行商、系列
        info = html.xpath('/html/body/div[2]/div[1]/div[2]/p/a')
        for i in info:
            if i.text == None:
                continue
            if i.attrib.get('href')[:27] == self.director:
                #导演
                data[0] = i.text.replace("'","\\'")
                data[1] = i.attrib.get('href')[28:]
                 
            elif i.attrib.get('href')[:25] == self.studio:
                #制作商
                data[2] = i.text.replace("'","\\'")
                data[3] = i.attrib.get('href')[26:]
                 
            elif i.attrib.get('href')[:24] == self.label:
                #发行商
                data[4] = i.text.replace("'","\\'")
                data[5] = i.attrib.get('href')[25:]
                 
            elif i.attrib.get('href')[:25] == self.series:
                #系列
                data[6] = i.text.replace("'","\\'")
                data[7] = i.attrib.get('href')[26:]
                 
        #图片个数image_len
        data[8] = str(html.xpath('//*[@id="sample-waterfall"]/a').__len__())
        #获取类别列表genre
        data[9] = '|'.join(html.xpath('/html/body/div[2]/div[1]/div[2]/p/span/a/text()')).replace("'","\\'")
        #时长len
        tmp = html.xpath('/html/body/div[2]/div[1]/div[2]/p[3]/text()')
        if tmp.__len__() != 0:
            data[10] = tmp[0].replace('分钟','').strip()
        else:
            data[10] = '0'
        #演员stars
        data[11] = '|'.join(html.xpath('//*[@id="avatar-waterfall"]/a/span/text()')).replace("'","\\'")
        #番号
        data[12] = html.xpath('/html/body/div[2]/div[1]/div[2]/p[1]/span[2]/text()')[0]
        #接取除了番号的标题
        data[13] = html.xpath('/html/body/div[2]/h3/text()')[0][data[12].__len__()+1:].replace("'","\\'")
        #封面 截取video之后的部分
        data[14] = html.xpath('/html/body/div[2]/div[1]/div[1]/a/img/@src')[0][37:]
        #发行时间
        data[15] = html.xpath('/html/body/div[2]/div[1]/div[2]/p[2]/text()')[0].strip()
        return data
    
    #获取所有类别
    def replace_genre(self):
        html = etree.HTML(requests.get('https://avmo.pw/cn/genre').text)
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
    
    #获取最后一次的id
    def get_last(self,where_id = ''):
        if where_id == '':
            sql="SELECT linkid FROM {0} ORDER BY linkid DESC LIMIT 0,1;".format(self.main_table)
        else:
            sql="SELECT linkid FROM {0} WHERE linkid<'{1}' ORDER BY linkid DESC LIMIT 0,1;".format(self.main_table, where_id)
        self.CUR.execute(sql)
        res = self.CUR.fetchall()
         
        self.stop_id = 'zzzz'
        if res[0][0] == '':
            self.start_id = '0000'
        else:
            self.start_id = res[0][0]
if __name__ == '__main__':
    avmo()
