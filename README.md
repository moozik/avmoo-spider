最新地址：https://javmoo.net/cn

# avio.pw番号爬虫

## 使用方法
抓取来自avio.pw的信息，并插入数据库，id区间为0000-zzzz
`get_av_spider.py -i -s 0000 -e zzzz`

抓取来自avio.pw的信息，不进行存储操作
`get_av_spider.py -s 1000 -e 2000`

接着上次抓取并使用代理
`get_av_spider.py -a -p http://127.0.0.1:1080`

-h(-help):使用说明
-i(-insert):插入数据库
-s(-start):开始id(0000,1ddd,36wq)
-e(-end):结束id(0000,1ddd,36wq)
-a(-auto):获取当前最新的一个id和网站最新的一个id，补全新增数据
-p(-proxies):使用指定的https代理服务器或SOCKS5代理服务器。例如：-p http://127.0.0.1:1080,-p socks5://127.0.0.1:52772

## 联系方式
邮箱:moozik@qq.com
