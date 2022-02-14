#!/usr/bin/env python3
# -*- coding:utf-8 -*-
from flask import render_template
from flask import Flask
from flask import request
from flask import redirect
from flask import url_for
import json
import datetime
import requests
import time
import re
import os
import math
import binascii
import common
import spider_avmo
import _thread
import collections
from queue import Queue
from urllib.parse import quote, unquote

app = Flask(__name__)
app.jinja_env.auto_reload = True
app.config['TEMPLATES_AUTO_RELOAD'] = True


# 全局配置初始化
common.init()
# 数据库
DB = common.DB

# 每页展示的数量
PAGE_LIMIT = common.CONFIG.getint("website", "page_limit")

# 缓存
SQL_CACHE = {}
# 缓存默认开启
IF_USE_CACHE = True
SPIDER_AVMO = spider_avmo.Avmo()

# 文件类型与判定
FILE_TAIL = {
    'mp4': "\.(mp4|mkv|flv|avi|rm|rmvb|mpg|mpeg|mpe|m1v|mov|3gp|m4v|m3p|wmv|wmp|wm)$",
    'jpg': "\.(jpg|png|gif|jpeg|bmp|ico)$",
    'mp3': "\.(mp3|wav|wmv|mpa|mp2|ogg|m4a|aac)$",
    'torrent': "\.torrent$",
    'zip': "\.(zip|rar|gz|7z)$",
    'doc': "\.(xls|xlsx|doc|docx|ppt|pptx|csv|pdf|html|txt)$",
}

AV_FILE_REG = "[a-zA-Z]{3,5}-\d{3,4}"

# 任务队列
QUEUE = Queue(maxsize=0)

# 主页 搜索页
@app.route('/')
@app.route('/page/<int:pagenum>')
@app.route('/search/<keyword>')
@app.route('/search/<keyword>/page/<int:pagenum>')
def index(keyword='', pagenum=1):
    if pagenum < 1:
        redirect(url_for('/'))
    limit_start = (pagenum - 1) * PAGE_LIMIT

    where = []
    # 识别linkid
    if isLinkId(keyword):
        return movie(keyword)
    # sql mode
    elif keyword[:5] == 'where':
        where.append(keyword[5:])
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
                where.append(
                    "av_id IN (SELECT distinct val FROM av_extend WHERE extend_name='like' AND key='av_id')")
                continue

            where.append('''
            (av_list.title LIKE '%{0}%' OR
            av_list.director = '{0}' OR
            av_list.studio = '{0}' OR
            av_list.label = '{0}' OR
            av_list.series LIKE '%{0}%' OR
            av_list.genre LIKE '%{0}%' OR
            av_list.stars LIKE '%{0}%')'''.format(key_item))


    result = select_av_list(column='av_list.*', av_list_where=where,
                            limit=(limit_start, PAGE_LIMIT))
    if keyword != '':
        page_root = '/search/{}'.format(quote(keyword))
    else:
        page_root = ''
    return render_template('index.html', data={'av_list': result[0]}, page=pagination(pagenum, result[1], page_root, PAGE_LIMIT), keyword=keyword, config=common.CONFIG)

# 电影页
@app.route('/movie/<linkid>')
def movie(linkid=''):
    if linkid == '':
        return redirect(url_for('index'), 404)
    if '-' in linkid:
        where = 'av_list.av_id="{}"'.format(linkid.upper())
    else:
        where = 'av_list.linkid="{}"'.format(linkid)
    movieList = query_sql("SELECT * FROM av_list WHERE {}".format(where))
    if movieList == []:
        return redirect(url_for('index'), 404)
    return render_template('movie.html', data=movieBuild(movieList[0]), origin_link = common.get_url("movie", movieList[0]["linkid"]), config=common.CONFIG)

# 构造电影页
def movieBuild(movie):
    if 'build' in movie:
        return movie
    # 修复数据
    if len(movie["genre"]) > 0 and movie["genre"][0] != '|':
        execute_sql(
            "update av_list set genre=('|' || genre || '|')  where genre not like '|%'")
    # 修复数据 20200212
    if len(movie["stars"]) > 0 and movie["stars"][-1] != '|':
        execute_sql(
            "update av_list set stars=(stars || '|')  where stars not like '%|'")
    # 系列
    if movie['genre'] != "":
        movie['genre_list'] = movie['genre'][1:].split('|')
    
    # 演员
    if movie['stars_url'] != "" and not isinstance(movie['stars_url'], list):
        movie['stars_url'] = movie['stars_url'].strip('|').split("|")
        movie['stars'] = movie['stars'].strip('|').split("|")

        sqltext = "SELECT linkid,name,headimg FROM av_stars WHERE linkid IN ('{}')".format(
            "','".join(movie['stars_url'])
        )
        movie['stars_data'] = query_sql(sqltext)
        # 其他所有演员
        if len(movie['stars_data']) < len(movie['stars_url']):
            movie['stars_map'] = []
            linkid_list = [x["linkid"] for x in movie['stars_data']]
            for i in range(len(movie['stars_url'])):
                if movie['stars_url'][i] in linkid_list:
                    continue
                movie['stars_map'].append({
                    "linkid": movie['stars_url'][i],
                    "name": movie['stars'][i]
                })

    # 图片
    movie['imglist'] = []
    if movie['image_len'] != '0':
        count = int(movie['image_len'])
        imgurl = common.CONFIG.get("website", "cdn") + '/digital/video' + \
            movie['bigimage'].replace('pl.jpg', '')
        for i in range(1, count+1):
            movie['imglist'].append({
                'small': '{}-{}.jpg'.format(imgurl, i),
                'big': '{}jp-{}.jpg'.format(imgurl, i)
            })
    
    # 影片资源
    movie['movie_resource_list'] = select_extend_value(
        'movie_res', movie['av_id'])
    movie['build'] = True
    return movie

# 分类页
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
    origin_link = common.get_url(function, keyword, pagenum)
    if function in ['director','studio','label','series']:
        where = ["av_list.{}_url='{}'".format(function, keyword)]
    if function == 'genre':
        where = ["av_list.genre LIKE '%|{}|%'".format(keyword)]
        ret = common.fetchall(DB['CUR'], "SELECT * FROM av_genre WHERE name='{}'".format(keyword))
        if len(ret) > 0:
            origin_link = common.get_url(function, ret[0]['linkid'], pagenum)
    if function == 'stars':
        where = ["av_list.stars_url LIKE '%|{}%'".format(keyword)]

    page_root = '/{}/{}'.format(function, keyword)
    result = select_av_list(column="av_list.*",
                            av_list_where=where, limit=(limit_start, PAGE_LIMIT))

    starsData = None
    if function == 'stars':
        starsData = query_sql(
            "SELECT * FROM av_stars WHERE linkid='{}';".format(keyword))
        if len(starsData) == 1:
            starsData = starsData[0]
            # 计算年龄
            if starsData['birthday'] != '':
                sp = starsData['birthday'].split('-')
                birthdayData = datetime.date(int(sp[0]), int(sp[1]), int(sp[2]))
                starsData['age'] = math.ceil(
                    (datetime.date.today() - birthdayData).days/365)
            keyword = starsData['name']
        else:
            keyword = ''

    if function != 'genre' and function != 'stars':
        keyword = ''

    return render_template('index.html', data={'av_list': result[0], 'av_stars': starsData}, page=pagination(pagenum, result[1], page_root, PAGE_LIMIT), keyword=keyword, origin_link = origin_link, config=common.CONFIG)


# 标签页
@app.route('/genre')
def genre():
    # 统计标签个数
    genre_list = []
    for row in query_sql("SELECT genre AS genre FROM av_list"):
        genre_list.extend(list(set(row['genre'].strip("|").split("|"))))
    genre_counter = collections.Counter(genre_list)

    data = {}
    av_genre_res = query_sql("SELECT linkid,name,title FROM av_genre")
    for item in av_genre_res:
        if item['title'] not in data:
            data[item['title']] = []
        # 组装标签数据
        if item['name'] in genre_counter:
            item["genre_count"] = genre_counter[item['name']]
        
        data[item["title"]].append(item)
    data = list(data.values())
    return render_template('genre.html', data={'av_genre': data}, page={'pageroot': "/genre", 'count': len(av_genre_res)}, origin_link = common.get_url("genre"), config=common.CONFIG)

# 演员页
@app.route('/actresses')
@app.route('/actresses/page/<int:pagenum>')
def like_stars(pagenum=1):
    pageLimit = common.CONFIG.getint("website", "actresses_page_limit")
    sqltext = "SELECT av_stars.*,COUNT(av_list.release_date) AS movie_count,av_list.release_date FROM av_stars LEFT JOIN (SELECT release_date,stars_url FROM av_list ORDER BY release_date desc)av_list ON INSTR(av_list.stars_url, av_stars.linkid) > 0 GROUP BY av_stars.linkid ORDER BY av_list.release_date DESC LIMIT {},{}".format(
        (pagenum - 1) * pageLimit, pageLimit)
    result = query_sql(sqltext)

    res_count = query_sql("SELECT COUNT(1) AS count FROM av_stars")
    return render_template('actresses.html', data=result, page=pagination(pagenum, res_count[0]['count'], "/actresses", pageLimit), origin_link = common.get_url("actresses"), config=common.CONFIG)

# 爬虫页
@app.route('/spider')
def page_spider():
    return render_template('spider.html', config=common.CONFIG)

# 爬虫接口
@app.route('/action/crawl', methods=['POST'])
def action_crawl():
    input_text = request.form['input_text']
    input_list = [x.strip() for x in input_text.split("\n") if x.strip() != ""]
    if len(input_list) == 0:
        return '请输入有效id'
    for link in input_list:
        QUEUE.put((
            "crawl_by_url",
            (link, )
        ))
    return '正在下载({})影片...'.format(len(input_list))

# 爬虫精确接口 确定到页面类型
@app.route('/action/crawl/accurate', methods=['POST'])
def action_crawl_accurate():
    global QUEUE, SQL_CACHE
    page_type = request.form['page_type']
    keyword = request.form['keyword']
    if page_type not in ['movie', 'star', 'genre', 'series', 'studio', 'label', 'director', 'search']:
        return 'wrong'
    QUEUE.put((
        "crawl_accurate",
        (page_type, keyword, 1, False)
    ))
    SQL_CACHE = {}
    return '正在下载...'


# 演员爬虫接口
@app.route('/action/crawl/star', methods=['POST'])
def action_crawl_star():
    global QUEUE
    linkid = request.form['linkid']

    if linkid == 'all':
        star_list = query_sql("SELECT linkid,name FROM av_stars")
        for item in star_list:
            # 增量更新
            QUEUE.put((
                "crawl_accurate",
                ('star', item["linkid"], 1, True)
            ))
        return '正在下载({})...'.format(','.join([x['name'] for x in star_list]))

    if not isLinkId(linkid):
        return '请输入有效id'
    star_list = query_sql("SELECT linkid,name FROM av_stars WHERE linkid='{}'".format(linkid))
    # 全量更新
    QUEUE.put((
        "crawl_accurate",
        ("star", linkid, 1, False)
    ))
    return '正在下载({})...'.format(star_list[0]["name"])

# 类目爬虫接口
@app.route('/action/crawl/genre')
def action_crawl_genre():
    global QUEUE
    QUEUE.put((
        "crawl_genre",
        ()
    ))
    return '正在下载...'

@app.route('/action/last/insert')
def action_last_insert():
    return json.dumps(SPIDER_AVMO.get_last_insert_list())

# 磁盘扫描工具
@app.route('/action/scandisk')
def action_scandisk():
    if 'path_target' not in request.values or 'file_target' not in request.values:
        return render_template('scandisk.html', config=common.CONFIG)

    path_target = request.values['path_target']
    path_target = upperPath(path_target)
    if not os.path.exists(path_target):
        return render_template('scandisk.html', config=common.CONFIG)

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
            # 图片地址
            row['smallimage'] = row['bigimage'].replace(
                'pl.jpg', 'ps.jpg')
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

    return render_template('scandisk.html', file_res=file_res, av_data_map=av_data_map, file_target=file_target, path_target=path_target, config=common.CONFIG)

# 缓存开关
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

# 本地打开
@app.route('/action/explorer')
def action_explorer():
    path = request.values["path"]
    # 打开指定路径
    os.system('explorer "{}"'.format(path))
    return 'ok'

# 添加扩展信息接口
@app.route('/action/extend/insert')
def action_extend_insert():
    extend_name = request.values["extend_name"]
    key = request.values["key"]
    val = request.values["val"]
    # 格式化
    if extend_name == "movie_res":
        # key目前只会存avid所以upper无碍
        key = key.upper()
        val = upperPath(val)
        bizName = "资源"

    if extend_name == "like":
        bizName = "收藏"

    valList = select_extend_value(extend_name, key)
    if val in valList:
        return "已存在不能重复添加"
    else:
        sqltext = "INSERT INTO av_extend (extend_name,key,val) VALUES ('{}','{}','{}')".format(
            extend_name, key, val
        )
        execute_sql(sqltext)
        return bizName + '已添加'

# 删除扩展信息接口
@app.route('/action/extend/delete')
def action_extend_delete():
    extend_name = request.values["extend_name"]
    key = request.values["key"]
    val = request.values["val"]
    sqltext = "DELETE from av_extend WHERE extend_name='{}' AND key='{}' AND val='{}'".format(
        extend_name, key, val
    )
    execute_sql(sqltext)
    return '已删除'


# 删除影片 仅限手动调用
@app.route('/action/delete/movie/<linkid>')
def action_delete_movie(linkid=''):
    sqltext = "DELETE FROM av_list WHERE linkid='{}'".format(linkid)
    execute_sql(sqltext)
    return 'movie已删除'

# 删除演员 仅限手动调用
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

# 标题翻译
@app.route('/action/translate')
def action_translate():
    tmp = request.values["words"].split(' ')
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

# 分析演员
@app.route('/action/analyse/star/<linkid>')
def action_analyse_star(linkid=''):
    sql = "SELECT * FROM av_list WHERE stars_url like '%|{}%';".format(linkid)
    data = query_sql(sql, False)
    genreAll = []
    starsAll = []
    minuteSum = 0
    for row in data:
        genreAll.extend(row["genre"].strip('|').split("|"))
        starsAll.extend(row["stars"].strip('|').split("|"))
        minuteSum = minuteSum + int(row["len"])

    genreCounter = collections.OrderedDict(
        sorted(collections.Counter(genreAll).items(), key=lambda x: x[1], reverse=True))
    starsCounter = collections.OrderedDict(
        sorted(collections.Counter(starsAll).items(), key=lambda x: x[1], reverse=True))

    genreList = []
    starsList = []

    for key in list(genreCounter.keys()):
        genreList.append({
            'name': key,
            'count': genreCounter[key]
        })

    headList = list(starsCounter.keys())[:21]
    for key in list(starsCounter.keys()):
        if key in headList:
            starsList.append({
                'name': key,
                'count': starsCounter[key]
            })
    return {
        "starName": starsList[0]['name'],
        "minuteSum": minuteSum,
        "genreCounter": genreList,
        "starsCounter": starsList[1:]
    }


@app.route('/action/change/language')
def action_change_language():
    country = request.values['country']
    common.CONFIG.set("base", "country", country)
    common.config_save()
    common.config_init()
    return 'ok'

# 爬虫线程
def spider_thread():
    global QUEUE, SPIDER_AVMO
    SPIDER_AVMO.init_db()
    print("spider_thread.start")
    while True:
        time.sleep(common.CONFIG.getfloat("spider", "sleep"))

        (function_name, param) = QUEUE.get()
        print("=" * 10, function_name, param, "=" * 10, "start")
        if function_name == "crawl_accurate":
            SPIDER_AVMO.crawl_accurate(param[0], param[1], param[2], param[3])
        if function_name == "crawl_by_url":
            SPIDER_AVMO.crawl_by_url(param[0])
        if function_name == "crawl_genre":
            SPIDER_AVMO.crawl_genre()
        
        print("=" * 10, function_name, param, "=" * 10, "end\n")

def upperPath(path):
    # 如果为windows环境路径，则路径首字母大写
    if re.match("^[a-z]\:\\\\", path):
        return path[0].upper() + path[1:]
    else:
        return path

# 上色
def spanColor(content, color):
    return '<span style="color:{}">{}</span>'.format(color, content)


# 识别linkid
def isLinkId(linkid=''):
    return re.match('^[a-z0-9]{16}$', linkid)


# 分页
def pagination(pagenum, count, pageroot, pagelimit):
    pagecount = math.ceil(count / pagelimit)
    total_max = 8
    p1 = pagenum - total_max
    p2 = pagenum + total_max
    pagelist = [x for x in range(p1, p2 + 1) if x > 0 and x <= pagecount]

    pageleft = 0
    pageright = 0
    if pagecount != 0 and pagenum != pagecount:
        pageright = pagenum + 1
    if pagenum != 1:
        pageleft = pagenum - 1
    
    pagehead = 0
    pagetail = 0
    if len(pagelist) > 0:
        if pagelist[0] != 1:
            pagehead = 1
        if pagelist[-1] != pagecount:
            pagetail = pagecount
    return {
        'now': pagenum,
        'left': pageleft,
        'right': pageright,
        'list': pagelist,
        'head': pagehead,
        'tail': pagetail,
        'pageroot': pageroot,
        'count': count
    }


# 查询列表
def select_av_list(column='*', av_list_where=[], limit=(0, 30), order='release_date DESC', othertable=''):
    order = 'ORDER BY ' + order

    where_str = '1'
    if av_list_where != []:
        where_str = ' and '.join(av_list_where)
    sqltext = "SELECT {} FROM av_list {} WHERE {} GROUP BY av_list.linkid {}".format(
        column, othertable, where_str, order)
    result = query_sql(sqltext + ' LIMIT {},{}'.format(limit[0], limit[1]))

    # 扩展信息
    extendList = select_extend_list('movie_res', [x["av_id"] for x in result])
    for i in range(len(result)):
        # 图片地址
        result[i]['smallimage'] = result[i]['bigimage'].replace(
            'pl.jpg', 'ps.jpg')
        # 扩展信息
        if result[i]['av_id'] not in extendList:
            continue
        for extend in extendList[result[i]['av_id']]:
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
def select_extend_list(extend_name, keyList):
    if len(keyList) == 0:
        return {}
    sqltext = "SELECT key,val from av_extend WHERE extend_name='{}' AND key IN ('{}')".format(
        extend_name, "','".join(keyList))
    result = query_sql(sqltext)
    ret = {}
    for extend in result:
        if extend['key'] not in ret:
            ret[extend['key']] = []
        ret[extend['key']].append(extend['val'])
    return ret


# 获取指定key的扩展信息
def select_extend_value(extend_name, key):
    sqltext = "SELECT val from av_extend WHERE extend_name='{}' AND key='{}'".format(
        extend_name, key
    )
    ret = query_sql(sqltext, False)
    if len(ret) == 0:
        return []
    else:
        return [x["val"] for x in ret]


# 遍历文件
def walk_all_files(path_target):
    for root, dirs, files in os.walk(path_target):
        for file in files:
            yield root, file


# 执行sql
def execute_sql(sql):
    print("SQL EXEC:\n{}".format(sql))
    DB['CUR'].execute(sql)
    DB['CONN'].commit()
    tableName = get_table_name(sql)[0]
    # 清除指定表的缓存
    for cacheKey in list(SQL_CACHE.keys()):
        if tableName in cacheKey:
            del SQL_CACHE[cacheKey]


# 查询sql
def query_sql(sql, if_cache=True) -> list:
    cacheKey = cache_key(sql)
    # 是否使用缓存
    if IF_USE_CACHE and if_cache:
        # 是否有缓存
        if cacheKey in SQL_CACHE.keys():
            print('SQL CACHE[{}]'.format(cacheKey))
            return SQL_CACHE[cacheKey][:]
        else:
            print('SQL EXEC[{}]:\n{}'.format(cacheKey, sql))
            ret = common.fetchall(DB["CUR"], sql)
            if IF_USE_CACHE and ret != []:
                SQL_CACHE[cacheKey] = ret
            return ret[:]
    else:
        print('SQL EXEC:\n{}'.format(sql))
        return common.fetchall(DB["CUR"], sql)


# 获取sql中的表名
def get_table_name(sql):
    return list(set(re.findall("(av_[a-z]+)", sql)))


# 获取缓存key
def cache_key(sql):
    return '|'.join(get_table_name(sql)) + ':' + str(binascii.crc32(sql.encode()) & 0xffffffff)


if __name__ == '__main__':
    _thread.start_new_thread(spider_thread, ())
    app.run(port=5000)
