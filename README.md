## 运行需求
python3
**第三方包**
```bash
pip install requests
pip install lxml
pip install flask
```
## 功能

- `http://127.0.0.1:5000/spider`输入链接，抓取链接内所有影片，自动翻页，跳过已抓取影片
- `http://127.0.0.1:5000/action/scandisk`扫描本地硬盘，识别文件名
- `http://127.0.0.1:5000/search/keyword`多关键字搜索
- 本地视频路径绑定到番号，在网页打开本地视频
- 标题快捷翻译
- 电影分析

方便管理影片信息和视频文件


## 打开方法
命令行运行`python flask_avmo.py`启动本地web(首次打开会创建db)
打开`http://127.0.0.1:5000`即可看到主页

如果遇到运行错误，尝试删除`config.ini`，可能有新增配置项


## 查看数据库数据
可以用`sqlite-web`这个库
```bash
pip install sqlite-web
sqlite_web avmoo.db
```