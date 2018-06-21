from flask import render_template
from flask import Flask
from flask import request
from flask import redirect
from flask import url_for
import sqlite3
import re
app = Flask(__name__)

#每页展示的数量
PAGE_LIMIT = 30
CDN_SITE = 'jp.netcdn.space'

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
    print(result[1])
    return render_template('index.html', data=result[0], cdn=CDN_SITE)


def conn(dbfile= 'avmo.db'):
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
    print('sql:', sqltext)

    sqltext = 'select count(1) as count from {} where {}'.format(table, where)
    DB['CUR'].execute(sqltext)
    result_count = DB['CUR'].fetchall()[0][0]
    return (result, result_count)


if __name__ == '__main__':
    DB = conn()
    app.run()
