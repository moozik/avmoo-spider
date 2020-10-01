#!/usr/bin/env python3
#-*- coding:utf-8 -*-
import sys
import time
import getopt
import requests
import sqlite3
import math
import re
import os
import json
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
https://pics.javcdn.pw/cover/3tya_b.jpg
https://pics.javcdn.pw/cover/{{linkid}}_b.jpg

'''

class avmo:
    def __init__(self):
        
        #================主要配置================
        #其他配置初始化
        self.config()
        self.requestInit()
            
        #指定目录
        self.av_dir = 'D:/sku/avtype1/'

        #json地址
        self.json_file = 'av_data.json'
        self.js_file = 'av_data.js'

        if not os.path.exists(self.json_file):
            with open(self.json_file, 'w') as f:
                f.write('[]')
        #================读取参数================
        try:
            opts, args = getopt.getopt(
                sys.argv[1:],
                "lu",
                ['list', 'update']
            )
        except:
            exit()

        opt_dict = {}
        for op, value in opts:
            opt_dict[op] = value

        if '-l' in opt_dict or '--list' in opt_dict:
            av_input = self.av_input(self.av_dir)
            for item in av_input:
                print(item)
            print('count:{}'.format(len(av_input)))
            count = len(set([x['avid'] for x in av_input]))
            print('avcount:{}'.format(count))

        if '-u' in opt_dict or '--update' in opt_dict:
            av_input = self.av_input(self.av_dir)
            #更新列表
            self.update_list(av_input)
    
    def av_input(self, av_dir):
        av_input = []
        #遍历视频文件
        for filename in self.dir_list(av_dir):
            this = {
                'file':filename,
                'newfile':'',
                'error':'',
                'avid':''
            }
            #格式化名称
            # if not re.match(self.format_reg, filename):
                # if filename in av_input:
                #     print('{} is exist'.format(filename))
                #     continue
                # av_input.append(filename)
                # av_input.append(this)
            res = re.match(self.ori_reg, filename)
            if None == res:
                this['error'] = '不能识别'
                av_input.append(this)
                continue
            
            if res.group(2) == None:
                new_filename = res.group(1).upper() + '.' + res.group(4)
            else:
                new_filename = res.group(1).upper() + res.group(2) + '.' + res.group(4)

            this['newfile'] = new_filename
            # print('rename:{} to {}'.format(av_dir + filename, av_dir + new_filename))
            if new_filename != filename:
                os.rename(av_dir + filename, av_dir + new_filename)
            # if new_filename in av_input:
            #     print('{} is exist'.format(filename))
            #     continue

            res = re.match(self.format_reg, new_filename)
            if res.group(1) == None:
                this['error']='not match'

            this['avid'] = res.group(1)

            av_input.append(this)

        return av_input

    #遍历指定目录
    def dir_list(self, path, reg = '.*\.(avi|mp4|mkv)$'):
        for root ,dirs, files in os.walk(path):
            for filename in files:
                if re.match(reg, filename):
                    yield filename

    #更新
    def update_list(self, av_input):
        #读取库
        av_data = []
        with open(self.json_file, 'r') as f:
            av_data = json.loads(f.read())
        # print(av_data)
        av_data_exist = [x['avid'] for x in av_data]
        for av_obj in av_input:
            if av_obj['avid'] == '':
                print('{}:'.format(av_obj['avid'], av_obj['error']))
                continue
            avid = av_obj['avid']
            avfile = av_obj['newfile']
            if avid in av_data_exist:
                print('{} 存在.'.format(avid))
                #更新avfile字段
                for index in range(len(av_data)):
                    if av_data[index]['avid'] == avid:
                        if 'avfile' not in av_data[index]:
                            av_data[index]['avfile'] = avfile
                            print('更新avfile字段:' + av_data[index]['avfile'])
                        break
                continue
            
            print('{} 获取中.....'.format(avid))
            # if avid in av_data_exist:
            #     flag = False
            #     for i in range(len(av_data)):
            #         if av_data[i]['avid'] == avid:
            #             if 'avlink' in av_data[i]:
            #                 avlink = av_data[i]['avlink']
            #             else:
            #                 flag = True
            #                 print(av_data[i])
            #             break
            #     if flag:
            #         print('avid no found')
            #         continue
            # else:
            avlink = self.avid2link(avid)
            print(avlink)
            if avlink == False:
                print('{} 没找到'.format(avid))
                av_data.append({
                    "avid": avid,
                    "avfile": avfile,
                })
                av_data_exist.append(avid)
                continue
            
            #使用跳板加速
            # response = self.s.get('https://moozik.cn/old_mousehole.php?url=' + avlink)
            response = self.s.get(avlink)
            
            # response = self.s.get(avlink)
            data = self.movie_page_data(etree.HTML(response.text))
            data['avlink'] = avlink
            data['avfile'] = avfile
            
            av_data.append(data)
            av_data_exist.append(avid)
        #存储到json文件
        with open(self.json_file, 'w') as f:
            f.write(json.dumps(av_data))
        #存储到js文件
        with open(self.js_file, 'w') as fw:
            with open(self.json_file, 'r') as fr:
                fw.write('window.av_data = ' + fr.read() + ';')
    def avid2link(self, avid):
        url = 'https://avmoo.host/cn/search/' + avid
        # url = 'https://moozik.cn/mousehole/https/avmoo.host/cn/search/' + avid
        response = self.s.get(url)
        html = etree.HTML(response.text)
        for item in html.xpath('//*[@id="waterfall"]/div'):
            pageavid = item.xpath('a/div[2]/span/date[1]/text()')
            if len(pageavid) > 0 and pageavid[0] == avid:
                print(item.xpath('a/@href')[0])
                return item.xpath('a/@href')[0]
        return False
    
    def requestInit(self):
        #创建会话对象
        self.s = requests.Session()
        #超时时间
        self.s.timeout = 3
        self.s.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/67.0.3396.99 Safari/537.36'
        }
        #代理
        self.s.proxies = {
            #'https':'http://127.0.0.1:1080'
        }
    
    #默认配置
    def config(self):

        # self.format_reg = '^([0-9A-Z]+-\d+)((-|_)\d)?\.[^\.]+$'
        self.format_reg = '^([0-9A-Z]+-\d+)((-|_)\d)?\.[^\.]+$'
        self.ori_reg = '(?!@)([0-9a-zA-Z]{3,7}-?\d{3,4})((-|_)\d)?\.(mp4|avi|mkv)$'

        self.site = 'avmoo.host'
        #站点url
        self.site_url = 'https://{0}/cn'.format(self.site)

        #番号主页url
        self.movie_url = self.site_url+'/movie/'
        #导演 制作 发行 系列
        self.director_url = self.get_url('cn','director','')
        self.studio_url = self.get_url('cn','studio','')
        self.label_url = self.get_url('cn','label','')
        self.series_url = self.get_url('cn', 'series', '')
        
        #主函数延时
        self.main_sleep = 1

    def get_url(self, country, pagetype, linkid):
        # return self.site_url + '/' + country + 
        return '{}/{}/{}/{}'.format(self.site_url, country, pagetype, linkid)

    #sqlite conn
    def conn(self):
        try:
            #链接sqlite
            self.CONN = sqlite3.connect(self.sqlite_file, check_same_thread=False)
            self.CUR = self.CONN.cursor()
        except:
            print('connect database fail.')
            sys.exit()

    def movie_page_data(self, html):
        data = {
            'director':'',
            'studio':'',
            'label':'',
            'series':''
        }
        #番号
        try:
            data['avid'] = html.xpath('/html/body/div[2]/div[1]/div[2]/p[1]/span[2]/text()')[0]
        except:
            return data
        #获取：导演、制作商、发行商、系列
        right_info = html.xpath('/html/body/div[2]/div[1]/div[2]/p/a')
        for i in right_info:
            if i.text == None:
                continue
            tmp_text = i.text.replace("'", '"')
            tmp_href = i.attrib.get('href')

            if self.director_url in tmp_href:
                #导演
                data['director'] = tmp_text
                # data[2] = tmp_href.replace(self.director_url, '')
            elif self.studio_url in tmp_href:
                #制作商
                data['studio'] = tmp_text
                # data[4] = tmp_href.replace(self.studio_url, '')
            elif self.label_url in tmp_href:
                #发行商
                data['label'] = tmp_text
                # data[6] = tmp_href.replace(self.label_url, '')
            elif self.series_url in tmp_href:
                #系列
                data['series'] = tmp_text
                # data[8] = tmp_href.replace(self.series_url, '')

        #获取类别列表genre 类别列表genre_url
        data['genre'] = '|'.join(html.xpath(
            '/html/body/div[2]/div[1]/div[2]/p/span/a/text()')).replace("'", '"')
        # genre_url_list = html.xpath(
        #     '/html/body/div[2]/div[1]/div[2]/p/span/a/@href')
        # if genre_url_list != None and len(genre_url_list) != 0:
        #     data['genre'] = '|' + '|'.join(
        #         [re.findall('([a-z0-9]+)$', x)[0] for x in genre_url_list])
        #演员stars
        data['stars'] = '|'.join(html.xpath(
            '//div[@id="avatar-waterfall"]/a/span/text()')).replace("'", '"')
        if data['stars'] != '':
            data['stars'] = '|' + data['stars']
        #stars_url
        # stars_url_list = html.xpath('//div[@id="avatar-waterfall"]/a/@href')
        # if stars_url_list != None and len(stars_url_list) != 0:
        #     data['stars'] = '|'.join([re.findall('([a-z0-9]+)$', x)[0] for x in stars_url_list])

        #图片个数image_len
        data['image_len'] = str(len(html.xpath('//div[@id="sample-waterfall"]/a')))
        #时长len
        lentext = html.xpath('/html/body/div[2]/div[1]/div[2]/p[3]/text()')
        if len(lentext) != 0 and '分钟' in lentext[0]:
            data['len'] = lentext[0].replace('分钟', '').strip()
        else:
            data['len'] = '0'

        #接取除了番号的标题
        data['title'] = html.xpath('/html/body/div[2]/h3/text()')[0]
        #封面 截取域名之后的部分
        data['bigimage'] = '/' + html.xpath('/html/body/div[2]/div[1]/div[1]/a/img/@src')[0].split('/',5)[5]
        #发行时间
        data['date'] = html.xpath('/html/body/div[2]/div[1]/div[2]/p[2]/text()')[0].strip()

        return data

if __name__ == '__main__':
    avmo()
