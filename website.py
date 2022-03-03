#!/usr/bin/env python3
# -*- coding:utf-8 -*-
import collections
import datetime
import json
import math
import re
import time

from flask import Flask
from flask import redirect
from flask import render_template
from flask import request
from flask import url_for

from common import *
from spider import Spider

app = Flask(__name__)
app.jinja_env.auto_reload = True
app.config['TEMPLATES_AUTO_RELOAD'] = True

SPIDER = Spider()

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


def run():
    print("website.run")
    if CONFIG.getboolean("base", "debug_mode"):
        app.debug = True
    app.run(port=CONFIG.getint("base", "port"), processes=1)


@app.context_processor
def with_config():
    return {
        'config': CONFIG,
        'page_type_map': PAGE_TYPE_MAP,
        'country_map': COUNTRY_MAP,
    }


@app.template_filter("quote")
def do_quote(val):
    return quote(val, safe="")


# 主页 搜索页
@app.route('/')
@app.route('/page/<int:page_num>')
@app.route('/search/<path:keyword>')
@app.route('/search/<path:keyword>/page/<int:page_num>')
def index(keyword='', page_num=1):
    where = search_where_build(keyword)

    (result, row_count) = select_av_list(av_list_where=where, page_num=page_num)
    if keyword != '':
        page_root = '/search/{}'.format(quote(keyword))
    else:
        page_root = ''
    return render_template('index.html',
        data={
            "av_list": result,
            'page_type': 'index'
        },
        frame_data={
            'title': keyword,
            'placeholder': keyword,
            'origin_link': get_url("search", quote(keyword), page_num),
            'page': pagination(page_num, row_count, page_root)
        })
       


# 演员页
@app.route('/actresses')
@app.route('/actresses/page/<int:page_num>')
def page_actresses(page_num=1):
    page_limit = CONFIG.getint("website", "actresses_page_limit")
    sql_text = '''
    SELECT av_stars.*,COUNT(av_list.release_date) AS movie_count,av_list.release_date
    FROM av_stars
    LEFT JOIN (
        SELECT release_date,stars_url
        FROM av_list
        ORDER BY release_date desc
    )av_list ON INSTR(av_list.stars_url, av_stars.linkid) > 0
    GROUP BY av_stars.linkid
    ORDER BY av_list.release_date DESC
    '''
    # 性能模式简化sql
    if CONFIG.getboolean("website", "efficiency_mode"):
        sql_text = "SELECT * FROM av_stars"

    sql_result = "{} LIMIT {},{}".format(sql_text, (page_num - 1) * page_limit, page_limit)
    result = query_sql(sql_result)
    count = query_sql('SELECT COUNT(*) AS co FROM av_stars')[0]['co']
    return render_template('actresses.html',
        data={
            'av_stars': result
        },
        frame_data={
            'title': '女优',
            'origin_link': get_url("actresses"),
            'page': pagination(page_num, count, "/actresses", page_limit)
        })


# 番号页
@app.route('/series')
@app.route('/series/page/<int:page_num>')
@app.route('/studio')
@app.route('/studio/page/<int:page_num>')
@app.route('/label')
@app.route('/label/page/<int:page_num>')
@app.route('/group')
@app.route('/group/page/<int:page_num>')
def page_group(page_num=1):
    # 页面类型
    page_type = request.path.split('/')[1]
    result = group_data(page_type, page_num)
    
    if page_type == "group":
        count_res = query_sql(
            "SELECT count(1) AS co FROM (SELECT DISTINCT substr(av_id, 0, instr(av_id, '-')) FROM av_list)")
    else:
        count_res = query_sql(
            "SELECT count(1) AS co FROM av_list WHERE {} != ''".format(page_type + '_url'))
    return render_template('group.html',
        data={
            "list": result,
            "page_type": page_type,
        },
        frame_data={
            'title':PAGE_TYPE_MAP[page_type]['name'],
            'page':pagination(page_num, count_res[0]['co'], '/' + page_type, CONFIG.getint('website', 'group_page_limit'))
        })


# 构造group页面data todo 加参数给like用
def group_data(page_type: str,page_num: int,where: str = '1'):
    page_limit = CONFIG.getint('website', 'group_page_limit')
    order_by = CONFIG.get('website', 'group_page_order_by')
    if order_by not in ['release_date', 'count']:
        order_by = 'count'

    if page_type == "group":
        sql_text = '''
        SELECT linkid,linkid AS title,release_date,bigimage,av_id,count(1) AS count FROM(
        SELECT
        substr(av_id, 0, instr(av_id, '-')) AS linkid,
        release_date,bigimage,av_id
        FROM av_list
        WHERE {3}
        ORDER BY release_date DESC,av_id DESC
        )
        GROUP BY linkid
        ORDER BY {0} DESC
        LIMIT {1},{2}
        '''.format(
            order_by,
            (page_num - 1) * page_limit,
            page_limit,
            where,
        )
    else:
        sql_text = '''
        SELECT *,count(*) AS count FROM(SELECT {1} AS linkid,{0} AS title,release_date,bigimage,av_id FROM av_list
        WHERE {1} != '' AND {5}
        ORDER BY release_date DESC)
        GROUP BY linkid
        ORDER BY {2} DESC
        LIMIT {3},{4}
        '''.format(
            page_type,
            page_type + '_url',
            order_by,
            (page_num - 1) * page_limit,
            page_limit,
            where
        )

    result = query_sql(sql_text)
    for i in range(len(result)):
        # 图片地址
        result[i]['smallimage'] = result[i]['bigimage'].replace(
            'pl.jpg', 'ps.jpg')
    return result

# 标签页
@app.route('/genre')
def genre():
    # 获取类目
    av_genre_res = query_sql("SELECT linkid,name,title FROM av_genre")

    # 如果genre为空则抓取
    if not av_genre_res:
        print('spider.genre.fetch')
        insert("av_genre", Spider().crawl_genre())
        return "请刷新"

    # 统计标签个数
    genre_list = []
    for row in query_sql("SELECT genre AS genre FROM av_list"):
        genre_list.extend(list(set(row['genre'].strip("|").split("|"))))
    genre_counter = collections.Counter(genre_list)

    data = {}
    for item in av_genre_res:
        if item['title'] not in data:
            data[item['title']] = []
        # 组装标签数据
        if item['name'] in genre_counter:
            item["genre_count"] = genre_counter[item['name']]

        data[item["title"]].append(item)
    data = list(data.values())
    return render_template('genre.html',
        data={
            'av_genre': data
        },
        frame_data={
            'title': PAGE_TYPE_MAP['genre']['name'],
            'origin_link':get_url("genre"),
            'page':{'count': len(av_genre_res)}
        })


# 分类页
@app.route('/director/<linkid>')
@app.route('/director/<linkid>/page/<int:page_num>')
@app.route('/studio/<linkid>')
@app.route('/studio/<linkid>/page/<int:page_num>')
@app.route('/label/<linkid>')
@app.route('/label/<linkid>/page/<int:page_num>')
@app.route('/series/<linkid>')
@app.route('/series/<linkid>/page/<int:page_num>')
def search_normal(linkid='', page_num=1):
    # 页面类型
    page_type = request.path.split('/')[1]
    # 原始链接
    origin_link = get_url(page_type, linkid, page_num)
    # 翻页链接
    page_root = '/{}/{}'.format(page_type, linkid)

    # 条件
    where = PAGE_TYPE_MAP[page_type]['where'].format(linkid)
    # 查询
    (result, row_count) = select_av_list(av_list_where=[where], page_num=page_num)
    # 判空
    if not result:
        return '没找到数据<br>{}'.format(a_tag_build(get_url(page_type, linkid)))
    
    # 设置默认搜索词
    placeholder = result[0][page_type]
    
    # 是否收藏当前页面
    is_like = False
    if PAGE_TYPE_MAP[page_type]["like_enable"] and storage("av_extend", {"extend_name": "like", "key":PAGE_TYPE_MAP[page_type]["key"], "val": linkid}):
        is_like = True
    
    return render_template('index.html',
        data={
            'av_list': result,
            'page_type': page_type,
            'linkid': linkid,
            'is_like': is_like
        },
        frame_data={
            'title': placeholder,
            'placeholder': placeholder,
            'origin_link': origin_link,
            'page': pagination(page_num, row_count, page_root)
        })


# 分类页
@app.route('/star/<keyword>')
@app.route('/star/<keyword>/page/<int:page_num>')
@app.route('/genre/<keyword>')
@app.route('/genre/<keyword>/page/<int:page_num>')
@app.route('/group/<keyword>')
@app.route('/group/<keyword>/page/<int:page_num>')
def search_other(keyword='', page_num=1):
    # group 和 genre 的linkid不是标准linkid
    page_type = request.path.split('/')[1]
    page_root = '/{}/{}'.format(page_type, keyword)

    placeholder = ""
    linkid = keyword
    origin_link = CONFIG.get("base", "avmoo_site")

    if page_type == 'genre':
        keyword = storage("av_genre", {"linkid": keyword})[0]['name']
        placeholder = keyword
        origin_link = get_url('genre', keyword)

    if page_type == 'group':
        placeholder = keyword
        origin_link = get_url("search", keyword)

    if page_type == 'star':
        origin_link = get_url("star", keyword)

    where = PAGE_TYPE_MAP[page_type]['where'].format(keyword)

    # 查询
    (result, row_count) = select_av_list(av_list_where=[where], page_num=page_num)

    star_data = None
    if page_type == 'star':
        if len(result) > 0 and result[0]["stars"] != "":
            placeholder = result[0]["stars"].split("|")[result[0]["stars_url"].split("|").index(keyword)]

        star_data = query_sql("SELECT * FROM av_stars WHERE linkid='{}'".format(keyword))
        if len(star_data) == 1:
            star_data = star_data[0]
            # 计算年龄
            if star_data['birthday'] != '':
                sp = star_data['birthday'].split('-')
                birthday_data = datetime.date(int(sp[0]), int(sp[1]), int(sp[2]))
                star_data['age'] = math.ceil(
                    (datetime.date.today() - birthday_data).days / 365)

    # 是否收藏当前页面
    is_like = False
    if PAGE_TYPE_MAP[page_type]["like_enable"] and storage("av_extend", {"extend_name": "like", "key":PAGE_TYPE_MAP[page_type]["key"], "val": keyword}):
        is_like = True

    return render_template('index.html',
        data={
            'av_list': result,
            'av_stars': star_data,
            'page_type': page_type,
            'linkid': linkid,
            'is_like': is_like
        },
        frame_data={
            'title': placeholder,
            'placeholder': placeholder,
            'origin_link': origin_link,
            'page': pagination(page_num, row_count, page_root)
        })


# 电影页
@app.route('/movie/<linkid>')
def movie(linkid=''):
    where = PAGE_TYPE_MAP['movie']['where'].format(linkid)
    movie_list = query_sql("SELECT * FROM av_list WHERE {}".format(where))
    if not movie_list:
        return "没找到影片<br>{}".format(linkid, a_tag_build(get_url('movie', linkid)))
    movie_data = movie_build(movie_list[0])
    return render_template('movie.html',
        data=movie_data,
        frame_data={
            'title': movie_data['title'],
            'origin_link': get_url("movie", movie_list[0]["linkid"])
        })

# 收藏页 影片
@app.route('/like/movie')
@app.route('/like/movie/page/<int:page_num>')
def page_like_movie(page_num=1):
    page_root = '/like/movie'

    where = "av_id IN (SELECT distinct val FROM av_extend WHERE extend_name='like' AND key='av_id')"
    (result, row_count) = select_av_list(av_list_where=[where], page_num=page_num)
    
    return render_template('index.html',
        data={
            "av_list": result,
            'page_type': 'like'
        },
        frame_data={
            'title': '收藏影片',
            'page': pagination(page_num, row_count, page_root)
        })


# 收藏页 番号 系列 发行 制作
@app.route('/like/<page_type>')
@app.route('/like/<page_type>/page/<int:page_num>')
def page_like(page_type='', page_num=1):
    pmap = PAGE_TYPE_MAP[page_type]
    if not pmap['like_enable']:
        return "error"
    
    page_root = '/like/' + page_type
    where = ''
    # 收藏sql
    extend_sql = "SELECT distinct val FROM av_extend WHERE extend_name='like' AND key='{}'".format(PAGE_TYPE_MAP[page_type]['key'])
    
    if page_type == 'group':
        where = "substr(av_id, 0, instr(av_id, '-')) IN ({})".format(extend_sql)
    
    if page_type in ['series', 'studio', 'label']:
        where = "{} IN ({})".format(PAGE_TYPE_MAP[page_type]['key'], extend_sql)

    count = len(storage("av_extend", {"extend_name":'like','key': PAGE_TYPE_MAP[page_type]['key']}))
    return render_template('group.html',
        data={
            "list": group_data(page_type, page_num, where),
            "page_type": page_type,
        },
        frame_data={
            'title': '收藏' + PAGE_TYPE_MAP[page_type]['name'],
            'page': pagination(page_num, count, page_root, CONFIG.getint('website', 'group_page_limit'))
        })


# 爬虫页
@app.route('/spider')
def page_spider():
    return render_template('spider.html',
        frame_data={
            'title': '爬虫'
        })


# 配置页
@app.route('/config')
def page_config():
    return render_template('config.html',
        frame_data={
            'title': '配置'
        })


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


# 分析
@app.route('/analyse/<page_type>/<keyword>')
def action_analyse_star(page_type='', keyword=''):
    sql = "SELECT * FROM av_list WHERE {};".format(page_type_datail_where_build(page_type, keyword))
    data = fetchall(sql)
    if not data:
        return "没找到数据<br>{}".format(a_tag_build(get_url(page_type, keyword)))

    genre_all = []
    stars_all = []
    series_all = []
    studio_all = []
    label_all = []
    minute_sum = 0
    for row in data:
        genre_all.extend(row["genre"].strip('|').split("|"))
        stars_all.extend(row["stars"].strip('|').split("|"))
        if row["series"]:
            series_all.append(row["series"])
        if row["studio"]:
            studio_all.append(row["studio"])
        if row["label"]:
            label_all.append(row["label"])

        minute_sum = minute_sum + int(row["len"])

    genre_counter = collections.OrderedDict(
        sorted(collections.Counter(genre_all).items(), key=lambda x: x[1], reverse=True))
    stars_counter = collections.OrderedDict(
        sorted(collections.Counter(stars_all).items(), key=lambda x: x[1], reverse=True))
    series_counter = collections.OrderedDict(
        sorted(collections.Counter(series_all).items(), key=lambda x: x[1], reverse=True))
    studio_counter = collections.OrderedDict(
        sorted(collections.Counter(studio_all).items(), key=lambda x: x[1], reverse=True))
    label_counter = collections.OrderedDict(
        sorted(collections.Counter(label_all).items(), key=lambda x: x[1], reverse=True))

    genre_counter = [{'name': x, 'count': genre_counter[x]} for x in genre_counter]
    stars_counter = [{'name': x, 'count': stars_counter[x]} for x in stars_counter if x != '']
    series_counter = [{'name': x, 'count': series_counter[x]} for x in series_counter if x != '']
    studio_counter = [{'name': x, 'count': studio_counter[x]} for x in studio_counter if x != '']
    label_counter = [{'name': x, 'count': label_counter[x]} for x in label_counter if x != '']

    # group 为默认
    analyse_name = keyword
    if page_type == 'star':
        analyse_name = stars_counter[0]['name']

    if page_type == 'genre':
        analyse_name = genre_counter[0]['name']

    if page_type in ['director', 'studio', 'label', 'series']:
        analyse_name = data[0][page_type]

    data = {
        "analyse_name": analyse_name,
        "page_type": page_type,
        "keyword": keyword,
        "minute_sum": minute_sum,
        "genre_counter": genre_counter,
        "stars_counter": stars_counter,
        "series_counter": series_counter,
        "studio_counter": studio_counter,
        "label_counter": label_counter
    }
    return render_template('analyse.html',
        data=data,
        frame_data={
            'title': '[{}]分析结果'.format(data['analyse_name'])
        })


# 构造where条件
def search_where_build(keyword: str) -> list:
    where = []
    keyword = keyword.strip()

    if keyword == '':
        return []

    # sql mode
    if keyword[:5] == 'WHERE':
        return [keyword[5:]]

    # 自定义搜索结构
    re_res = re.findall("((director|studio|label|series|genre|star|group)\\[(.+?)\\])", keyword)
    for item in re_res:
        where.append(page_type_datail_where_build(item[1], item[2]))
        keyword = keyword.replace(item[0], '')

    keyword = keyword.strip()
    # 通用搜索
    for key_item in keyword.strip().split(' '):
        if key_item == '':
            continue

        # 识别linkid
        if is_linkid(key_item):
            genre_data = storage("av_genre", {"linkid": [keyword]})
            if genre_data:
                where.append("genre GLOB '*|{}|*'".format(genre_data[0]["name"]))
                continue

            sql = " OR ".join(["{}='{}'".format(item, key_item) for item in
                               ['linkid', 'director_url', 'studio_url', 'label_url', 'series_url']])
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

        where.append(search_where(key_item))
    return where

# page_type详情页
def page_type_datail_where_build(page_type: str, keyword: str) -> str:
    keyword = keyword

    if page_type == 'group':
        return "av_id like '{}-%'".format(keyword)

    if page_type == 'genre':
        if is_linkid(keyword):
            keyword = storage("av_genre", {"linkid": [keyword]}, "name")[0]
        return "genre like '%|{}|%'".format(sql_escape(keyword))

    if page_type == 'star':
        if is_linkid(keyword) or re.match("[a-z0-9]{4}", keyword):
            return "stars_url like '%|{}%'".format(keyword)
        else:
            return "stars like '%|{}|%'".format(sql_escape(keyword))

    if page_type in ['director', 'studio', 'label', 'series']:
        if is_linkid(keyword):
            return "{}_url = '{}'".format(page_type, keyword)
        else:
            return "{} = '{}'".format(page_type, sql_escape(keyword))


def page_type_group_where_build(page_type: str) -> str:
    if page_type not in ['movie', 'series', 'studio', 'label']:
        return '1=1'
    

# 构造电影页
def movie_build(movie_data):
    # 修复数据
    if movie_data["genre"] and movie_data["genre"][0] != '|':
        execute("update av_list set genre=('|' || genre || '|')  where genre != '' and genre not like '|%'")
    # 修复数据 20200212
    if movie_data["stars"] and movie_data["stars"][-1] != '|':
        execute("update av_list set stars=(stars || '|')  where stars != '' and stars not like '%|'")
    # 系列
    movie_data['genre_data'] = []
    if movie_data['genre'] != "":
        for item in movie_data['genre'].strip('|').split('|'):
            movie_data['genre_data'].append({
                "linkid": storage("av_genre", {"name":item},"linkid")[0],
                "name": item
            })

    # 演员
    if movie_data['stars_url'] is not None and movie_data['stars_url'] != "" and not isinstance(movie_data['stars_url'],
                                                                                                list):
        movie_data['stars_url'] = movie_data['stars_url'].strip('|').split("|")
        movie_data['stars'] = movie_data['stars'].strip('|').split("|")

        sql_text = "SELECT linkid,name,headimg FROM av_stars WHERE linkid IN ('{}')".format(
            "','".join(movie_data['stars_url'])
        )
        movie_data['stars_data'] = query_sql(sql_text)
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
    movie_data['movie_resource_list'] = storage("av_extend", {"extend_name": "movie_res", "key": [movie_data['av_id']]},
                                                "val")

    movie_data['av_group'] = movie_data['av_id'].split('-', 1)[0]

    # 是否已收藏
    movie_data["is_like"] = False
    if storage("av_extend", {"extend_name": "like", "key": "av_id", "val": movie_data['av_id']}):
        movie_data["is_like"] = True
    
    # 标记
    movie_data['build'] = True
    return movie_data


# 爬虫控制
@app.route('/action/crawl/control/<action>')
def action_crawl_control(action):
    if action == "clean":
        QUEUE.queue.clear()
        return "已清空"

    if action == "exit":
        SPIDER.get_running_work("exit")
        return "已跳过当前任务"


# 爬虫接口
# /spider 表单按钮
@app.route('/action/crawl', methods=['POST'])
def action_crawl():
    url_text = request.form['url_text']
    input_num_limit = request.form['page_limit']
    skip_exist = True
    if request.form['skip_exist'] == "False":
        skip_exist = False
    link_list = [x.strip() for x in url_text.split("\n") if x.strip() != ""]

    if len(link_list) == 0:
        return '请输入有效id'
    page_limit = PAGE_MAX

    if input_num_limit.isnumeric() and int(input_num_limit) <= PAGE_MAX:
        page_limit = int(input_num_limit)

    for link in link_list:
        # 调用搜索查询
        if not re.match("https?://", link):
            # 构造search链接,编码搜索词
            link = get_url("search", quote(link))

        page_type, keyword, page_start = parse_url(link)
        if page_type == "":
            print("wrong link:", link)
            continue
        ret = crawl_accurate(page_type, keyword, page_start, page_limit, skip_exist)

    return redirect(url_for("page_spider"))


# 爬虫精确接口 确定到页面类型
# /genre 更新类目按钮
# /actresses 更新所有影片按钮
# /movie/linkid 详情页重新抓取按钮
# /search/keyword 详情页重新抓取按钮
# /(star|genre|series|studio|label|director|group)/linkid 更新影片按钮
@app.route('/action/crawl/accurate', methods=['POST'])
def action_crawl_accurate():
    return crawl_accurate(request.form['page_type'], request.form['keyword'])


# 爬虫任务统一入口 除了genre
def crawl_accurate(page_type: str, keyword: str = "", page_start: int = 1, page_limit: int = PAGE_MAX,
                   skip_exist: bool = True):
    if page_type not in ['movie', 'star', 'genre', 'series', 'studio', 'label', 'director', 'search', 'popular',
                         'group', 'all_star']:
        return 'wrong'

    if page_type == 'group':
        page_type = 'search'
        keyword = keyword + '-'

    if page_type == 'all_star':
        star_list = query_sql("SELECT linkid,name FROM av_stars")
        for item in star_list:
            # 遍历所有演员
            add_work({
                "page_type": "star",
                "keyword": item["linkid"],
                "skip_exist": True,
            })
        return '排队中({})...'.format(len(star_list))

    if page_type in ['movie', 'star', 'genre', 'series', 'studio', 'label', 'director']:
        if not is_linkid(keyword):
            return
    add_work({
        "page_type": page_type,
        "keyword": keyword,
        "page_start": page_start,
        "page_limit": page_limit,
        "skip_exist": skip_exist,
    })
    return '排队中...'


# 添加任务信息进队列,补充url信息
def add_work(work: dict):
    data = {
        "page_type": work["page_type"],
        "keyword": work["keyword"],
        "page_start": 1,
        "page_limit": PAGE_MAX,
        "skip_exist": True,
    }
    for key in ["page_start", "page_limit", "skip_exist"]:
        if key in work:
            data[key] = work[key]
    data["url"] = get_url(work["page_type"], work["keyword"], work["page_start"])
    QUEUE.put(data)


@app.route('/action/last/insert')
def action_last_insert():
    global SPIDER
    return json.dumps({
        "last_insert_list": SPIDER.get_last_insert_list(),
        "wait_work": list(QUEUE.queue),
        "running_work": SPIDER.get_running_work(),
        "done_work": SPIDER.get_done_work(),
    })


# 磁盘扫描工具
@app.route('/scandisk')
def page_scandisk():
    if 'path_target' not in request.values or 'file_target' not in request.values:
        return render_template('scandisk.html', frame_data={'title': '扫描硬盘'})

    path_target = request.values['path_target']
    path_target = upper_path(path_target)
    if not os.path.exists(path_target):
        return render_template('scandisk.html', frame_data={'title': '扫描硬盘'})

    # 文件目标类型
    file_target = request.values['file_target']
    # 路径信息
    file_res = []
    av_data_map = {}
    extend_file_list = {}
    if file_target == "mp4":
        ret = storage("av_extend", {"extend_name": "movie_res"})
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
        exist = (av_id in extend_file_list and now_path in extend_file_list[av_id])
        info = {
            # 是否已存储路径
            "has_res_extend": False,
            # 是否已抓取影片
            "has_fetch_movie": False,
        }
        if exist:
            
            info["has_res_extend"] = True

        file_res.append({
            'file_path': now_path,
            'file_target': file_target,
            'info': info,
            'av_id': av_id,
        })
    if file_target == "mp4":
        av_id_list = [x["av_id"] for x in file_res if "av_id" in x]
        sql_text = "SELECT * FROM av_list WHERE av_id in ('{}')".format(
            "','".join(av_id_list))
        for row in fetchall(sql_text):
            # 图片地址
            row['smallimage'] = row['bigimage'].replace(
                'pl.jpg', 'ps.jpg')
            av_data_map[row["av_id"]] = row

    for i in range(len(file_res)):
        if 'av_id' not in file_res[i]:
            continue
        if file_target == "mp4":
            if file_res[i]['av_id'] in av_data_map:
                file_res[i]['info']['has_fetch_movie'] = True

    return render_template('scandisk.html',
        file_res=file_res,
        av_data_map=av_data_map,
        file_target=file_target,
        path_target=path_target,
        frame_data={'title': '扫描硬盘'})


# 本地打开
@app.route('/action/explorer')
def action_explorer():
    # 打开指定路径
    try:
        os.startfile(request.values["path"])
    except FileNotFoundError as e:
        print('FileNotFoundError,error:', e)
        return '文件未找到'
    return 'ok'


# 添加扩展信息接口
@app.route('/action/extend/insert')
def action_extend_insert():
    data = dict(request.values)
    biz_name = ""
    # 影片资源
    if data["extend_name"] == "movie_res":
        # key目前只会存avid所以upper无碍
        data["val"] = upper_path(data["val"])
        biz_name = "资源"
    # 收藏
    if data["extend_name"] == "like":
        biz_name = "收藏"

    val_list = storage("av_extend", {"extend_name": data["extend_name"], "key": [data["key"]]}, "val")
    
    if data["val"] in val_list:
        return "已存在不能重复添加"
    else:
        DATA_STORAGE["av_extend"].append(data)
        insert("av_extend", [data])
        return biz_name + '已添加'


# 删除扩展信息接口
@app.route('/action/extend/delete')
def action_extend_delete():
    delete("av_extend", dict(request.values))
    return '已删除'


# 删除影片 仅限手动调用
@app.route('/action/delete/movie/<linkid>')
def action_delete_movie(linkid=''):
    delete("av_list", {"linkid": linkid})
    return 'movie已删除'


# 删除演员 仅限手动调用
@app.route('/action/delete/stars/<linkid>')
def action_delete_stars(linkid=''):
    star_movie = query_sql("SELECT linkid,stars_url FROM av_list WHERE stars_url like '%|{}%'".format(linkid))
    for item in star_movie:
        move_star_list = query_sql("SELECT linkid FROM av_stars WHERE linkid IN ('{}')".format(
            item['stars_url'].strip('|').replace('|', "','")
        ))
        if len(move_star_list) == 1:
            delete("av_list", {"linkid": item['linkid']})
    delete("av_stars", {"linkid": linkid})
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


@app.route('/action/change/language')
def action_change_language():
    country = request.values['country']
    CONFIG.set("base", "country", country)
    config_save(CONFIG)
    config_init()
    return 'ok'


def upper_path(path: str) -> str:
    # 如果为windows环境路径，则路径首字母大写
    if re.match("^[a-z]:\\\\", path):
        return path[0].upper() + path[1:]
    else:
        return path


# 上色
def a_tag_build(link):
    return '<a href="{}">{}</a>'.format(link, link)


# 识别linkid
def is_linkid(linkid: str = '') -> bool:
    if linkid is None:
        return False
    return re.match('^[a-z0-9]{16}$', linkid)


# 分页
def pagination(pagenum, count, pageroot, pagelimit=None) -> dict:
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
    sql_text = "SELECT * FROM av_list WHERE {} ".format(where_str)
    result = query_sql(
        sql_text + ' ORDER BY {} LIMIT {},{}'.format(sql_order_by, (page_num - 1) * page_limit, page_limit))

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
        extend_list = storage("av_extend", {"extend_name": "movie_res", "key": [result[i]['av_id']]}, "val")
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
    return result, get_sql_count(sql_text)


def get_sql_count(sql_text):
    return query_sql('SELECT COUNT(1) AS count FROM ({})'.format(sql_text))[0]['count']


# 遍历文件
def walk_all_files(path_target):
    for root, dirs, files in os.walk(path_target):
        for file in files:
            yield root, file


if __name__ == '__main__':
    pass
