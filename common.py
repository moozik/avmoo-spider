import requests
from lxml import etree

#avmoo_site = "https://avmoo.com"
avmoo_site = ""

def get_db_file():
    return 'avmoo.db'

def get_country():
    # cn tw en ja
    return 'cn'

def show_column_name(data, description) -> list:
    result = []
    for row in data:
        row_dict = {}
        for i in range(len(description)):
            row_dict[description[i][0]] = row[i]
        result.append(row_dict)
    return result

def fetchall(cur, sql) -> list:
    cur.execute(sql)
    ret = cur.fetchall()
    return show_column_name(ret, cur.description)

def get_avmoo_site():
    global avmoo_site
    if avmoo_site != "":
        return avmoo_site
    res = requests.get('https://tellme.pw/avmoo')
    html = etree.HTML(res.text)
    avmoo_site = html.xpath('/html/body/div[1]/div[2]/div/div[2]/h4[1]/strong/a/@href')[0]
    print("newUrl:{}".format(avmoo_site))
    return avmoo_site