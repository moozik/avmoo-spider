## 运行需求
python3
**第三方包**
```bash
pip install requests
pip install lxml
pip install flask
```
## 功能

- `/spider`输入链接，抓取链接内所有影片
- `/scandisk`扫描本地硬盘，识别番号文件名
- `/analyse/star/4d2d8be56df2dead`分析影片
- `/search/keyword`多关键字搜索
- 本地视频路径绑定到番号，在网页打开本地视频
- 标题快捷翻译
- 电影分析

方便管理影片信息和视频文件


## 打开方法
命令行运行`python run.py`启动本地web(首次打开会创建db)
默认地址为`http://127.0.0.1:5000`，端口可通过配置修改
首次使用需要打开一下`/genre`页面抓取类目信息
