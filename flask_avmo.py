#!/usr/bin/env python3
# -*- coding:utf-8 -*-
from flask import render_template
from flask import Flask
from flask import request
from flask import redirect
from flask import url_for
import sqlite3
import datetime
import time
import re
import os
import math
import binascii
import config
import spider_avmo
import _thread

app = Flask(__name__)
app.jinja_env.auto_reload = True
app.config['TEMPLATES_AUTO_RELOAD'] = True

# 每页展示的数量
PAGE_LIMIT = 30
#图片服务器，图片慢可以尝试换另一个
CDN_SITE = '//jp.netcdn.space'
CDN_SITE = '//pics.dmm.co.jp'
# 默认语言为中文
DEFAULT_LANGUAGE = 'cn'
# 缓存
SQL_CACHE = {}
# 缓存默认开启
IF_USE_CACHE = True
SPIDER_AVMO = spider_avmo.avmo()

#文件类型与判定
FILE_TAIL = {
    'mp4':"\.(mp4|mkv|flv|avi|rm|rmvb|mpg|mpeg|mpe|m1v|mov|3gp|m4v|m3p|wmv|wmp|wm|ts)$",
    'jpg':"\.(jpg|png|gif|jpeg|bmp|ico)$",
    'mp3':"\.(mp3|wav|wmv|mpa|mp2|ogg|m4a|aac)$",
    'torrent':"\.torrent$",
    'zip':"\.(zip|rar|gz|7z)$",
    'doc':"\.(xls|xlsx|doc|docx|ppt|pptx|csv|pdf|html|txt)$",
}

AV_FILE_REG = "[a-zA-Z]{3,5}-\d{3,4}"

@app.route('/')
@app.route('/page/<int:pagenum>')
@app.route('/search/<keyword>')
@app.route('/search/<keyword>/page/<int:pagenum>')
def index(keyword='', pagenum=1):
    if pagenum < 1:
        redirect(url_for('/'))
    limit_start = (pagenum - 1) * PAGE_LIMIT
    keyword = keyword.replace("'", '').replace('"', '').strip()

    where = []

    # 识别番号
    if re.match('^[a-zA-Z0-9 \-]{4,14}$', keyword):
        tmp = keyword.replace(' ', '-').upper()
        if '-' in tmp:
            return movie(tmp)
        else:
            where.append('av_list.av_id like "%{}%"'.format(tmp))
    # 搜索
    elif keyword != '':
        key_list = keyword.split(' ')

        for key_item in key_list:
            if key_item == '已发布':
                date = time.strftime("%Y-%m-%d", time.localtime())
                where.append('av_list.release_date <= "{}"'.format(date))
                continue

            if key_item == '有资源':
                where.append('av_extend.val is not null')
                continue

            if key_item == '收藏影片':
                sql = "SELECT val FROM av_like WHERE type='av_id'"
                data = querySql(sql)
                where.append('av_list.av_id in ("{}")'.format(
                    '","'.join([x['val'] for x in data])))
                continue

            where.append('''
            (av_list.title like "%{0}%" or
            av_list.av_id like "%{0}%" or
            av_list.director = "{0}" or
            av_list.studio = "{0}" or
            av_list.label like "%{0}%" or
            av_list.series like "%{0}%" or
            av_list.genre like "%{0}%" or
            av_list.stars like "%{0}%")'''.format(key_item))
    elif keyword == '':
        where = []

    result = selectAvList(column='av_list.*', av_list_where=where,
                          limit=(limit_start, PAGE_LIMIT))
    if keyword != '':
        page_root = '/{}/{}'.format('search', keyword)
    else:
        page_root = ''
    return render_template('index.html', data={'av_list': result[0]}, cdn=CDN_SITE, page=pagination(pagenum, result[1], page_root), keyword=keyword)


@app.route('/movie/<linkid>')
def movie(linkid=''):
    if linkid == '':
        return redirect(url_for('index'), 404)
    if '-' in linkid:
        where = ['av_list.av_id="{}"'.format(linkid.upper())]
    else:
        where = ['av_list.linkid="{}"'.format(linkid)]
    sql_arr = selectAvList(
        column='av_list.*', av_list_where=where, limit=(0, 1))

    if sql_arr[0] == []:
        return redirect(url_for('index'), 404)

    movie = sql_arr[0][0]
    # 系列
    if movie['genre']:
        movie['genre_list'] = movie['genre'].split('|')
    # 演员
    if movie['stars_url']:
        sql = 'select linkid,name,headimg from av_stars where linkid in ("{}")'.format(
            movie['stars_url'].strip('|').replace('|', '","'))
        stars_data = querySql(sql)
        movie['stars_data'] = stars_data
    # 图片
    img = []
    if movie['image_len'] != '0':
        count = int(movie['image_len'])
        imgurl = CDN_SITE + '/digital/video' + \
            movie['bigimage'].replace('pl.jpg', '')
        for i in range(1, count+1):
            img.append({
                'small': '{}-{}.jpg'.format(imgurl, i),
                'big': '{}jp-{}.jpg'.format(imgurl, i)
            })
    else:
        img = ''
    movie['imglist'] = img
    # 本地文件
    movie['movie_resource_list'] = selectExtendValue(
        'movie_res', movie['av_id'])
    return render_template('movie.html', data=movie, cdn=CDN_SITE)


@app.route('/director/<keyword>')
@app.route('/director/<keyword>/page/<int:pagenum>')
@app.route('/studio/<keyword>')
@app.route('/studio/<keyword>/page/<int:pagenum>')
@app.route('/label/<keyword>')
@app.route('/label/<keyword>/page/<int:pagenum>')
@app.route('/series/<keyword>')
@app.route('/series/<keyword>/page/<int:pagenum>')
@app.route('/genre/<keyword>')
@app.route('/genre/<keyword>/page/<int:pagenum>')
@app.route('/stars/<keyword>')
@app.route('/stars/<keyword>/page/<int:pagenum>')
def search(keyword='', pagenum=1):
    if pagenum < 1:
        return redirect(url_for('index'), 404)
    limit_start = (pagenum - 1) * PAGE_LIMIT

    function = request.path.split('/')[1]
    if function == 'director' or function == 'studio' or function == 'label' or function == 'series':
        where = ['av_list.{}_url="{}"'.format(function, keyword)]
    if function == 'genre':
        where = ['av_list.{} LIKE "%{}%"'.format(function, keyword)]
    if function == 'stars':
        where = ['av_list.stars_url LIKE "%{}%"'.format(keyword)]

    page_root = '/{}/{}'.format(function, keyword)
    result = selectAvList(column='av_list.*',
                          av_list_where=where, limit=(limit_start, PAGE_LIMIT))

    starsData = None
    if function == 'stars':
        starsData = querySql(
            'SELECT * FROM "av_stars" where linkid="{}";'.format(keyword))[0]
        # 计算年龄
        if starsData['birthday'] != '':
            sp = starsData['birthday'].split('-')
            birthdayData = datetime.date(int(sp[0]), int(sp[1]), int(sp[2]))
            starsData['age'] = math.ceil(
                (datetime.date.today() - birthdayData).days/365)
        keyword = starsData['name']

    if function != 'genre' and function != 'stars':
        keyword = ''

    return render_template('index.html', data={'av_list': result[0], 'av_stars': starsData}, cdn=CDN_SITE, page=pagination(pagenum, result[1], page_root), keyword=keyword)


@app.route('/genre')
def genre():
    result = querySql('select name,title from av_genre')
    data = {}
    for item in result:
        if item['title'] not in data:
            data[item['title']] = []
        data[item['title']].append(item)
    data = list(data.values())
    return render_template('genre.html', data=data, cdn=CDN_SITE)


@app.route('/like/add/<data_type>/<data_val>')
def like_add(data_type=None, data_val=None):
    if data_type != None and data_val != None:
        timetext = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        sqltext = 'REPLACE INTO av_like VALUES("{}", "{}", "{}")'.format(
            data_type, data_val, timetext)
        DB['CUR'].execute(sqltext)
        DB['CONN'].commit()
        return '已添加收藏'


@app.route('/like/del/<data_type>/<data_val>')
def like_del(data_type=None, data_val=None):
    if data_type != None and data_val != None:
        sqltext = 'DELETE FROM av_like WHERE type="{}" and val="{}"'.format(
            data_type, data_val)
        print(sqltext)
        DB['CUR'].execute(sqltext)
        DB['CONN'].commit()
        return '已删除收藏'


@app.route('/like/movie')
@app.route('/like/movie/page/<int:pagenum>')
def like_page(pagenum = 1):
    limit_start = (pagenum - 1) * PAGE_LIMIT
    result = selectAvList(column='*', limit=(limit_start, PAGE_LIMIT),
                          othertable=" JOIN av_like ON av_like.type='av_id' AND av_like.val = av_list.av_id ", order='av_like.time DESC')

    return render_template('index.html', data={'av_list': result[0]}, cdn=CDN_SITE, page=pagination(pagenum, result[1], '/like/movie'), keyword='收藏影片')

@app.route('/actresses')
@app.route('/actresses/page/<int:pagenum>')
def like_stars(pagenum = 1):
    limit_start = (pagenum - 1) * PAGE_LIMIT
    sqltext = 'select av_stars.*,count(distinct av_list.release_date) as movie_count,av_list.release_date from av_stars LEFT JOIN (select release_date,stars_url from av_list order by release_date desc)av_list on instr(av_list.stars_url, av_stars.linkid) > 0 group by av_stars.linkid order by av_list.release_date desc limit {},{}'.format(limit_start, PAGE_LIMIT)
    result = querySql(sqltext)
    
    res_count = querySql('SELECT COUNT(1) AS count FROM av_stars')
    return render_template('actresses.html', data=result, cdn=CDN_SITE, page=pagination(pagenum, res_count[0]['count'], "/actresses"))


@app.route('/action/scandisk')
def action_scandisk():
    if 'path_target' not in request.values or 'file_target' not in request.values:
        return render_template('scandisk.html')

    path_target = request.values['path_target']
    if not os.path.exists(path_target):
        return render_template('scandisk.html')

    file_target = request.values['file_target']
    reg = FILE_TAIL[file_target]
    av_file_res = []
    file_res = []
    extend_list = {}
    if file_target == "mp4":
        sqltext = 'select key,val from "av_extend" where extend_name="movie_res" and val not like "magnet%" and val not like "http%"'
        DB['CUR'].execute(sqltext)
        ret = DB['CUR'].fetchall()
        for row in ret:
            extend_list[row[0]] = row[1]
    for root,dirs,files in os.walk(path_target):
        for file in files:
            if re.search(reg, file):
                nowPath = os.path.join(root, file)
                if file_target != "mp4":
                    file_res.append(nowPath)
                    continue
                
                av_check = re.search(AV_FILE_REG, file)
                if not av_check:
                    file_res.append(nowPath)
                    continue
                #格式化avid
                av_id = av_check.group(0).upper()
                av_file_res.append({
                    'file_path':nowPath,
                    'av_id':av_id,
                    'exist':(av_id in extend_list and extend_list[av_id] == nowPath),
                })
    return render_template('scandisk.html', file_res=file_res, av_file_res=av_file_res, path_target=path_target, avmoo_url=config.getAvmooUrl())


@app.route('/action/catch/switch')
def action_catch_switch():
    global IF_USE_CACHE
    global SQL_CACHE
    if IF_USE_CACHE == True:
        IF_USE_CACHE = False
        SQL_CACHE = {}
        return '已关闭缓存'
    else:
        IF_USE_CACHE = True
        SQL_CACHE = {}
        return '已打开缓存'


@app.route('/action/explorer/<movie_path>')
def action_explorer(movie_path):
    # 打开指定路径
    os.system('explorer "{}"'.format(movie_path))
    return 'ok'


@app.route('/action/extend/insert/<extend_name>/<key>/<val>')
def action_extend_insert(extend_name, key, val):
    insertExtendValue(extend_name, key, val)
    return '扩展信息添加成功'


@app.route('/action/extend/delete/<extend_name>/<key>/<val>')
def action_extend_delete(extend_name, key, val):
    deleteExtendValue(extend_name, key, val)
    return '扩展信息删除成功'


@app.route('/action/download/star/<linkid>')
def action_download_star(linkid=''):
    global SPIDER_AVMO

    if linkid == 'all':
        star_list = querySql("select linkid from av_stars")
        _thread.start_new_thread(SPIDER_AVMO.spider_by_stars_list, ([x['linkid'] for x in star_list],))
        return '正在下载所有...'

    if not isLinkId(linkid):
        return 'id格式不正确'
    _thread.start_new_thread(SPIDER_AVMO.spider_by_stars, (linkid,))
    return '{},正在下载...'.format(linkid)


@app.route('/action/download/genre')
def action_download_genre():
    global SPIDER_AVMO
    _thread.start_new_thread(SPIDER_AVMO.genre_update, ())
    return '正在下载...'


@app.route('/action/delete/movie/<linkid>')
def action_delete_movie(linkid=''):
    sqltext = 'DELETE FROM "av_list" WHERE linkid="{}"'.format(linkid)
    DB['CUR'].execute(sqltext)
    DB['CONN'].commit()
    return 'movie已删除'


@app.route('/action/delete/stars/<linkid>')
def action_delete_stars(linkid=''):
    star_movie = querySql(
        'SELECT linkid,stars_url FROM av_list WHERE stars_url like "%|{}%"'.format(linkid))
    for item in star_movie:
        move_star_list = querySql('SELECT linkid FROM av_stars WHERE linkid in ("{}")'.format(
            item['stars_url'].strip('|').replace('|', '","')
        ))
        if len(move_star_list) == 1:
            sqltext = 'DELETE FROM "av_list" WHERE linkid="{}"'.format(
                item['linkid'])
            print(sqltext)
            DB['CUR'].execute(sqltext)
            DB['CONN'].commit()
    sqltext = 'DELETE FROM "av_stars" WHERE linkid="{}"'.format(linkid)
    print(sqltext)
    DB['CUR'].execute(sqltext)
    DB['CONN'].commit()
    return 'stars已删除'

def isLinkId(linkid = ''):
    # 识别linkid
    return re.match('^[a-z0-9]{16}$', linkid)

def insertExtendValue(extend_name, key, val):
    sqltext = "INSERT INTO av_extend (extend_name,key,val) values ('{}','{}','{}')".format(
        extend_name, key, val
    )
    print(sqltext)
    DB['CUR'].execute(sqltext)
    DB['CONN'].commit()


def selectExtendValue(extend_name, key):
    sqltext = 'select val from "av_extend" where extend_name="{}" and key="{}"'.format(
        extend_name, key
    )
    DB['CUR'].execute(sqltext)
    ret = DB['CUR'].fetchall()
    if len(ret) == 0:
        return []
    else:
        return [x[0] for x in ret]


def deleteExtendValue(extend_name, key, val):
    sqltext = 'delete from "av_extend" where extend_name="{}" and key="{}" and val="{}"'.format(
        extend_name, key, val
    )
    print(sqltext)
    DB['CUR'].execute(sqltext)
    DB['CONN'].commit()

#分页
def pagination(pagenum, count, pageroot):
    pagecount = math.ceil(count / PAGE_LIMIT)
    if pagecount <= 15:
        p1 = 1
        p2 = pagecount
    else:
        if pagenum - 7 < 1:
            p1 = 1
        else:
            p1 = pagenum - 7
        if pagenum + 7 > pagecount:
            p2 = pagecount
        else:
            p2 = pagenum + 7

    pagelist = [x for x in range(p1, p2 + 1)]

    if pagenum != pagecount:
        pageright = pagenum + 1
    else:
        pageright = 0
    if pagenum != 1:
        pageleft = pagenum - 1
    else:
        pageleft = 0

    return {
        'now': pagenum,
        'left': pageleft,
        'right': pageright,
        'list': pagelist,
        'pageroot':pageroot
    }


def conn():
    CONN = sqlite3.connect(config.getDbFile(), check_same_thread=False)
    CUR = CONN.cursor()
    return {
        'CONN': CONN,
        'CUR': CUR,
    }


def selectAvList(column='*', av_list_where=[], limit=(0, 30), order='release_date DESC', othertable=''):
    order = 'ORDER BY ' + order

    where_str = '1'
    if av_list_where != []:
        where_str = ' and '.join(av_list_where)
    sqltext = "SELECT {},count(av_extend.val) as movie_res_count FROM av_list left join av_extend on av_extend.extend_name='movie_res' and av_list.av_id=av_extend.key {} WHERE {} group by av_list.linkid {}".format(
        column, othertable, where_str, order)

    sqllimit = ' LIMIT {},{}'.format(limit[0], limit[1])
    result = querySql(sqltext + sqllimit)

    res_count = querySql(
        'SELECT COUNT(1) AS count FROM ({})'.format(sqltext))
    return (result, res_count[0]['count'])


def querySql(sql):
    cacheKey = (binascii.crc32(sql.encode()) & 0xffffffff)
    # 是否使用缓存
    if IF_USE_CACHE:
        # 是否有缓存
        if cacheKey in SQL_CACHE.keys():
            print('SQL CACHE[{}]'.format(cacheKey))
            return SQL_CACHE[cacheKey][:]
        else:
            print('SQL EXEC[{}]:\n{}'.format(cacheKey, sql))
            DB['CUR'].execute(sql)
            ret = DB['CUR'].fetchall()
            ret = showColumnname(ret, DB['CUR'].description)

            if IF_USE_CACHE:
                SQL_CACHE[cacheKey] = ret
            return ret[:]
    else:
        print('SQL EXEC:\n{}'.format(sql))
        DB['CUR'].execute(sql)
        ret = DB['CUR'].fetchall()
        ret = showColumnname(ret, DB['CUR'].description)
        return ret


def showColumnname(data, description):
    result = []
    for row in data:
        row_dict = {}
        for i in range(len(description)):
            row_dict[description[i][0]] = row[i]
        # 图片地址
        if 'bigimage' in row_dict.keys():
            row_dict['smallimage'] = row_dict['bigimage'].replace(
                'pl.jpg', 'ps.jpg')
        result.append(row_dict)

    return result


if __name__ == '__main__':
    DB = conn()
    app.run(port=5000)
