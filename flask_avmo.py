#!/usr/bin/env python3
# -*- coding:utf-8 -*-
from flask import render_template
from flask import Flask
from flask import request
from flask import redirect
from flask import url_for
import sqlite3
import datetime
import requests
import time
import re
import os
import math
import binascii
import config
import spider_avmo
import _thread
import html
app = Flask(__name__)
app.jinja_env.auto_reload = True
app.config['TEMPLATES_AUTO_RELOAD'] = True

# 每页展示的数量
PAGE_LIMIT = 30
# 图片服务器，图片慢可以尝试换另一个
CDN_SITE = '//jp.netcdn.space'
CDN_SITE = '//pics.dmm.co.jp'
# 默认语言为中文
DEFAULT_LANGUAGE = 'cn'
# 缓存
SQL_CACHE = {}
# 缓存默认开启
IF_USE_CACHE = True
SPIDER_AVMO = spider_avmo.Avmo()

# 文件类型与判定
FILE_TAIL = {
    'mp4': "\.(mp4|mkv|flv|avi|rm|rmvb|mpg|mpeg|mpe|m1v|mov|3gp|m4v|m3p|wmv|wmp|wm|ts)$",
    'jpg': "\.(jpg|png|gif|jpeg|bmp|ico)$",
    'mp3': "\.(mp3|wav|wmv|mpa|mp2|ogg|m4a|aac)$",
    'torrent': "\.torrent$",
    'zip': "\.(zip|rar|gz|7z)$",
    'doc': "\.(xls|xlsx|doc|docx|ppt|pptx|csv|pdf|html|txt)$",
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
            where.append("av_list.av_id LIKE '%{}%'".format(tmp))
    # 搜索
    elif keyword != '':
        key_list = keyword.split(' ')

        for key_item in key_list:
            if key_item == '已发布':
                date = time.strftime("%Y-%m-%d", time.localtime())
                where.append("av_list.release_date <= '{}'".format(date))
                continue

            if key_item == '有资源':
                where.append(
                    "av_id IN (SELECT distinct key FROM av_extend WHERE extend_name='movie_res')")
                continue

            if key_item == '已下载':
                where.append(
                    "av_id IN (SELECT distinct key FROM av_extend WHERE extend_name='movie_res' AND val NOT LIKE 'magnet%' AND val NOT LIKE 'http%')")
                continue

            if key_item == '收藏影片':
                # where.append("av_list.av_id in (SELECT val FROM av_like WHERE type='av_id')")

                where.append(
                    "av_id IN (SELECT distinct val FROM av_extend WHERE extend_name='like' and key='av_id')")
                continue

            where.append('''
            (av_list.title LIKE '%{0}%' OR
            av_list.director = '{0}' OR
            av_list.studio = '{0}' OR
            av_list.label = '{0}' OR
            av_list.series LIKE '%{0}%' OR
            av_list.genre LIKE '%{0}%' OR
            av_list.stars LIKE '%{0}%')'''.format(key_item))

    elif keyword == '':
        where = []

    result = select_av_list(column='av_list.*', av_list_where=where,
                            limit=(limit_start, PAGE_LIMIT))
    if keyword != '':
        page_root = '/search/{}'.format(keyword)
    else:
        page_root = ''
    return render_template('index.html', data={'av_list': result[0]}, cdn=CDN_SITE, page=pagination(pagenum, result[1], page_root, PAGE_LIMIT), keyword=keyword)


@app.route('/movie/<linkid>')
def movie(linkid=''):
    if linkid == '':
        return redirect(url_for('index'), 404)
    if '-' in linkid:
        where = ['av_list.av_id="{}"'.format(linkid.upper())]
    else:
        where = ['av_list.linkid="{}"'.format(linkid)]
    sql_arr = select_av_list(
        column='av_list.*', av_list_where=where, limit=(0, 1))

    if sql_arr[0] == []:
        return redirect(url_for('index'), 404)

    movie = sql_arr[0][0]
    # 系列
    if movie['genre']:
        movie['genre_list'] = movie['genre'].split('|')
    # 演员
    if movie['stars_url']:
        sqltext = "SELECT linkid,name,headimg FROM av_stars WHERE linkid IN ('{}')".format(
            movie['stars_url'].strip('|').replace('|', "','"))
        stars_data = query_sql(sqltext)
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
    movie['movie_resource_list'] = select_extend_value(
        'movie_res', movie['av_id'])
    return render_template('movie.html', data=movie, cdn=CDN_SITE, avmoo_url=config.get_avmoo_url())


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
        where = ["av_list.{}_url='{}'".format(function, keyword)]
    if function == 'genre':
        where = ["av_list.{} LIKE '%{}%'".format(function, keyword)]
    if function == 'stars':
        where = ["av_list.stars_url LIKE '%{}%'".format(keyword)]

    page_root = '/{}/{}'.format(function, keyword)
    result = select_av_list(column="av_list.*",
                            av_list_where=where, limit=(limit_start, PAGE_LIMIT))

    starsData = None
    if function == 'stars' and pagenum == 1:
        starsData = query_sql(
            "SELECT * FROM av_stars WHERE linkid='{}';".format(keyword))[0]
        # 计算年龄
        if starsData['birthday'] != '':
            sp = starsData['birthday'].split('-')
            birthdayData = datetime.date(int(sp[0]), int(sp[1]), int(sp[2]))
            starsData['age'] = math.ceil(
                (datetime.date.today() - birthdayData).days/365)
        keyword = starsData['name']

    if function != 'genre' and function != 'stars':
        keyword = ''

    return render_template('index.html', data={'av_list': result[0], 'av_stars': starsData}, cdn=CDN_SITE, page=pagination(pagenum, result[1], page_root, PAGE_LIMIT), keyword=keyword, avmoo_url=config.get_avmoo_url())


@app.route('/genre')
def genre():
    result = query_sql("SELECT name,title FROM av_genre")
    data = {}
    for item in result:
        if item['title'] not in data:
            data[item['title']] = []
        data[item['title']].append(item)
    data = list(data.values())
    return render_template('genre.html', data=data, cdn=CDN_SITE, page={'pageroot': "/genre", 'count': len(result)})


@app.route('/like/add/<data_type>/<data_val>')
def like_add(data_type=None, data_val=None):
    if data_type != None and data_val != None:
        timetext = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        sqltext = "REPLACE INTO av_like VALUES('{}', '{}', '{}')".format(
            data_type, data_val, timetext)
        execute_sql(sqltext)
        return '已添加收藏'


@app.route('/like/del/<data_type>/<data_val>')
def like_del(data_type=None, data_val=None):
    if data_type != None and data_val != None:
        sqltext = "DELETE FROM av_like WHERE type='{}' AND val='{}'".format(
            data_type, data_val)
        execute_sql(sqltext)
        return '已删除收藏'


@app.route('/actresses')
@app.route('/actresses/page/<int:pagenum>')
def like_stars(pagenum=1):
    pageLimit = 36
    sqltext = "SELECT av_stars.*,COUNT(distinct av_list.release_date) AS movie_count,av_list.release_date FROM av_stars LEFT JOIN (SELECT release_date,stars_url FROM av_list ORDER BY release_date desc)av_list ON INSTR(av_list.stars_url, av_stars.linkid) > 0 GROUP BY av_stars.linkid ORDER BY av_list.release_date DESC LIMIT {},{}".format(
        (pagenum - 1) * pageLimit, pageLimit)
    result = query_sql(sqltext)

    res_count = query_sql("SELECT COUNT(1) AS count FROM av_stars")
    return render_template('actresses.html', data=result, cdn=CDN_SITE, page=pagination(pagenum, res_count[0]['count'], "/actresses", pageLimit))


@app.route('/action/scandisk')
def action_scandisk():
    if 'path_target' not in request.values or 'file_target' not in request.values:
        return render_template('scandisk.html')

    path_target = request.values['path_target']
    path_target = upperPath(path_target)
    if not os.path.exists(path_target):
        return render_template('scandisk.html')

    # 文件目标类型
    file_target = request.values['file_target']
    # 路径信息
    file_res = []
    av_data_map = {}
    extend_file_list = {}
    if file_target == "mp4":
        ret = query_sql(
            "SELECT key,val FROM av_extend WHERE extend_name='movie_res' AND val NOT LIKE 'magnet%' AND val NOT LIKE 'http%'", False)
        for row in ret:
            if row['key'] in extend_file_list:
                extend_file_list[row['key']].append(row['val'])
            else:
                extend_file_list[row['key']] = [row['val']]

    reg = FILE_TAIL[file_target]
    # 遍历所有文件
    for root, file in walk_all_files(path_target):
        # 不符合后缀要求略过
        if not re.search(reg, file):
            continue

        nowPath = upperPath(os.path.join(root, file))
        av_check = re.search(AV_FILE_REG, file)
        if file_target != "mp4" or not av_check:
            file_res.append({
                'file_path': nowPath,
                'file_target': file_target,
            })
            continue

        # 格式化avid
        av_id = av_check.group(0).upper()
        exist = (
            av_id in extend_file_list and nowPath in extend_file_list[av_id])
        info = ''
        if exist:
            info += spanColor("[已存储路径]", "green")
        else:
            info += spanColor("[未存储路径]", "red")

        file_res.append({
            'file_path': nowPath,
            'file_target': file_target,
            'info': info,
            'av_id': av_id,
        })
    if file_target == "mp4":
        av_id_list = [x["av_id"] for x in file_res if "av_id" in x]
        sqltext = "SELECT * FROM 'av_list' WHERE av_id in ('{}')".format(
            "','".join(av_id_list))
        for row in query_sql(sqltext, False):
            av_data_map[row["av_id"]] = row

    for i in range(len(file_res)):
        if 'av_id' not in file_res[i]:
            continue
        if file_target == "mp4":
            if file_res[i]['av_id'] in av_data_map:
                file_res[i]['info'] += spanColor("[影片已抓取]", "green")
            else:
                file_res[i]['info'] += spanColor("[影片未抓取]", "red")
        file_res[i]['info'] = file_res[i]['info'].strip(',')

    return render_template('scandisk.html', file_res=file_res, av_data_map=av_data_map, file_target=file_target, path_target=path_target, avmoo_url=config.get_avmoo_url())

# 遍历文件


def walk_all_files(path_target):
    for root, dirs, files in os.walk(path_target):
        for file in files:
            yield root, file


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
    val = html.unescape(val)
    # 格式化
    if extend_name == "movie_res":
        # key目前只会存avid所以upper无碍
        key = key.upper()
        val = upperPath(val)
    sqltext = "INSERT INTO av_extend (extend_name,key,val) VALUES ('{}','{}','{}')".format(
        extend_name, key, val
    )
    execute_sql(sqltext)
    return '扩展信息添加成功'


@app.route('/action/extend/delete/<extend_name>/<key>/<val>')
def action_extend_delete(extend_name, key, val):
    sqltext = "DELETE from av_extend WHERE extend_name='{}' AND key='{}' AND val='{}'".format(
        extend_name, key, val
    )
    execute_sql(sqltext)
    return '扩展信息删除成功'


@app.route('/action/download/star/<linkid>')
def action_download_star(linkid=''):
    global SPIDER_AVMO

    if linkid == 'all':
        star_list = query_sql("SELECT linkid FROM av_stars")
        _thread.start_new_thread(SPIDER_AVMO.spider_by_stars_list, ([
                                 x['linkid'] for x in star_list],))
        return '正在下载所有...'

    if not isLinkId(linkid):
        return 'id格式不正确'
    _thread.start_new_thread(SPIDER_AVMO.spider_by_stars, (linkid, False))
    return '{},正在下载...'.format(linkid)


@app.route('/action/download/movie/<linkid>')
def action_download_movie(linkid=''):
    global SPIDER_AVMO
    if not isLinkId(linkid):
        return 'id格式不正确'
    _thread.start_new_thread(SPIDER_AVMO.spider_by_movie, (linkid, ))
    return '{},正在下载影片...'.format(linkid)


@app.route('/action/download/genre')
def action_download_genre():
    global SPIDER_AVMO
    _thread.start_new_thread(SPIDER_AVMO.genre_update, ())
    return '正在下载...'

# 仅限手动调用


@app.route('/action/delete/movie/<linkid>')
def action_delete_movie(linkid=''):
    sqltext = "DELETE FROM av_list WHERE linkid='{}'".format(linkid)
    execute_sql(sqltext)
    return 'movie已删除'

# 仅限手动调用


@app.route('/action/delete/stars/<linkid>')
def action_delete_stars(linkid=''):
    star_movie = query_sql(
        "SELECT linkid,stars_url FROM av_list WHERE stars_url like '%|{}%'".format(linkid))
    for item in star_movie:
        move_star_list = query_sql("SELECT linkid FROM av_stars WHERE linkid IN ('{}')".format(
            item['stars_url'].strip('|').replace('|', "','")
        ))
        if len(move_star_list) == 1:
            sqltext = "DELETE FROM av_list WHERE linkid='{}'".format(
                item['linkid'])
            print(sqltext)
            DB['CUR'].execute(sqltext)
            DB['CONN'].commit()
    sqltext = "DELETE FROM av_stars WHERE linkid='{}'".format(linkid)
    execute_sql(sqltext)
    return 'stars已删除'


@app.route('/action/translate/<data>')
def action_translate(data=''):
    tmp = data.split(' ')
    tmp.pop(0)
    inputtext = ''.join(tmp)

    res = requests.post('http://wap.youdao.com/translate',
                        data={'inputtext': inputtext, 'type': 'JA2ZH_CN'})
    if res.status_code != 200 or len(res.text) < 20000:
        return "出现错误.." + inputtext
    tt = re.findall('<ul id="translateResult">(.*?)<\/ul>',
                    res.text, re.DOTALL)
    if tt == []:
        return "出现错误.." + inputtext
    return tt[0].strip()[4:-5]


def upperPath(path):
    # 如果为windows环境路径，则路径首字母大写
    if re.match("^[a-z]\:\\\\", path):
        return path[0].upper() + path[1:]
    else:
        return path


def spanColor(content, color):
    return '<span style="color:{}">{}</span>'.format(color, content)

# 识别linkid
def isLinkId(linkid=''):
    return re.match('^[a-z0-9]{16}$', linkid)


def select_extend_value(extend_name, key):
    sqltext = "SELECT val from av_extend WHERE extend_name='{}' AND key='{}'".format(
        extend_name, key
    )
    ret = query_sql(sqltext, False)
    if len(ret) == 0:
        return []
    else:
        return [x["val"] for x in ret]

# 分页
def pagination(pagenum, count, pageroot, pagelimit):
    pagecount = math.ceil(count / pagelimit)
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
        'pageroot': pageroot,
        'count': count
    }


def conn():
    CONN = sqlite3.connect(config.get_db_file(), check_same_thread=False)
    CUR = CONN.cursor()
    return {
        'CONN': CONN,
        'CUR': CUR,
    }


def select_av_list(column='*', av_list_where=[], limit=(0, 30), order='release_date DESC', othertable=''):
    order = 'ORDER BY ' + order

    where_str = '1'
    if av_list_where != []:
        where_str = ' and '.join(av_list_where)
    sqltext = "SELECT {} FROM av_list {} WHERE {} GROUP BY av_list.linkid {}".format(
        column, othertable, where_str, order)
    result = query_sql(sqltext + ' LIMIT {},{}'.format(limit[0], limit[1]))

    # 扩展信息
    extendList = select_extend_by_key([x["av_id"] for x in result])
    for i in range(len(result)):
        # 图片地址
        result[i]['smallimage'] = result[i]['bigimage'].replace(
            'pl.jpg', 'ps.jpg')
        # 扩展信息
        if result[i]['av_id'] not in extendList or 'movie_res' not in extendList[result[i]['av_id']]:
            continue
        for extend in extendList[result[i]['av_id']]['movie_res']:
            if extend[:6] == "magnet" or extend[:3] == "115":
                result[i]['magnet'] = 1
                continue
            if extend[:4] == "http":
                result[i]['http'] = 1
                continue
            result[i]['file'] = 1
    res_count = query_sql('SELECT COUNT(1) AS count FROM ({})'.format(sqltext))
    return (result, res_count[0]['count'])

# 获取指定key的扩展信息


def select_extend_by_key(keyList):
    if len(keyList) == 0:
        return {}
    sqltext = "SELECT key,extend_name,val from av_extend WHERE key IN ('{}')".format(
        "','".join(keyList))
    result = query_sql(sqltext)
    ret = {}
    for extend in result:
        if extend['key'] not in ret:
            ret[extend['key']] = {}

        if extend['extend_name'] not in ret[extend['key']]:
            ret[extend['key']][extend['extend_name']] = []
        ret[extend['key']][extend['extend_name']].append(extend['val'])
    return ret


def execute_sql(sql):
    DB['CUR'].execute(sql)
    DB['CONN'].commit()
    SQL_CACHE = {}


def query_sql(sql, ifCache=True) -> list:
    cacheKey = (binascii.crc32(sql.encode()) & 0xffffffff)
    # 是否使用缓存
    if IF_USE_CACHE and ifCache:
        # 是否有缓存
        if cacheKey in SQL_CACHE.keys():
            print('SQL CACHE[{}]'.format(cacheKey))
            return SQL_CACHE[cacheKey][:]
        else:
            print('SQL EXEC[{}]:\n{}'.format(cacheKey, sql))
            DB['CUR'].execute(sql)
            ret = DB['CUR'].fetchall()
            ret = show_column_name(ret, DB['CUR'].description)

            if IF_USE_CACHE:
                SQL_CACHE[cacheKey] = ret
            return ret[:]
    else:
        print('SQL EXEC:\n{}'.format(sql))
        DB['CUR'].execute(sql)
        ret = DB['CUR'].fetchall()
        ret = show_column_name(ret, DB['CUR'].description)
        return ret


def show_column_name(data, description) -> list:
    result = []
    for row in data:
        row_dict = {}
        for i in range(len(description)):
            row_dict[description[i][0]] = row[i]
        result.append(row_dict)
    return result


if __name__ == '__main__':
    DB = conn()
    app.run(port=5000)
