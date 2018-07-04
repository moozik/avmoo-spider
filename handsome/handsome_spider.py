import requests
import sqlite3
import re
from lxml import etree

'''
id:
网址：https://moozik.cn/links.html
头像：https://moozik.cn/usr/uploads/logo3.jpg
site_name：三暮成粥
site_title：生命就是音乐啤酒鲜花
index_title:独立思考与人云亦云
文章数量:123
友链数量：
'''
class handsome:
    def __init__(self):
        self.config()
        self.main_loop()
    
    def config(self):
        #allsite 待检查列表
        self.pre_site_list_wait = ['https://moozik.cn']
        #allsite 已扫描列表
        self.done_scan_list = []
        
        #普通网站insert
        self.site_insert = []
        #handsome insert
        self.handsome_insert = []
        #friend_dict
        self.friend_insert = []
        
        self.sqlite_file = 'handsome.db'
        self.main_table = 'handsome_site'
        self.friend_table = 'handsome_friend'
        self.conn()
        
        #创建会话对象
        self.s = requests.Session()
        self.s.headers['User-Agent'] = 'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/66.0.3359.181 Safari/537.36'
        #超时时间
        self.s.timeout = 5

    def main_loop(self):
        while True:
            if self.pre_site_list_wait == [] \
            and self.site_insert == [] \
            and self.handsome_insert == [] \
            and self.friend_insert == []:
                break
            print('NEW LOOP!========\n')
            # print('          pre_site_list_wait:', len(self.pre_site_list_wait))

            pre_site_list = []
            if self.pre_site_list_wait != []:
                pre_site_list = self.pre_site_list_wait
                self.pre_site_list_wait = []

            # print('          pre_site_list:', len(pre_site_list))
            for site in pre_site_list:
                if site[-1:] == '/':
                    site = site[:-1]
                #添加已扫描
                self.done_scan_list.append(site)
                # print('          done_scan_list:', len(self.done_scan_list))
                #检查是否为handsoem网站
                is_handsome = self.site_check(site)
                if is_handsome == 'error':
                    print('   SITE:', site.ljust(30) , '     ERROR!')
                    self.site_insert.append(
                        (site, 'error', 0)
                    )
                    continue
                elif is_handsome == False:
                    print('   SITE:',site)
                    try:
                        res = self.s.get(site)
                        title = re.findall(
                            '<title.*?>(.*?)</title>', res.text, re.S)[0]
                    except:
                        title = 'page_error'
                    self.site_insert.append(
                        (site, title, 0)
                    )
                elif is_handsome == True:
                    print('   SITE:',site.ljust(30) , ' IS HANDSOME!')
                    self.handsome_insert.append(self.site_handsome(site))
            
            #插入数据库
            '''
            print(self.site_insert)
            print(self.handsome_insert)
            print(self.friend_insert)
            '''
            sql_list = {}
            if len(self.site_insert) != 0:
                sql_list['site_insert'] = 'replace into {}(site,title,is_handsome) values("{})'.format(
                    self.main_table, '),("'.join(
                        ['{0[0]}","{0[1]}",{0[2]}'.format(x) for x in self.site_insert]))
                self.site_insert = []
            
            if len(self.handsome_insert) != 0:
                sql_list['handsome_insert'] = 'replace into {}(site,title,is_handsome,logo,friend_count)values("{})'.format(
                    self.main_table, '),("'.join(
                        ['{0[0]}","{0[1]}",{0[2]},"{0[3]}",{0[4]}'.format(x) for x in self.handsome_insert]))
                self.handsome_insert = []
            
            if len(self.friend_insert) != 0:
                sql_list['friend_insert'] = 'replace into {}(a_site,b_site)values("{}")'.format(
                    self.friend_table,'"),("'.join(
                        ['{0[0]}","{0[1]}'.format(x) for x in self.friend_insert]))
                self.friend_insert = []

            for name, val in sql_list.items():
                self.CUR.execute(val)
                self.CONN.commit()
                print('INSERT DB:{} ROWS:{}'.format(name, self.CUR.rowcount))
    #获取各种信息
    def site_handsome(self, site):
        index_text = self.s.get(site).text
        html = etree.HTML(index_text)
        title = html.xpath('//title/text()')[0]
        logo = html.xpath('//img[@class="img-full"]/@src')[0]
        
        links_text = self.s.get(site + '/links.html').text
        html = etree.HTML(links_text)
        friend_href = html.xpath('//div[@class="tab-content"]/ul/li/a/@href')
        friend_count = len(friend_href)
        print('      friend_count:{}'.format(friend_count))
        for friend in friend_href:
            if friend not in self.done_scan_list:
                self.pre_site_list_wait.append(friend)
            
            self.friend_insert.append(
                (site,friend)
            )
        return (site,title,1,logo,friend_count)
    #检查是否为handsome主题
    def site_check(self, site):
        url = site + '/usr/themes/handsome/assets/css/handsome.min.css'
        try:
            response = self.s.get(url)
            if response.status_code == 200:
                if '@charset "utf-8";' in  response.text:
                    response = self.s.get(site + '/links.html')
                    if response.status_code == 200:
                        return True
                    else:
                        return False
                else:
                    return False
            else:
                return False
        except:
            return 'error'
    def conn(self):
        try:
            #链接sqlite
            self.CONN = sqlite3.connect(self.sqlite_file)
            self.CUR = self.CONN.cursor()
        except:
            print('connect database fail.')
            exit()
        try:
            self.CUR.execute('select count(1) from ' + self.main_table)
        except:
            self.CUR.execute('''
            CREATE TABLE "table_name" (
            "id"  INTEGER NOT NULL,
            "site"  TEXT(100) NOT NULL,
            "is_handsome"  INTEGER,
            "title"  TEXT(500),
            "logo"  TEXT(500),
            "friend_count"  INTEGER,
            PRIMARY KEY ("id")
            ); '''.replace("table_name", self.main_table))
        try:
            self.CUR.execute('select count(1) from ' + self.friend_table)
        except:
            self.CUR.execute('''
            CREATE TABLE "table_name" (
            "a_id"  INTEGER,
            "b_id"  INTEGER,
            "site_a"  TEXT(300) NOT NULL,
            "site_b"  TEXT(300) NOT NULL,
            PRIMARY KEY ("a_site" ASC, "b_site" ASC)
            ); '''.replace("table_name", self.friend_table))

if __name__ == '__main__':
    handsome()
