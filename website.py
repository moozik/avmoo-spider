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
import collections
from urllib.parse import quote

from spider import Spider
from common import *

app = Flask(__name__)
app.jinja_env.auto_reload = True
app.config['TEMPLATES_AUTO_RELOAD'] = True

# 文件类型与判定
FILE_TAIL = {
    'mp4': "\\.(mp4|mkv|flv|avi|rm|rmvb|mpg|mpeg|mpe|m1v|mov|3gp|m4v|m3p|wmv|wmp|wm)$",
    'jpg': "\\.(jpg|png|gif|jpeg|bmp|ico)$",
    'mp3': "\\.(mp3|wav|wmv|mpa|mp2|ogg|m4a|aac)$",
    'torrent': "\\.torrent$",
    'zip': "\\.(zip|rar|gz|7z)$",
    'doc': "\\.(xls|xlsx|doc|docx|ppt|pptx|csv|pdf|html|txt)$",
}

# av视频文件判断正则
AV_FILE_REG = "[a-zA-Z]{3,5}-\\d{3,4}"


@app.context_processor
def with_config():
    return {
        'config': CONFIG
    }


# 主页 搜索页
@app.route('/')
@app.route('/page/<int:pagenum>')
@app.route('/search/<keyword>')
@app.route('/search/<keyword>/page/<int:pagenum>')
def index(keyword='', pagenum=1):
    where = av_list_where_build(keyword)

    (result, row_count) = select_av_list(av_list_where=where, page_num=pagenum)
    if keyword != '':
        page_root = '/search/{}'.format(quote(keyword))
    else:
        page_root = ''
    return render_template('index.html', data={"av_list": result, 'page_type': 'index'},
                           page=pagination(pagenum, row_count, page_root), placeholder=keyword,
                           origin_link=get_url("search", quote(keyword), pagenum))


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
                           origin_link=get_url("movie", movie_list[0]["linkid"]))


def av_list_where_build(keyword: str) -> list:
    where = []

    # sql mode
    if keyword[:5] == 'WHERE':
        where.append(keyword[5:])
    # 搜索
    elif keyword.strip() == '':
        return where

    for key_item in keyword.strip().split(' '):
        key_item = key_item.strip()
        # 识别linkid
        if is_linkid(key_item):
            genre = storage("av_genre", {"linkid": [keyword]})
            if genre:
                where.append("genre GLOB '*|{}|*'".format(genre["name"]))
                continue
            
            sql = " OR ".join(["{}='{}'".format(item, key_item) for item in ['linkid', 'director_url', 'studio_url', 'label_url', 'series_url']])
            where.append("({} OR stars_url GLOB '*|{}*')".format(sql, key_item))
            continue
        
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
                "av_id IN (SELECT distinct key FROM av_extend WHERE extend_name='movie_res' AND val LIKE '_:\\%')")
            continue

        if key_item == '收藏影片':
            where.append(
                "av_id IN (SELECT distinct val FROM av_extend WHERE extend_name='like' AND key='av_id')")
            continue

        re_res = re.findall("^(director|studio|label|series|genre|star|group)=(.+)", key_item)
        if re_res:
            page_type = re_res[0][0]
            item_keyword = re_res[0][1]
            where.append(get_where_by_page_type(page_type, item_keyword))
            continue

        where.append(search_where(key_item))
    return where


# 构造电影页
def movie_build(movie_data):
    # 提前返回
    if 'build' in movie_data:
        return movie_data
    # 修复数据
    if len(movie_data["genre"]) > 0 and movie_data["genre"][0] != '|':
        execute(
            "update av_list set genre=('|' || genre || '|')  where genre != '' and genre not like '|%'")
    # 修复数据 20200212
    if len(movie_data["stars"]) > 0 and movie_data["stars"][-1] != '|':
        execute(
            "update av_list set stars=(stars || '|')  where stars != '' and stars not like '%|'")
    # 系列
    if movie_data['genre'] != "":
        movie_data['genre_list'] = movie_data['genre'][1:].split('|')

    # 演员
    if movie_data['stars_url'] != "" and not isinstance(movie_data['stars_url'], list):
        movie_data['stars_url'] = movie_data['stars_url'].strip('|').split("|")
        movie_data['stars'] = movie_data['stars'].strip('|').split("|")

        sqltext = "SELECT linkid,name,headimg FROM av_stars WHERE linkid IN ('{}')".format(
            "','".join(movie_data['stars_url'])
        )
        movie_data['stars_data'] = query_sql(sqltext)
        # 其他所有演员
        if len(movie_data['stars_data']) < len(movie_data['stars_url']):
            movie_data['stars_map'] = []
            linkid_list = [x["linkid"] for x in movie_data['stars_data']]
            for i in range(len(movie_data['stars_url'])):
                if movie_data['stars_url'][i] in linkid_list:
                    continue
                movie_data['stars_map'].append({
                    "linkid": movie_data['stars_url'][i],
                    "name": movie_data['stars'][i]
                })

    # 图片
    movie_data['imglist'] = []
    if movie_data['image_len'] != '0':
        count = int(movie_data['image_len'])
        img_url = CONFIG.get("website", "cdn") + '/digital/video' + movie_data['bigimage'].replace('pl.jpg', '')
        for i in range(1, count + 1):
            movie_data['imglist'].append({
                'small': '{}-{}.jpg'.format(img_url, i),
                'big': '{}jp-{}.jpg'.format(img_url, i)
            })

    # 影片资源
    movie_data['movie_resource_list'] = storage_col("av_extend", {"extend_name": "movie_res", "key": [movie_data['av_id']]}, "val")

    movie_data['av_group'] = movie_data['av_id'].split('-', 1)[0]

    # 标记
    movie_data['build'] = True
    return movie_data


@app.route('/group')
@app.route('/group/page/<int:page_num>')
def page_group(page_num=1):
    page_limit = CONFIG.getint('website', 'group_page_limit')
    order_by = CONFIG.get('website', 'group_page_order_by')
    if order_by not in ['release_date', 'count']:
        order_by = 'count'
    sql_text = '''
    SELECT number,release_date,bigimage,av_id,count(1) AS count FROM(
    SELECT
    substr(av_id, 0, instr(av_id, '-')) AS number,
    release_date,bigimage,av_id
    FROM av_list
    ORDER BY release_date DESC,av_id DESC
    )
    GROUP BY number
    ORDER BY {} DESC
    LIMIT {},{}
    '''.format(
        order_by, (page_num - 1) * page_limit, page_limit
    )
    count_res = query_sql(
        "SELECT count(1) AS co FROM (SELECT DISTINCT substr(av_id, 0, instr(av_id, '-')) FROM av_list)")
    result = query_sql(sql_text)
    for i in range(len(result)):
        # 图片地址
        result[i]['smallimage'] = result[i]['bigimage'].replace(
            'pl.jpg', 'ps.jpg')
    return render_template('group.html', data=result, page=pagination(page_num, count_res[0]['co'], '/group', page_limit))


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
@app.route('/group/<keyword>')
@app.route('/group/<keyword>/page/<int:pagenum>')
def search(keyword='', pagenum=1):
    if pagenum < 1:
        return redirect(url_for('index'), 404)
    placeholder = ""
    page_type = request.path.split('/')[1]
    origin_link = get_url(page_type, keyword, pagenum)
    where = []
    if page_type in ['director', 'studio', 'label', 'series']:
        where = ["av_list.{}_url='{}'".format(page_type, keyword)]

    if page_type == 'genre':
        if is_linkid(keyword):
            sql = "SELECT * FROM av_genre WHERE linkid='{}'".format(keyword)
        else:
            sql = "SELECT * FROM av_genre WHERE name='{}'".format(keyword)
        ret = fetchall(sql)
        if len(ret) > 0:
            where = ["av_list.genre LIKE '%|{}|%'".format(ret[0]['name'])]
            placeholder = ret[0]['name']
            origin_link = get_url(page_type, ret[0]['linkid'], pagenum)

    if page_type == 'group':
        placeholder = keyword
        where = ["av_list.av_id LIKE '{}-%'".format(keyword)]
        origin_link = get_url("search", keyword, pagenum)

    if page_type == 'star':
        where = ["av_list.stars_url LIKE '%|{}%'".format(keyword)]

    page_root = '/{}/{}'.format(page_type, keyword)
    (result, row_count) = select_av_list(av_list_where=where, page_num=pagenum)

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

    return render_template('index.html', data={'av_list': result, 'av_stars': star_data, 'page_type': page_type, 'keyword': keyword},
                           page=pagination(pagenum, row_count, page_root), placeholder=placeholder,
                           origin_link=origin_link)


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
                           page={'pageroot': "/genre", 'count': len(av_genre_res)}, origin_link=get_url("genre"))


# 演员页
@app.route('/actresses')
@app.route('/actresses/page/<int:pagenum>')
def like_stars(pagenum=1):
    page_limit = CONFIG.getint("website", "actresses_page_limit")
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

    return render_template('actresses.html', data=result,
                           page=pagination(pagenum, len(DATA_STORAGE["av_stars"]), "/actresses", page_limit),
                           origin_link=get_url("actresses"))


# 配置页
@app.route('/config')
def page_config():
    return render_template('config.html')


# 修改配置
@app.route('/action/config', methods=['POST'])
def action_config():
    # 表单存在的配置项name
    for name in request.form:
        (section, option) = name.split(".")
        CONFIG.set(section=section, option=option, value=request.form[name])
    config_save(CONFIG)
    config_init()
    print("new config:", list(request.form))
    return redirect(request.referrer)


# 爬虫页
@app.route('/spider')
def page_spider():
    return render_template('spider.html')


# 爬虫接口
# /spider 表单按钮
@app.route('/action/crawl', methods=['POST'])
def action_crawl():
    url_text = request.form['url_text']
    crawl_page_num_limit = request.form['crawl_page_num_limit']
    link_list = [x.strip() for x in url_text.split("\n") if x.strip() != ""]
    if len(link_list) == 0:
        return '请输入有效id'
    crawl_page_num_limit_int = 100
    if crawl_page_num_limit.isnumeric() and int(crawl_page_num_limit) <= 100:
        crawl_page_num_limit_int = int(crawl_page_num_limit)
    for link in link_list:
        QUEUE.put((
            "crawl_by_url",
            (link, crawl_page_num_limit_int)
        ))
    return redirect(url_for("page_spider"))


# 爬虫精确接口 确定到页面类型
# /movie/linkid 详情页抓取按钮
@app.route('/action/crawl/accurate', methods=['POST'])
def action_crawl_accurate():
    page_type = request.form['page_type']
    keyword = request.form['keyword']
    if page_type not in ['movie', 'star', 'genre', 'series', 'studio', 'label', 'director', 'search', 'group', 'allStar']:
        return 'wrong'

    if page_type == 'group':
        page_type = 'search'
        keyword = keyword + '-'

    if page_type == 'allStar':
        star_list = query_sql("SELECT linkid,name FROM av_stars")
        for item in star_list:
            # 遍历所有演员
            QUEUE.put((
                "crawl_accurate",
                ('star', item["linkid"], 1, 100, get_exist_linkid("star", item["linkid"]))
            ))
        return '正在下载({})...'.format(len(star_list))

    QUEUE.put((
        "crawl_accurate",
        (page_type, keyword, 1, 100, get_exist_linkid(page_type, keyword))
    ))
    return '正在下载...'


# 类目爬虫接口
@app.route('/action/crawl/genre')
def action_crawl_genre():
    QUEUE.put((
        "crawl_genre",
        ()
    ))
    return '正在下载...'


@app.route('/action/last/insert')
def action_last_insert():
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
            tmp["url"] = get_url(item[1][0], item[1][1], item[1][2])
            tmp["page_limit"] = item[1][3]

        if item[0] == "crawl_genre":
            tmp["url"] = get_url("genre")

        queue_list.append(tmp)
    return json.dumps({
        "last_insert_list": Spider().get_last_insert_list(),
        "queue_list": queue_list
    })


# 磁盘扫描工具
@app.route('/scandisk')
def page_scandisk():
    if 'path_target' not in request.values or 'file_target' not in request.values:
        return render_template('scandisk.html')

    path_target = request.values['path_target']
    path_target = upper_path(path_target)
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
            "SELECT key,val FROM av_extend WHERE extend_name='movie_res' AND val LIKE '_:\\%' ",
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
        sqltext = "SELECT * FROM av_list WHERE av_id in ('{}')".format(
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
                           path_target=path_target)


# 本地打开
@app.route('/action/explorer')
def action_explorer():
    # 打开指定路径
    os.startfile(request.values["path"])
    return 'ok'


# 添加扩展信息接口
@app.route('/action/extend/insert')
def action_extend_insert():
    data = {
        "extend_name": request.values["extend_name"],
        "key": request.values["key"],
        "val": request.values["val"],
    }

    biz_name = ""
    # 格式化
    if data["extend_name"] == "movie_res":
        # key目前只会存avid所以upper无碍
        data["val"] = upper_path(data["val"])
        biz_name = "资源"

    if data["extend_name"] == "like":
        biz_name = "收藏"

    val_list = storage_col("av_extend", {"extend_name": data["extend_name"], "key": [data["key"]]}, "val")
    
    if data["val"] in val_list:
        return "已存在不能重复添加"
    else:
        DATA_STORAGE["av_extend"].append(data)
        insert("av_extend", [data])
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
    execute(sqltext)
    DATA_STORAGE.clear()
    return '已删除'


# 删除影片 仅限手动调用
@app.route('/action/delete/movie/<linkid>')
def action_delete_movie(linkid=''):
    sqltext = "DELETE FROM av_list WHERE linkid='{}'".format(linkid)
    execute(sqltext)
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
            execute(sqltext)
    sqltext = "DELETE FROM av_stars WHERE linkid='{}'".format(linkid)
    execute(sqltext)
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
@app.route('/analyse/<page_type>/<keyword>')
def action_analyse_star(page_type='', keyword=''):
    sql = "SELECT * FROM av_list WHERE {};".format(get_where_by_page_type(page_type, keyword))
    data = query_sql(sql, False)

    genre_all = []
    stars_all = []
    series_all = []
    minute_sum = 0
    for row in data:
        genre_all.extend(row["genre"].strip('|').split("|"))
        stars_all.extend(row["stars"].strip('|').split("|"))
        if row["series"]:
            series_all.append(row["series"])
        minute_sum = minute_sum + int(row["len"])

    genre_counter = collections.OrderedDict(
        sorted(collections.Counter(genre_all).items(), key=lambda x: x[1], reverse=True))
    stars_counter = collections.OrderedDict(
        sorted(collections.Counter(stars_all).items(), key=lambda x: x[1], reverse=True))
    series_counter = collections.OrderedDict(
        sorted(collections.Counter(series_all).items(), key=lambda x: x[1], reverse=True))

    genre_counter = [{'name': x.replace(' ', '__'), 'count': genre_counter[x]} for x in genre_counter]
    stars_counter = [{'name': x, 'count': stars_counter[x]} for x in stars_counter if x != '']
    series_counter = [{'name': x.replace(' ', '__'), 'count': series_counter[x]} for x in series_counter if x != '']

    # group genre 为默认
    analyse_name = keyword
    if page_type == 'star':
        analyse_name = stars_counter[0]['name']
    if page_type in ['director', 'studio', 'label', 'series']:
        analyse_name = data[0][page_type]

    data = {
        "analyse_name": analyse_name,
        "page_type": page_type,
        "keyword": keyword,
        "minute_sum": minute_sum,
        "genre_counter": genre_counter,
        "stars_counter": stars_counter,
        "series_counter": series_counter
    }
    return render_template('analyse.html', data=data)


@app.route('/action/change/language')
def action_change_language():
    country = request.values['country']
    CONFIG.set("base", "country", country)
    config_save(CONFIG)
    config_init()
    return 'ok'


def get_where_by_page_type(page_type: str, keyword: str) -> str:
    keyword = keyword.replace('__', ' ')

    if page_type == 'group':
        return "av_id like '{}-%'".format(keyword)
    
    if page_type == 'genre':
        if is_linkid(keyword):
            genre = storage_col("av_genre", {"linkid": [keyword]}, "name")
            keyword = genre[0]
        return "genre like '%|{}|%'".format(keyword)
    
    if page_type == 'star':
        if is_linkid(keyword):
            return "stars_url like '%|{}%'".format(keyword)
        else:
            return "stars like '%|{}|%'".format(keyword)

    if page_type in ['director', 'studio', 'label', 'series']:
        if is_linkid(keyword):
            return "{}_url = '{}'".format(page_type, keyword)
        else:
            return "{} = '{}'".format(page_type, keyword)


def upper_path(path: str) -> str:
    # 如果为windows环境路径，则路径首字母大写
    if re.match("^[a-z]:\\\\", path):
        return path[0].upper() + path[1:]
    else:
        return path


# 上色
def span_color(content, color):
    return '<span style="color:{}">{}</span>'.format(color, content)


# 识别linkid
def is_linkid(linkid: str = '') -> bool:
    if linkid is None:
        return False
    return re.match('^[a-z0-9]{16}$', linkid)


# 分页
def pagination(pagenum, count, pageroot, pagelimit = None) -> dict:
    if not pagelimit:
        # 默认为主页的limit
        pagelimit = CONFIG.getint("website", "page_limit")
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
def select_av_list(av_list_where: list, page_num: int):
    # 每页展示的数量
    page_limit = CONFIG.getint("website", "page_limit")

    sql_order_by = "release_date DESC,av_id DESC"
    where_str = "1"
    if av_list_where:
        where_str = " AND ".join(av_list_where)
    sqltext = "SELECT * FROM av_list WHERE {} ".format(where_str)
    result = query_sql(sqltext + ' ORDER BY {} LIMIT {},{}'.format(sql_order_by, (page_num - 1) * page_limit, page_limit))

    for i in range(len(result)):
        # hover框类目信息
        if result[i]["genre"].strip("|") != "":
            result[i]["genre_desc"] = "(" + result[i]["genre"].strip("|").replace("|", ") (") + ")"
        # hover框演员信息
        if result[i]["stars"].strip("|") != "":
            result[i]["stars_desc"] = "(" + result[i]["stars"].strip("|").replace("|", ") (") + ")"

        # 图片地址
        result[i]['smallimage'] = result[i]['bigimage'].replace(
            'pl.jpg', 'ps.jpg')
        
        # 扩展信息
        extend_list = storage_col("av_extend", {"extend_name": "movie_res", "key": [result[i]['av_id']]}, "val")
        if not extend_list:
            continue
        for extend in extend_list:
            if extend[:6] == "magnet" or extend[:3] == "115":
                result[i]['magnet'] = 1
                continue
            if extend[:4] == "http":
                result[i]['http'] = 1
                continue
            result[i]['file'] = 1
    res_count = query_sql('SELECT COUNT(1) AS count FROM ({})'.format(sqltext))
    return result, res_count[0]['count']


# 遍历文件
def walk_all_files(path_target):
    for root, dirs, files in os.walk(path_target):
        for file in files:
            yield root, file


if __name__ == '__main__':
    pass
