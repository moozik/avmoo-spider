## 运行需求
python3
**第三方包**
```
pip install requests
pip install lxml
pip install flask
```

## 本地web服务器（读取db内容）

![running_flask](https://raw.githubusercontent.com/moozik/avmoo-spider/master/running_flask.png)

- `python flask_avmo.py` 启动本地web
- 打开`http://127.0.0.1:5000`

## 爬虫（写数据到db）

目标在 https://tellme.pw/avmoo
如果网址变了，需要手动把目标网址换了

首次运行会自动创建本地db文件

![running_spider](https://raw.githubusercontent.com/moozik/avmoo-spider/master/running_spider.png)

抓取指定演员所有影片
`https://avmoo.casa/cn/star/1971f1973cf8172f`
将`1971f1973cf8172f`放到本地web的搜索框，可以更新指定演员id的所有影片到本地数据库
