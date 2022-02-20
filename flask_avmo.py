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
import threading
import collections
from queue import Queue
from urllib.parse import quote

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

SPIDER_AVMO = spider_avmo.Avmo()

# 文件类型与判定
FILE_TAIL = {
    'mp4': "\\.(mp4|mkv|flv|avi|rm|rmvb|mpg|mpeg|mpe|m1v|mov|3gp|m4v|m3p|wmv|wmp|wm)$",
    'jpg': "\\.(jpg|png|gif|jpeg|bmp|ico)$",
    'mp3': "\\.(mp3|wav|wmv|mpa|mp2|ogg|m4a|aac)$",
    'torrent': "\\.torrent$",
    'zip': "\\.(zip|rar|gz|7z)$",
    'doc': "\\.(xls|xlsx|doc|docx|ppt|pptx|csv|pdf|html|txt)$",
}

AV_FILE_REG = "[a-zA-Z]{3,5}-\\d{3,4}"

# 任务队列
QUEUE = Queue(maxsize=0)


# 主页 搜索页
@app.route('/')
@app.route('/page/<int:pagenum>')
@app.route('/search/<keyword>')
@app.route('/search/<keyword>/page/<int:pagenum>')
def index(keyword='', pagenum=1):
    where = []
    # 识别linkid
    if is_linkid(keyword):
        return movie(keyword)
    # sql mode
    elif keyword[:5] == 'WHERE':
        where.append(keyword[5:])
    # 搜索
    elif keyword != '':
        for key_item in keyword.split(' '):
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
            where.append(common.search_where(key_item))

    (result, row_count) = select_av_list(column='av_list.*', av_list_where=where,
                                         limit=((pagenum - 1) * PAGE_LIMIT, PAGE_LIMIT))
    if keyword != '':
        page_root = '/search/{}'.format(quote(keyword))
    else:
        page_root = ''
    return render_template('index.html', data={'av_list': result},
                           page=pagination(pagenum, row_count, page_root, PAGE_LIMIT), placeholder=keyword,
                           origin_link=common.get_url("search", quote(keyword), pagenum), config=common.CONFIG)


# 电影页
@app.route('/movie/<linkid>')
def movie(linkid=''):
    if linkid == '':
        return redirect(url_for('index'), 404)
    if '-' in linkid:
        where = 'av_list.av_id="{}"'.format(linkid.upper())
    else:
        where = 'av_list.linkid="{}"'.format(linkid)
    movie_list = query_sql("SELECT * FROM av_list WHERE {}".format(where))
    if not movie_list:
        return redirect(url_for('index'), 404)
    return render_template('movie.html', data=movie_build(movie_list[0]),
                           origin_link=common.get_url("movie", movie_list[0]["linkid"]), config=common.CONFIG)


# 构造电影页
def movie_build(movie):
    if 'build' in movie:
        return movie
    # 修复数据
    if len(movie["genre"]) > 0 and movie["genre"][0] != '|':
        execute_sql(
            "update av_list set genre=('|' || genre || '|')  where genre != '' and genre not like '|%'")
    # 修复数据 20200212
    if len(movie["stars"]) > 0 and movie["stars"][-1] != '|':
        execute_sql(
            "update av_list set stars=(stars || '|')  where stars != '' and stars not like '%|'")
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
        img_url = common.CONFIG.get("website", "cdn") + '/digital/video' + movie['bigimage'].replace('pl.jpg', '')
        for i in range(1, count + 1):
            movie['imglist'].append({
                'small': '{}-{}.jpg'.format(img_url, i),
                'big': '{}jp-{}.jpg'.format(img_url, i)
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
@app.route('/star/<keyword>')
@app.route('/star/<keyword>/page/<int:pagenum>')
def search(keyword='', pagenum=1):
    if pagenum < 1:
        return redirect(url_for('index'), 404)
    placeholder = ""
    page_type = request.path.split('/')[1]
    origin_link = common.get_url(page_type, keyword, pagenum)
    where = []
    if page_type in ['director', 'studio', 'label', 'series']:
        where = ["av_list.{}_url='{}'".format(page_type, keyword)]

    if page_type == 'genre':
        placeholder = keyword
        where = ["av_list.genre LIKE '%|{}|%'".format(keyword)]
        ret = common.fetchall(DB['CUR'], "SELECT * FROM av_genre WHERE name='{}'".format(keyword))
        if len(ret) > 0:
            origin_link = common.get_url(page_type, ret[0]['linkid'], pagenum)

    if page_type == 'star':
        where = ["av_list.stars_url LIKE '%|{}%'".format(keyword)]

    page_root = '/{}/{}'.format(page_type, keyword)
    (result, row_count) = select_av_list(column="av_list.*", av_list_where=where,
                                         limit=((pagenum - 1) * PAGE_LIMIT, PAGE_LIMIT))

    # 设置默认搜索词
    if page_type in ['director', 'studio', 'label', 'series'] and len(result) > 0:
        placeholder = result[0][page_type]

    star_data = None
    if page_type == 'star':
        if len(result) > 0 and result[0]["stars"] != "":
            placeholder = result[0]["stars"].split("|")[result[0]["stars_url"].split("|").index(keyword)]

        star_data = query_sql(
            "SELECT * FROM av_stars WHERE linkid='{}';".format(keyword))
        if len(star_data) == 1:
            star_data = star_data[0]
            # 计算年龄
            if star_data['birthday'] != '':
                sp = star_data['birthday'].split('-')
                birthday_data = datetime.date(int(sp[0]), int(sp[1]), int(sp[2]))
                star_data['age'] = math.ceil(
                    (datetime.date.today() - birthday_data).days / 365)

    return render_template('index.html', data={'av_list': result, 'av_stars': star_data},
                           page=pagination(pagenum, row_count, page_root, PAGE_LIMIT), placeholder=placeholder,
                           origin_link=origin_link, config=common.CONFIG)


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
    return render_template('genre.html', data={'av_genre': data},
                           page={'pageroot': "/genre", 'count': len(av_genre_res)}, origin_link=common.get_url("genre"),
                           config=common.CONFIG)


# 演员页
@app.route('/actresses')
@app.route('/actresses/page/<int:pagenum>')
def like_stars(pagenum=1):
    page_limit = common.CONFIG.getint("website", "actresses_page_limit")
    sqltext = '''
    SELECT av_stars.*,COUNT(av_list.release_date) AS movie_count,av_list.release_date
    FROM av_stars
    LEFT JOIN (
        SELECT release_date,stars_url
        FROM av_list
        ORDER BY release_date desc
    )av_list ON INSTR(av_list.stars_url, av_stars.linkid) > 0
    GROUP BY av_stars.linkid
    ORDER BY av_list.release_date DESC LIMIT {},{}
    '''.format(
        (pagenum - 1) * page_limit, page_limit)
    result = query_sql(sqltext)

    res_count = query_sql("SELECT COUNT(1) AS count FROM av_stars")
    return render_template('actresses.html', data=result,
                           page=pagination(pagenum, res_count[0]['count'], "/actresses", page_limit),
                           origin_link=common.get_url("actresses"), config=common.CONFIG)


# 配置页
@app.route('/config')
def page_config():
    return render_template('config.html', config=common.CONFIG)


# 修改配置
@app.route('/action/config', methods=['POST'])
def action_config():
    # 表单存在的配置项name
    for name in common.CONFIG_NAME_LIST:
        if name not in request.form:
            continue
        (section, option) = name.split(".")
        common.CONFIG.set(section=section, option=option, value=request.form[name])
    common.config_save(common.CONFIG)
    common.config_init()
    print("new config:", list(request.form))
    return redirect(url_for('page_config'))


# 爬虫页
@app.route('/spider')
def page_spider():
    return render_template('spider.html', config=common.CONFIG)


# 爬虫接口
# /spider 表单按钮
@app.route('/action/crawl', methods=['POST'])
def action_crawl():
    url_text = request.form['url_text']
    crawl_pagenum_limit = request.form['crawl_pagenum_limit']
    link_list = [x.strip() for x in url_text.split("\n") if x.strip() != ""]
    if len(link_list) == 0:
        return '请输入有效id'
    crawl_pagenum_limit_int = 100
    if crawl_pagenum_limit.isnumeric() and int(crawl_pagenum_limit) <= 100:
        crawl_pagenum_limit_int = int(crawl_pagenum_limit)
    for link in link_list:
        QUEUE.put((
            "crawl_by_url",
            (link, crawl_pagenum_limit_int)
        ))
    return redirect(url_for("page_spider"))


# 爬虫精确接口 确定到页面类型
# /movie/linkid 详情页抓取按钮
@app.route('/action/crawl/accurate', methods=['POST'])
def action_crawl_accurate():
    global QUEUE, SQL_CACHE, SPIDER_AVMO
    page_type = request.form['page_type']
    keyword = request.form['keyword']
    if page_type not in ['movie', 'star', 'genre', 'series', 'studio', 'label', 'director', 'search']:
        return 'wrong'
    QUEUE.put((
        "crawl_accurate",
        (page_type, keyword, 1, 100, common.get_exist_linkid(page_type, keyword))
    ))
    return '正在下载...'


# 演员爬虫接口
# /actresses 演员页全量按钮，演员页指定按钮
# /star/linkid 更新按钮
@app.route('/action/crawl/star', methods=['POST'])
def action_crawl_star():
    global QUEUE, SPIDER_AVMO
    linkid = request.form['linkid']

    if linkid == 'all':
        star_list = query_sql("SELECT linkid,name FROM av_stars")
        for item in star_list:
            # 增量更新
            QUEUE.put((
                "crawl_accurate",
                ('star', item["linkid"], 1, 100, common.get_exist_linkid("star", item["linkid"]))
            ))
        return '正在下载({})...'.format(','.join([x['name'] for x in star_list]))

    if not is_linkid(linkid):
        return '请输入有效id'
    star_list = query_sql("SELECT linkid,name FROM av_stars WHERE linkid='{}'".format(linkid))
    # 全量更新
    QUEUE.put((
        "crawl_accurate",
        ("star", linkid, 1, 100, common.get_exist_linkid("star", linkid))
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
    global QUEUE
    # 计算当前等待中的任务
    queue_list = []
    for item in QUEUE.queue:
        tmp = {
            "url": "",
            "page_limit": None
        }
        if item[0] == "crawl_by_url":
            tmp["url"] = item[1][0]
            if "/movie/" not in item[1][0]:
                tmp["page_limit"] = item[1][1]

        if item[0] == "crawl_accurate":
            tmp["url"] = common.get_url(item[1][0], item[1][1], item[1][2])
            tmp["page_limit"] = item[1][3]

        if item[0] == "crawl_genre":
            tmp["url"] = common.get_url("genre")

        queue_list.append(tmp)
    return json.dumps({
        "last_insert_list": SPIDER_AVMO.get_last_insert_list(),
        "queue_list": queue_list
    })


# 磁盘扫描工具
@app.route('/scandisk')
def page_scandisk():
    if 'path_target' not in request.values or 'file_target' not in request.values:
        return render_template('scandisk.html', config=common.CONFIG)

    path_target = request.values['path_target']
    path_target = upper_path(path_target)
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
            "SELECT key,val FROM av_extend WHERE extend_name='movie_res' AND (val LIKE '_:\\%' OR val LIKE '/%')",
            False)
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

        now_path = upper_path(os.path.join(root, file))
        av_check = re.search(AV_FILE_REG, file)
        if file_target != "mp4" or not av_check:
            file_res.append({
                'file_path': now_path,
                'file_target': file_target,
            })
            continue

        # 格式化avid
        av_id = av_check.group(0).upper()
        exist = (
                av_id in extend_file_list and now_path in extend_file_list[av_id])
        info = ''
        if exist:
            info += span_color("[已存储路径]", "green")
        else:
            info += span_color("[未存储路径]", "red")

        file_res.append({
            'file_path': now_path,
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
                file_res[i]['info'] += span_color("[影片已抓取]", "green")
            else:
                file_res[i]['info'] += span_color("[影片未抓取]", "red")
        file_res[i]['info'] = file_res[i]['info'].strip(',')

    return render_template('scandisk.html', file_res=file_res, av_data_map=av_data_map, file_target=file_target,
                           path_target=path_target, config=common.CONFIG)


# 本地打开
@app.route('/action/explorer')
def action_explorer():
    # 打开指定路径
    os.startfile(request.values["path"])
    return 'ok'


# 添加扩展信息接口
@app.route('/action/extend/insert')
def action_extend_insert():
    extend_name = request.values["extend_name"]
    key = request.values["key"]
    val = request.values["val"]
    biz_name = ""
    # 格式化
    if extend_name == "movie_res":
        # key目前只会存avid所以upper无碍
        key = key.upper()
        val = upper_path(val)
        biz_name = "资源"

    if extend_name == "like":
        biz_name = "收藏"

    val_list = select_extend_value(extend_name, key)
    if val in val_list:
        return "已存在不能重复添加"
    else:
        sqltext = "INSERT INTO av_extend (extend_name,key,val) VALUES ('{}','{}','{}')".format(
            extend_name, key, val
        )
        execute_sql(sqltext)
        return biz_name + '已添加'


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
    return 'star已删除'


# 标题翻译
@app.route('/action/translate')
def action_translate():
    tmp = request.values["words"].split(' ')
    tmp.pop(0)
    input_text = ''.join(tmp)

    res = requests.post('http://wap.youdao.com/translate',
                        data={'inputtext': input_text, 'type': 'JA2ZH_CN'})
    if res.status_code != 200 or len(res.text) < 20000:
        return "出现错误.." + input_text
    tt = re.findall('<ul id="translateResult">(.*?)</ul>',
                    res.text, re.DOTALL)
    if not tt:
        return "出现错误.." + input_text
    return tt[0].strip()[4:-5]


# 分析演员
@app.route('/action/analyse/star/<linkid>')
def action_analyse_star(linkid=''):
    sql = "SELECT * FROM av_list WHERE stars_url like '%|{}%';".format(linkid)
    data = query_sql(sql, False)
    genre_all = []
    stars_all = []
    minute_sum = 0
    for row in data:
        genre_all.extend(row["genre"].strip('|').split("|"))
        stars_all.extend(row["stars"].strip('|').split("|"))
        minute_sum = minute_sum + int(row["len"])

    genre_counter = collections.OrderedDict(
        sorted(collections.Counter(genre_all).items(), key=lambda x: x[1], reverse=True))
    stars_counter = collections.OrderedDict(
        sorted(collections.Counter(stars_all).items(), key=lambda x: x[1], reverse=True))

    genre_list = []
    stars_list = []

    for key in list(genre_counter.keys()):
        genre_list.append({
            'name': key,
            'count': genre_counter[key]
        })

    head_list = list(stars_counter.keys())[:21]
    for key in list(stars_counter.keys()):
        if key in head_list:
            stars_list.append({
                'name': key,
                'count': stars_counter[key]
            })
    return {
        "starName": stars_list[0]['name'],
        "minuteSum": minute_sum,
        "genreCounter": genre_list,
        "starsCounter": stars_list[1:]
    }


@app.route('/action/change/language')
def action_change_language():
    country = request.values['country']
    common.CONFIG.set("base", "country", country)
    common.config_save(common.CONFIG)
    common.config_init()
    return 'ok'


# 爬虫线程
def spider_thread():
    global QUEUE, SPIDER_AVMO, SQL_CACHE
    print("spider_thread.start")
    while True:
        time.sleep(common.CONFIG.getfloat("spider", "sleep"))

        (function_name, param) = QUEUE.get()
        print("=" * 10, function_name, "=" * 10, "start")
        if function_name == "crawl_accurate":
            print("page_type: {0[0]}, keyword: {0[1]}, page_start: {0[2]}, page_limit: {0[3]}, exist_count: {1}".format(
                param, len(param[4])))
            SPIDER_AVMO.crawl_accurate(param[0], param[1], param[2], param[3], param[4])

        if function_name == "crawl_by_url":
            print("url:{},page_limit:{}".format(param[0], param[1]))
            page_type, keyword, page_start = common.parse_url(param[0])
            SPIDER_AVMO.crawl_accurate(page_type, keyword, page_start, param[1],
                                       common.get_exist_linkid(page_type, keyword))
            # 打开浏览器提醒抓取完成
            if common.CONFIG.getboolean("website", "use_cache"):
                SQL_CACHE.clear()
            page_type, keyword, page_start = common.parse_url(param[0])
            common.open_browser_tab(common.get_local_url(page_type, keyword, page_start))

        if function_name == "crawl_genre":
            SPIDER_AVMO.crawl_genre()

        print("=" * 10, function_name, "=" * 10, "end\n")


def upper_path(path):
    # 如果为windows环境路径，则路径首字母大写
    if re.match("^[a-z]:\\\\", path):
        return path[0].upper() + path[1:]
    else:
        return path


# 上色
def span_color(content, color):
    return '<span style="color:{}">{}</span>'.format(color, content)


# 识别linkid
def is_linkid(linkid: str = ''):
    if linkid is None:
        return False
    return re.match('^[a-z0-9]{16}$', linkid)


# 分页
def pagination(pagenum, count, pageroot, pagelimit):
    pagecount = math.ceil(count / pagelimit)
    total_max = 8
    p1 = pagenum - total_max
    p2 = pagenum + total_max
    pagelist = [x for x in range(p1, p2 + 1) if 0 < x <= pagecount]

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
def select_av_list(column='*', av_list_where=None, limit=(0, 30)):
    if av_list_where is None:
        av_list_where = []
    sql_order_by = "release_date DESC,av_id DESC"
    where_str = "1"
    if av_list_where:
        where_str = " AND ".join(av_list_where)
    sqltext = "SELECT {} FROM av_list WHERE {} GROUP BY av_list.linkid".format(
        column, where_str)
    result = query_sql(sqltext + ' ORDER BY {} LIMIT {},{}'.format(sql_order_by, limit[0], limit[1]))

    # 扩展信息
    extend_list = select_extend_list('movie_res', [x["av_id"] for x in result])
    for i in range(len(result)):
        if result[i]["genre"].strip("|") != "":
            result[i]["genre_desc"] = "(" + result[i]["genre"].strip("|").replace("|", ") (") + ")"

        if result[i]["stars"].strip("|") != "":
            result[i]["stars_desc"] = "(" + result[i]["stars"].strip("|").replace("|", ") (") + ")"

        # 图片地址
        result[i]['smallimage'] = result[i]['bigimage'].replace(
            'pl.jpg', 'ps.jpg')
        # 扩展信息
        if result[i]['av_id'] not in extend_list:
            continue
        for extend in extend_list[result[i]['av_id']]:
            if extend[:6] == "magnet" or extend[:3] == "115":
                result[i]['magnet'] = 1
                continue
            if extend[:4] == "http":
                result[i]['http'] = 1
                continue
            result[i]['file'] = 1
    res_count = query_sql('SELECT COUNT(1) AS count FROM ({})'.format(sqltext))
    return result, res_count[0]['count']


# 获取指定key的扩展信息
def select_extend_list(extend_name, key_list):
    if len(key_list) == 0:
        return {}
    sqltext = "SELECT key,val from av_extend WHERE extend_name='{}' AND key IN ('{}')".format(
        extend_name, "','".join(key_list))
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
    print("SQL EXEC:{}".format(sql))
    DB['CUR'].execute(sql)
    DB['CONN'].commit()


# 查询sql
def query_sql(sql, if_cache=True) -> list:
    cache_key = gen_cache_key(sql)
    # 是否使用缓存
    if common.CONFIG.getboolean("website", "use_cache") and if_cache:
        # 是否有缓存
        if cache_key in SQL_CACHE.keys():
            print('SQL CACHE[{}]'.format(cache_key))
            return SQL_CACHE[cache_key][:]
        else:
            print('SQL EXEC[{}]:{}'.format(cache_key, sql))
            ret = common.fetchall(DB["CUR"], sql)
            if common.CONFIG.getboolean("website", "use_cache") and ret != []:
                SQL_CACHE[cache_key] = ret
            return ret[:]
    else:
        print('SQL EXEC:{}'.format(sql))
        return common.fetchall(DB["CUR"], sql)


# 获取sql中的表名
def get_table_name(sql):
    return list(set(re.findall("(av_[a-z]+)", sql)))


# 获取缓存key
def gen_cache_key(sql):
    return '|'.join(get_table_name(sql)) + ':' + str(binascii.crc32(sql.encode()) & 0xffffffff)


if __name__ == '__main__':
    # 爬虫线程
    thread = threading.Thread(target=spider_thread, args=())
    thread.daemon = True
    thread.start()
    # 打开主页
    if common.CONFIG.getboolean("website", "auto_open_site_on_run"):
        common.open_browser_tab(common.get_local_url())
    # flask应用
    app.run(port=common.DEFAULT_PORT)
