最新地址：https://avmoo.net/

## 仿avmoo站

- `pip install flask` 安装flask
- `python flask_avmo.py` 启动本地web
- 打开`http://127.0.0.1:5000`

打开http://127.0.0.1:5000 查看

## 爬虫抓取数据
抓取来自avmoo.pw的信息，id区间为0000-0100
`spider_avmo.py -s 0000 -e 0100`

接着上次抓取电影
`spider_avmo.py -a`

接着上次抓取演员
`spider_avmo.py -t`

更新类别
`spider_avmo.py -g`

- -h(-help):使用说明
- -s(-start):开始id(0000,1ddd,36wq)
- -e(-end):结束id(0000,1ddd,36wq)
- -a(-auto):获取当前数据库最新的一个id和网站最新的一个id，补全新增数据
- -r(-retry):重试错误链接
- -g(-genre):更新类别
- -t(-stars):更新演员
- -p(-proxies):使用指定的https代理服务器或SOCKS5代理服务器。例如：-p http://127.0.0.1:1080,-p socks5://127.0.0.1:52772
