from flask import render_template
from flask import Flask
from flask import request
from flask import redirect
from flask import url_for
import sqlite3
import re
import math
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
'''

#每页展示的数量
PAGE_LIMIT = 30
CDN_SITE = '//jp.netcdn.space/digital/video'

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
        where = '''
         title like "%{0}%" or
         av_id like "%{0}%" or
         series like "%{0}%" or
         genre like "%{0}%" or
         stars like "%{0}%"
         '''.format(keyword)
    elif keyword == '':
        where = '1'
    result = sqliteSelect(
        'linkid,title,av_id,release_date,genre,stars,replace(bigimage,"pl.jpg","ps.jpg") as simage', 'av_list', where, (limit_start, PAGE_LIMIT))
    if keyword != '':
        page_root = '/{}/{}'.format('search', keyword)
    else:
        page_root = ''
    return render_template('index.html', data=result[0], cdn=CDN_SITE, pageroot=page_root, page=pagination(pagenum, result[1]))


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
    genre = result[10].split('|')
    #演员
    actor = result[11].split('|')
    #图片
    img = []
    if result[17] != '0':
        count = int(result[17])
        imgurl = CDN_SITE + result[16].replace('pl.jpg','')
        for i in range(1, count+1):
            img.append((
                '{}-{}.jpg'.format(imgurl, i),
                '{}jp-{}.jpg'.format(imgurl, i)
            ))
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
@app.route('/star/<keyword>')
@app.route('/star/<keyword>/page/<int:pagenum>')
def search(keyword='', pagenum = 1):
    if pagenum < 1:
        redirect(url_for('/'))
    limit_start = (pagenum - 1) * PAGE_LIMIT

    function = request.path.split('/')[1]
    if function == 'director' or function == 'studio' or function == 'label' or function == 'series':
        where = '{}_url="{}"'.format(function, keyword)
    if function == 'genre':
        where = 'genre like "%{}%"'.format(keyword)
    if function == 'star':
        where = 'stars like "%{}%"'.format(keyword)

    page_root = '/{}/{}'.format(function, keyword)
    result = sqliteSelect(
        'linkid,title,av_id,release_date,genre,stars,replace(bigimage,"pl.jpg","ps.jpg") as simage', 'av_list', where, (limit_start, PAGE_LIMIT))
    return render_template('index.html', data=result[0], cdn=CDN_SITE, pageroot=page_root, page=pagination(pagenum, result[1]))


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
    CONN = sqlite3.connect(dbfile, check_same_thread=False)
    CUR = CONN.cursor()
    return {
        'CONN':CONN,
        'CUR':CUR,
    }

def sqliteSelect(column = '*', table = 'av_list', where = '1', limit = (0,30)):
    #db = conn()
    sqltext = 'select {},id from {} where {} order by id desc limit {},{}'.format(
        column, table, where, limit[0], limit[1])
    DB['CUR'].execute(sqltext)
    result = DB['CUR'].fetchall()
    # print('sql:', sqltext)

    sqltext = 'select count(1) as count from {} where {}'.format(table, where)
    DB['CUR'].execute(sqltext)
    result_count = DB['CUR'].fetchall()[0][0]
    return (result, result_count)


if __name__ == '__main__':
    DB = conn()
    app.run()
