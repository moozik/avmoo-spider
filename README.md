## 运行需求
python3
**第三方包**
```
pip install requests
pip install lxml
pip install flask
```

## 本地web服务器

![running_flask](https://raw.githubusercontent.com/moozik/avmoo-spider/master/running_flask.png)

- `python flask_avmo.py` 启动本地web
- 打开`http://127.0.0.1:5000`

## 爬虫

目标在 https://tellme.pw/avmoo

![running_spider](https://raw.githubusercontent.com/moozik/avmoo-spider/master/running_spider.png)

抓取来自avmoo.pw的信息，id区间为0000-0100
`spider_avmo.py -s 0000 -e 0100`

接着上次抓取电影
`spider_avmo.py -a`

接着上次抓取演员
`spider_avmo.py -t`

更新类别
`spider_avmo.py -g`

抓取字幕（字幕网没了）
`spider_avmo.py -u keyword`
```
-h(-help):使用说明
-s(-start):开始id
    例如：'-s 0000' '-s 1ddd'
-e(-end):结束id
    例如：'-e xxxx' '-e zzzz'
-a(-auto):(常用)获取当前数据库最新的一个id和网站最新的一个id，补全新增数据
-r(-retry):重试错误链接
-g(-genre):更新类别
-t(-stars):更新演员
-p(-proxies):使用指定的https代理服务器或SOCKS5代理服务器。
    例如：'-p http://127.0.0.1:1080,-p socks5://127.0.0.1:52772'
-u(-163sub):使用指定关键字查找视频字幕。
    例如：'-u IPZ' '-u ABP'
```
