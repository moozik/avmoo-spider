from flask import render_template
from flask import Flask
from flask import request
from flask import redirect
from flask import url_for
import sqlite3
import time
import re
import math
import os
app = Flask(__name__)

#数据库列名
'''
0 => id
1 => linkid
2 => title
3 => av_id
4 => release_date
5 => len
6 => director
7 => studio
8 => label
9 => series
10 => genre
11 => stars
12 => director_url
13 => studio_url
14 => label_url
15 => series_url
16 => bigimage
17 => image_len

linkid,title,av_id,release_date,genre,stars,replace(bigimage,"pl.jpg","ps.jpg") as simage,id
'''

#每页展示的数量
PAGE_LIMIT = 30
CDN_SITE = '//jp.netcdn.space'


@app.route('/spider')
def spider():
    os.popen('python spider_avmo.py -i -a')
    return '正在更新'

@app.route('/')
@app.route('/page/<int:pagenum>')
@app.route('/search/<keyword>')
@app.route('/search/<keyword>/page/<int:pagenum>')
def index(keyword = '', pagenum = 1):
    if pagenum < 1:
        redirect(url_for('/'))
    limit_start = (pagenum -1) * PAGE_LIMIT
    keyword = keyword.replace("'",'').replace('"','').strip()

    if re.match('[a-zA-Z0-9 \-]{4,14}', keyword):
        where = 'av_id="{}"'.format(keyword.replace(' ', '-').upper())
    elif keyword != '':
        where = ''
        key_list = keyword.split(' ')
        for key_item in key_list:
            where += '''
            (title like "%{0}%" or
            director like "%{0}%" or
            studio like "%{0}%" or
            label like "%{0}%" or
            series like "%{0}%" or
            genre like "%{0}%" or
            stars like "%{0}%")and'''.format(key_item)
        where = where[:-3]
    elif keyword == '':
        where = '1'
    result = sqliteSelect('*', 'av_list', where, (limit_start, PAGE_LIMIT))
    if keyword != '':
        page_root = '/{}/{}'.format('search', keyword)
    else:
        page_root = ''
    return render_template('index.html', data=list_filter(result[0]), cdn=CDN_SITE, pageroot=page_root, page=pagination(pagenum, result[1]), keyword=keyword)


@app.route('/released')
@app.route('/released/page/<int:pagenum>')
def released(pagenum = 1):
    if pagenum < 1:
        redirect(url_for('/'))
    limit_start = (pagenum - 1) * PAGE_LIMIT
    date = time.strftime("%Y-%m-%d", time.localtime())
    where = 'release_date <= "{}"'.format(date)
    result = sqliteSelect(
        '*', 'av_list', where, (limit_start, PAGE_LIMIT))

    page_root = '/released'
    return render_template('index.html', data=list_filter(result[0]), cdn=CDN_SITE, pageroot=page_root, page=pagination(pagenum, result[1]), keyword='已发布 ')

@app.route('/movie/<linkid>')
def movie(linkid=''):
    if linkid=='':
        redirect(url_for('/'))
    if '-' in linkid:
        where = ' av_id="{}"'.format(linkid.upper())
    else:
        where = ' linkid="{}"'.format(linkid)
    result = sqliteSelect(
        '*', 'av_list', where, (0, 1))[0][0]
    
    #系列
    if result[10]:
        genre = result[10].split('|')
    else:
        genre = ''
    #演员
    if result[11]:
        actor = result[11].split('|')
    else:
        actor = ''
    #图片
    img = []
    if result[17] != '0':
        count = int(result[17])
        imgurl = CDN_SITE + '/digital/video' + result[16].replace('pl.jpg', '')
        for i in range(1, count+1):
            img.append((
                '{}-{}.jpg'.format(imgurl, i),
                '{}jp-{}.jpg'.format(imgurl, i)
            ))
    else:
        img = ''
    return render_template('movie.html', data=result, genre=genre, img=img, actor=actor, cdn=CDN_SITE)



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
def search(keyword='', pagenum = 1):
    if pagenum < 1:
        redirect(url_for('/'))
    limit_start = (pagenum - 1) * PAGE_LIMIT

    function = request.path.split('/')[1]
    if function == 'director' or function == 'studio' or function == 'label' or function == 'series':
        where = '{}_url="{}"'.format(function, keyword)
    if function == 'genre':
        where = 'genre like "%{}%"'.format(keyword)
    if function == 'stars':
        where = 'stars like "%{}%"'.format(keyword)

    page_root = '/{}/{}'.format(function, keyword)
    result = sqliteSelect(
        '*', 'av_list', where, (limit_start, PAGE_LIMIT))
    return render_template('index.html', data=list_filter(result[0]), cdn=CDN_SITE, pageroot=page_root, page=pagination(pagenum, result[1]), keyword='')


@app.route('/genre')
def genre():
    result = sqliteSelect('name,title','av_genre',1,(0,500),'')
    data = {}
    for item in result[0]:
        if item[1] not in data:
            data[item[1]] = []
        data[item[1]].append(item)
    data = list(data.values())
    return render_template('genre.html', data=data, cdn=CDN_SITE)



@app.route('/like/add/<data_type>/<data_val>')
def like_add(data_type=None, data_val=None):
    if data_type != None and data_val != None:
        timetext = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        sqltext = 'replace into av_like values("{}", "{}", "{}")'.format(
            data_type, data_val, timetext)
        DB['CUR'].execute(sqltext)
        DB['CONN'].commit()
        return 'ok'
    return ''


@app.route('/like/movie')
@app.route('/like/movie/page/<int:pagenum>')
def like_page(keyword='', pagenum=1):
    if pagenum < 1:
        redirect(url_for('/'))
    limit_start = (pagenum - 1) * PAGE_LIMIT
    if keyword == 'movie':
        keyword = 'av_id'

    main_sql = "select av_list.* from av_like join av_list on av_like.type='av_id' and av_like.val = av_list.av_id"
    select_sql = main_sql + ' order by av_like.time desc limit {}, {}'.format(
        limit_start, PAGE_LIMIT)
    count_sql = main_sql.replace('av_list.*', 'count(1)')
    
    page_root = '/like/{}/page'.format(keyword)
    result = db_fetchall(select_sql)
    page_count = db_fetchall(count_sql)[0][0]
    return render_template('index.html', data=list_filter(result), cdn=CDN_SITE, pageroot=page_root, page=pagination(pagenum, page_count), keyword='')


@app.route('/like/<keyword>')
def like_page_other(keyword=''):
    map_ = {
        'director':'导演',
        'studio':'制作',
        'label':'发行',
        'series':'系列',
    }
    #director
    #studio
    #label
    #series
    sqltext = "select av_list.* from av_like join (select * from av_list GROUP BY {0}_url order by id desc )av_list on av_like.type='{0}' and av_like.val=av_list.{0}_url".format(
        keyword
    )
    result = db_fetchall(sqltext)
    return render_template('like.html', data=list_filter(result), cdn=CDN_SITE, type_nick=map_[keyword], type_name=keyword, type_url=keyword + '_url')


@app.route('/like/stars')
def like_stars():
    sqltext = 'SELECT val FROM "av_like" where type="stars"'
    result = db_fetchall(sqltext)
    return render_template('stars.html', data=result)

def list_filter(data):
    result = []
    for row in data:
        result.append({
            'linkid':row[1], #linkid
            'title':row[2], #title
            'av_id':row[3], #av_id
            'release_date':row[4], #release_date
            'genre':row[10], #genre
            'stars':row[11], #stars
            'smallimage':row[16].replace('pl.jpg','ps.jpg'), #bigimage
            'director':row[6],#director
            'studio':row[7],#studio
            'label':row[8],#label
            'series':row[9],#series
            'director_url':row[12],  #director_url
            'studio_url':row[13],  #studio_url
            'label_url':row[14],  #label_url
            'series_url':row[15],  #series_url
        })
    return result

def pagination(pagenum, count):
    pagecount = math.ceil(count/PAGE_LIMIT)
    if pagecount<=15:
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

    pagelist = [x for x in range(p1, p2+1)]

    if pagenum != pagecount:
        pageright = pagenum + 1
    else:
        pageright = 0
    if pagenum != 1:
        pageleft = pagenum -1
    else:
        pageleft = 0
    
    return {
        'now': pagenum,
        'left': pageleft,
        'right': pageright,
        'list': pagelist
    }

def conn(dbfile= 'avmoo.db'):
    if os.path.exists('avmoo_.db'):
        dbfile = 'avmoo_.db'
    CONN = sqlite3.connect(dbfile, check_same_thread=False)
    CUR = CONN.cursor()
    return {
        'CONN':CONN,
        'CUR':CUR,
    }


def sqliteSelect(column='*', table='av_list', where='1', limit=(0, 30), order='id desc'):
    #db = conn()
    if order.strip() == '':
        order = ''
    else:
        order = 'order by ' + order
    sqltext = 'select {} from {} where {} {} limit {},{}'.format(
        column, table, where, order, limit[0], limit[1])

    result = db_fetchall(sqltext)
    # print('sql:', sqltext)

    sqltext = 'select count(1) as count from {} where {}'.format(table, where)
    result_count = db_fetchall(sqltext)[0][0]
    return (result, result_count)

def db_fetchall(sql):
    DB['CUR'].execute(sql)
    return DB['CUR'].fetchall()

if __name__ == '__main__':
    DB = conn()
    app.run()
