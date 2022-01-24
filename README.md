## 运行需求
python3
**第三方包**
```
pip install requests
pip install lxml
pip install flask
```
## 功能

- `http://127.0.0.1:5000/actresses`指定演员id，抓取名下所有影片
- `http://127.0.0.1:5000/actresses`指定影片id，抓取指定影片
- `http://127.0.0.1:5000/action/scandisk`扫描本地硬盘，识别文件名
- `http://127.0.0.1:5000/search/keyword`多关键字搜索
- 本地视频路径绑定到番号，在网页中点击打开本地视频
- 标题快捷翻译
- 电影分析，标签，合作演员，时长

方便管理影片信息和视频文件

**示例：**
- `https://avmoo.com/cn/star/1971f1973cf8172f`，演员id为`1971f1973cf8172f`
- `https://avmoo.com/cn/movie/7ab0ec65e785e691`，影片id为`7ab0ec65e785e691`

## 打开方法
命令行运行`python flask_avmo.py`或者`start_web.bat` 启动本地web(首次打开会创建db)
打开`http://127.0.0.1:5000`即可看到主页
